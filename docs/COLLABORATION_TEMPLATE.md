# Collaboration Template

Use this template at the start of every new phase so the goal, constraints, and
acceptance criteria are locked before implementation begins.

## 1. Phase Goal Card

Fill these in first. Keep each item to one or two lines if possible.

```text
Phase goal:
Definition of done:
Priority for this phase:
Out of scope:
Validation required:
Special constraints:
```

### Guidance

- `Phase goal`: what this phase is trying to accomplish
- `Definition of done`: what concrete state counts as finished
- `Priority for this phase`: planning first, direct implementation, validation first, etc.
- `Out of scope`: what must not be touched in this phase
- `Validation required`: unit tests, mock E2E, real CODESYS, special modes, etc.
- `Special constraints`: TDD, strict typing, no manual UI intervention, migration compatibility, and similar constraints

## 2. Pre-Work Confirmation Summary

Before starting implementation, reply with these four items:

```text
My understanding of the goal:
My first step:
What I am not planning to do in this phase:
Main risks or open uncertainties:
```

If the summary is not corrected, proceed.

## 3. Uncertainty Handling Rule

When an uncertainty appears, classify it before asking:

- Discoverable fact:
  Check the repo, docs, config, logs, stubs, and environment first.
- High-impact preference or tradeoff:
  Ask before proceeding.
- Low-risk, reversible detail:
  Use the safest default and note the assumption in the update.

Ask before proceeding when the uncertainty would:

- change the architecture boundary
- change the order of work
- change the definition of done
- add likely rework
- trigger a long real-environment validation path

Use this format when asking:

```text
Uncertainty:
Why it matters:
Recommended default:
What you need to decide:
```

## 4. Validation Layers

Default validation order:

1. Unit tests and static typing
2. Integration tests or mock E2E
3. Real CODESYS validation at phase boundaries or after environment-sensitive changes
4. Special-mode validation such as `--noUI`, alternate profiles, or other non-default runtime modes

Rules:

- Do not treat the slowest real-environment path as the default for every change.
- Run real CODESYS validation when the phase goal or recent changes justify it.
- Treat special modes as a separate compatibility track unless the phase goal explicitly makes them primary acceptance criteria.

## 5. Progress Update Format

Interim updates should normally include:

```text
Current task:
Why this task is next:
What is now confirmed:
Next step:
```

If the direction changes, add:

```text
What changed:
What this affects:
Whether a decision is needed:
```

## 6. End-of-Phase Retrospective

At the end of a phase, summarize:

```text
Completed:
What was unclear at the start:
Largest time cost:
Longest waiting path:
Avoidable rework:
What must be locked before the next phase:
```

## Default Assumptions

Unless explicitly changed in the phase goal card:

- High-impact uncertainties should be asked before proceeding.
- Host-side Python code should use strict typing.
- New behavior changes should follow TDD where practical.
- Real CODESYS validation is a phase-boundary activity, not the default after every edit.
- Special modes like `--noUI` are compatibility paths unless promoted to primary acceptance criteria.
