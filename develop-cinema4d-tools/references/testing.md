# Testing Strategy

## Test pyramid

### Ordinary Python

Use for pure functions, settings migration, formatting, geometry math that does
not require `c4d`, state machines, and negative cases.

### c4dpy

Use `cinema4d-c4dpy` for:

- confirming symbols and parameter IDs in the target version;
- creating and inspecting documents, objects, tags, splines, materials, and
  render data;
- importing `.pyp` modules and calling non-GUI functions;
- save/reopen verification;
- ownership and lifetime regression probes;
- testing plugin logic that does not need host registration or an event loop.

Run through the skill's bounded runner. Require the success marker only after all
assertions and outputs complete.

Build fixtures with `mxutils` rather than by hand or from committed `.c4d`
files: `mxutils.Random(seed=...)` plus `mxutils.SceneFaker` generate a
reproducible scene of objects, materials, tags, layers, render data and tracks
from a seed. Assert with `mxutils.CheckType` / `CheckIterable` so a failure names
the symbol and expected type, and dump `GetSceneGraphString()` /
`GetParameterTreeString()` / `GetContainerTreeString()` into the log on failure —
a structural diff beats re-running with more prints.

For `.pyp`, use `SourceFileLoader`, build the spec with
`spec_from_loader`, insert the module into `sys.modules` before
`exec_module()`, and remove it during repeated-import cleanup. Do not use
`spec_from_file_location()` for the non-standard `.pyp` suffix.

### Real GUI

Use `cinema4d-gui-testing` only when behavior depends on:

- `GeDialog` or `GeUserArea` event loops;
- BaseDraw/editor state;
- global command dispatch;
- real plugin registration/lifecycle;
- focus, selection, timers, drag/drop, or asynchronous host callbacks.

GUI automation is opt-in and expensive. Static or headless success does not
authorize a GUI launch.

## Evidence

- Record target Cinema version and exact executable.
- Check output values, scene state, saved artifacts, and negative behavior.
- A process exit, done marker, imported module, or registered command is not a
  sufficient assertion by itself.
- After a failure, inspect complete logs/evidence before rerunning.
- Do not hide skipped GUI coverage; state what remains manual.
