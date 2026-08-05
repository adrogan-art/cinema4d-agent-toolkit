---
name: develop-cinema4d-tools
description: Design, implement, diagnose, refactor, and verify Cinema 4D Python scripts and plugins, including .py and .pyp tools, CommandData/ObjectData/TagData classes, GeDialog interfaces, resources, registration, installation structure, and version compatibility. Use when the deliverable is a reusable Cinema 4D tool or plugin rather than a client 3D scene. Route headless c4d-module checks to cinema4d-c4dpy and real event-loop, BaseDraw, command, or plugin-lifecycle checks to cinema4d-gui-testing.
---

# Develop Cinema 4D Tools

Build a maintainable tool that solves the workflow problem and has evidence for
the cheapest valid test tier.

## Route the task

- Use this skill for reusable Cinema 4D scripts, plugins, commands, objects,
  tags, dialogs, utilities, and development infrastructure.
- Use `build-cinema4d-projects` when the deliverable is a stand, photozone,
  installation, editable scene, or render set.
- Use `cinema4d-c4dpy` as the shared headless runtime, not as the product-design
  workflow.
- Use `cinema4d-gui-testing` only when the assertion requires the real host GUI,
  event loop, BaseDraw, command dispatch, or plugin lifecycle.

## Load only relevant references

1. Read [references/architecture.md](references/architecture.md) before a new
   plugin, major feature, or structural refactor.
2. Read [references/testing.md](references/testing.md) before executing code or
   deciding whether GUI verification is necessary.
3. Read [references/ui-and-lifecycle.md](references/ui-and-lifecycle.md) for
   `GeDialog`, TreeView, timers, commands, document events, or plugin lifecycle.
4. Read [references/dialog-persistence.md](references/dialog-persistence.md)
   only when a dialog must remember layout or values across open/close, layout
   switches, or restarts.
5. Read [references/version-and-api.md](references/version-and-api.md) when API
   symbols, parameter IDs, threading rules, localization, renderer objects, or
   Cinema versions matter.
6. Read [references/delivery.md](references/delivery.md) before installation,
   encryption, licensing, or final handoff.

## Workflow

### 1. Establish the tool contract

- Identify the target Cinema 4D version, plugin type, user workflow, inputs,
  outputs, persistent state, and required UI behavior.
- Inspect the repository, current implementation, tests, resources, and local
  instructions before editing.
- Preserve unrelated user changes. Do not replace a working architecture merely
  to match a preferred template.
- Separate requested behavior from optional polish and future ideas.

### 2. Design for testability

- Keep pure calculations and state transitions outside Cinema callbacks when
  possible.
- Keep C4D API adapters thin and explicit.
- Keep registration and module import free of destructive or expensive side
  effects.
- Centralize IDs, version-dependent symbols, settings keys, and resource paths.
- Make document ownership, object ownership, bitmap ownership, and cache
  lifetime explicit.

### 3. Implement the smallest complete change

- Follow the repository's naming, packaging, resource, and localization
  conventions.
- Preserve stable plugin IDs and serialized data unless migration is part of the
  task.
- Use native C4D types and callbacks only where they provide real host behavior.
- Avoid rebuilding dynamic UI, scene data, or caches from periodic callbacks
  when an in-place update is sufficient.
- Add focused comments for non-obvious host constraints, not for ordinary code.

### 4. Verify by cost

1. Ordinary Python: pure logic, parsing, state, math, serialization, and mocks.
2. `cinema4d-c4dpy`: API symbols, scene/object behavior, plugin-module import,
   bitmap/geometry lifetime, saved files, and non-GUI regression tests.
3. `cinema4d-gui-testing`: only approved real-host UI/lifecycle assertions. Ask
   the user whether they will verify in the GUI themselves before proposing or
   launching an automated Cinema run; many prefer to drive the real host
   manually and want only the first two tiers automated.

Fail on missing evidence. A successful import or process exit alone does not
prove the tool works.

### 5. Deliver

- Report changed files, target Cinema version, tests run, results, installation
  state, and anything requiring manual verification.
- Do not install into additional Cinema versions or user locations unless they
  are in scope.
- Do not claim a GUI behavior was verified when only headless tests ran.

## Completion contract

Complete only when:

- the requested workflow is implemented;
- the code has clear ownership and separation between pure logic, C4D adapter,
  UI, and registration;
- applicable pure and c4dpy checks pass;
- GUI checks were either approved and passed or explicitly left for manual
  verification;
- plugin resources and installation paths are valid for the target version;
- no known regression or unresolved destructive migration is hidden.

## Keep this skill learning

Add only confirmed, reproducible, generalizable guardrails. Put runtime/process
rules in `cinema4d-c4dpy`, GUI harness rules in `cinema4d-gui-testing`, and
scene-production rules in `build-cinema4d-projects`. Do not duplicate them here.
