# Real CODESYS Lessons

## Purpose

This document records the main mistakes, proven facts, and debugging rules learned during the real-CODESYS investigation.

It exists to prevent the team from repeating the same long-loop debugging pattern.

Use it together with:

- [CONTINUE_TOMORROW.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/CONTINUE_TOMORROW.md)
- [DEBUGGING_GUIDE.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/DEBUGGING_GUIDE.md)
- [CODESYS_BOUNDARY_CONTRACT.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/CODESYS_BOUNDARY_CONTRACT.md)

`CONTINUE_TOMORROW.md` is the live breakpoint.
This file is the durable lessons-learned reference.

## What We Got Wrong

### 1. We used long real E2E runs as the first diagnostic tool

This was the biggest process mistake.

It hid the actual failure layer because one failing `http-all` or `cli-all` run could mix:

- startup problems
- profile-selection problems
- cleanup problems
- project-creation problems
- object-discovery problems
- compile-message problems
- probe bugs

Rule:

- never start a new real-CODESYS investigation with aggregate E2E
- start with the shortest probe that can answer one question

### 2. We assumed host-side contracts before proving real CODESYS semantics

Examples:

- assuming `Application/PLC_PRG` could be resolved the same way in every context
- assuming a successful `pou/code` implied our readback probe used the same lookup path
- assuming `MissingVar := TRUE;` was a deterministic compile-error sample
- assuming `Standard.project` could be treated like a normal project file

Rule:

- in real CODESYS work, prove semantics first
- only after that should the host-side abstraction be trusted

### 3. We trusted probes before validating the probes

We had probe-specific faults that created fake conclusions:

- `pou/list` was initially called with `POST` instead of `GET`
- the first readback probe ignored `session.created_pous`
- some conclusions were based on probe behavior, not product behavior

Rule:

- every probe must have a single purpose
- every probe must be validated before using it to drive product conclusions

### 4. We changed broad behavior before isolating the real failing path

Example:

- standard UI compile was forced onto `_safe_message_harvest=True`
- that avoided one class of instability, but it also hid real compile errors from the normal UI path

Rule:

- do not widen a workaround to every path until the failing path is proven
- keep fallback behavior and normal behavior separate unless the semantics are verified identical

## Proven Facts

These are not hypotheses anymore.

### Startup And Cleanup

- sandbox launches were not authoritative for real product behavior
- normal-user terminal launches are authoritative
- `shell_string` launch matched manual successful startup
- explicit managed PID tracking plus cleanup removed residual IDE windows

### Object Discovery And Write Semantics

- `PLC_PRG` exists in the real workflow we tested
- `pou/code` can write real content into `PLC_PRG`
- readback only became trustworthy after it matched the real lookup order
- `session.created_pous` is a critical lookup path in the runtime

### Compile Validation

- IDE-visible compile errors can exist while our API initially reports success
- this proved compile message harvesting and compile result semantics are not the same thing

### Project Creation

- `scriptengine.projects.open(existing_project_path)` works on a normal saved `.project`
- `scriptengine.projects.open(Standard.project)` fails with:
  - `Controls created on one thread cannot be parented to a control on a different thread.`
- `scriptengine.projects.create(path, True)` succeeds
- `projects.create(...)` produces a minimal project skeleton:
  - `Project Settings`
  - `__VisualizationStyle`
- `projects.create(...)` does not automatically provide:
  - a device
  - an application
  - an active application
  - `PLC_PRG`

This means:

- the old `open(Standard.project)` plus `save_as(...)` strategy is the wrong creation primitive in this environment
- the correct new foundation is `scriptengine.projects.create(...)`

## The Closest Meaningful Boundary

The closest meaningful boundary between our host code and real CODESYS is not the HTTP endpoint itself.

It is:

1. [src/codesys_api/assets/PERSISTENT_SESSION.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/src/codesys_api/assets/PERSISTENT_SESSION.py)
2. `/api/v1/script/execute`
3. the raw IronPython snippet executed inside CODESYS
4. the `scriptengine` object model

That boundary provides these capabilities:

- persistent named-pipe request handling
- session state such as `active_project`
- raw script execution inside the real CODESYS process
- result normalization back to the host

This is the layer to debug when higher-level abstractions are suspect.

Do not jump straight to:

- `project/create`
- `project/compile`
- `http-all`
- `cli-all`

when the actual uncertainty is in the `scriptengine` primitive itself.

## Rules For Future Real-CODESYS Work

### Rule 1: Prove the primitive before building the abstraction

Before trusting a new high-level API:

- verify the raw `scriptengine` call with `/api/v1/script/execute`
- capture the result shape
- only then wrap it in action-layer, HTTP, and CLI abstractions

### Rule 2: Keep one probe per question

Good probes:

- startup probe
- open-template-only probe
- open-existing-project-only probe
- direct-create-only probe
- write-then-readback probe

Bad probes:

- any probe that tries to answer startup, project creation, and compile correctness in one run

### Rule 3: Use negative controls

Whenever possible, prove both:

- the failing primitive
- the nearby working primitive

Example:

- `projects.open(Standard.project)` fails
- `projects.open(existing_project)` succeeds

This was the key comparison that prevented us from wrongly concluding that `projects.open(...)` was generally broken.

### Rule 4: Separate “platform behavior” from “host behavior”

Ask in this order:

1. Did CODESYS itself do the thing?
2. Did our probe correctly observe it?
3. Did our abstraction preserve it?

Do not start with step 3.

### Rule 5: Record negative findings as first-class facts

A failed path is valuable if it is proven and repeatable.

Examples that must remain documented:

- `open(Standard.project)` is not a valid create primitive here
- `projects.create(...)` is valid but minimal
- `session.created_pous` matters for lookup

These facts prevent future false starts.

## Minimum Workflow For New Real-CODESYS Debugging

When a new real-CODESYS problem appears, use this order:

1. Reproduce with the smallest existing probe.
2. If the probe is still too broad, create a new raw `script/execute` probe.
3. Prove the primitive in `scriptengine`.
4. Compare one failing primitive with one nearby working primitive.
5. Only after that, modify the host abstraction.
6. Only after the lower layer is stable, return to aggregate E2E.

## What To Update When We Learn Something New

When a new real-CODESYS fact is proven:

1. update [CONTINUE_TOMORROW.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/CONTINUE_TOMORROW.md) with the active breakpoint
2. update this file if the lesson changes future debugging behavior
3. add or update the smallest probe that demonstrates the fact
4. add a light unit test if the probe shape or document should stay stable
