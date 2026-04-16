# CODESYS Boundary Contract

## Purpose

This document defines the only CODESYS-facing primitives that the host-side code is allowed to depend on.

The rule is strict:

- if a CODESYS primitive is not explicitly defined here
- and is not backed by a raw probe plus a stable result shape
- then higher layers must not rely on it

Use this document together with:

- [REAL_CODESYS_LESSONS.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/REAL_CODESYS_LESSONS.md)
- [CONTINUE_TOMORROW.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/CONTINUE_TOMORROW.md)

## Closest Supported Boundary

The closest supported boundary between host code and real CODESYS is:

1. [src/codesys_api/assets/PERSISTENT_SESSION.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/src/codesys_api/assets/PERSISTENT_SESSION.py)
2. `/api/v1/script/execute`
3. a raw IronPython snippet executed in the CODESYS process
4. the `scriptengine` object model

Everything above that boundary is host abstraction:

- `ironpython_script_engine`
- `action_layer`
- HTTP handlers
- CLI commands

These higher layers may only compose primitives that are explicitly approved below.

## Approved Primitives

### 1. Open Existing Project

Primitive:

- `scriptengine.projects.open(existing_project_path, ...)`

Status:

- approved

What is proven:

- opening a normal existing `.project` works in the real environment

Probe:

- [real_project_open_raw_probe.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/scripts/manual/real_project_open_raw_probe.py) with `--mode existing`

### 2. Create New Empty Project

Primitive:

- `scriptengine.projects.create(path, primary=True)`

Status:

- approved

What is proven:

- this succeeds in the real environment
- it produces a minimal project skeleton
- the result does not automatically include device/application/PLC runtime structure

Probe:

- [real_project_create_direct_raw_probe.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/scripts/manual/real_project_create_direct_raw_probe.py)

### 3. Raw Script Execution

Primitive:

- `/api/v1/script/execute`
- `CodesysPersistentSession.execute_script_content(...)`

Status:

- approved

What is proven:

- the host can execute small raw scripts inside the real CODESYS process
- this is the required path for validating new scriptengine primitives before wrapping them

### 4. Session-State-Assisted POU Lookup

Primitive:

- lookup via `session.created_pous`

Status:

- approved

What is proven:

- real `pou/code` and trustworthy readback depend on `session.created_pous`
- probe logic must mirror this lookup order when validating writes

Probe:

- [real_pou_code_roundtrip_probe.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/scripts/manual/real_pou_code_roundtrip_probe.py)

## Rejected Or Unsafe Primitives

These are explicitly not allowed as foundation primitives for higher-level abstractions.

### 1. Open Template As Normal Project

Primitive:

- `scriptengine.projects.open("...\\Templates\\Standard.project")`

Status:

- rejected

Why:

- real environment reproduces:
  - `Controls created on one thread cannot be parented to a control on a different thread.`

Meaning:

- `Standard.project` must not be treated like a normal project file opened through `projects.open(...)`
- higher-level `project/create` must not depend on this path

Probe:

- [real_project_open_raw_probe.py](/C:/Users/vboxuser/Desktop/Repos/codesys-api/scripts/manual/real_project_open_raw_probe.py) with `--mode template`

## Rules For Higher Layers

### Rule 1

`ironpython_script_engine`, `action_layer`, HTTP, and CLI may only depend on approved primitives.

### Rule 2

Before introducing a new CODESYS primitive into host code:

1. add a raw probe using `/api/v1/script/execute`
2. run it against real CODESYS
3. document the result here
4. only then wrap it in product code

### Rule 3

If a primitive is proven unsafe, do not patch around it in higher layers.

Replace the primitive.

Current example:

- do not patch around `open(Standard.project)`
- replace the create foundation with `projects.create(...)`

### Rule 4

A higher-level API is not considered stable unless the underlying boundary primitive is stable first.

Examples:

- `project/create` is not stable until the full create sequence on top of `projects.create(...)` is proven
- `project/compile` is not stable until message harvesting is proven against real IDE-visible errors

## Current Required Next Step

The next required contract task is:

- rebuild formal `project/create` on top of `scriptengine.projects.create(path, primary=True)`

Then validate, in order:

1. adding or resolving device structure
2. resolving or creating application structure
3. creating or resolving `PLC_PRG`
4. creating task configuration
5. creating `MainTask`
6. assigning the main program to the task

Only after that should compile-path validation continue.
