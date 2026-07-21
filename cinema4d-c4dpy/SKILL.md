---
name: cinema4d-c4dpy
description: Execute and verify Cinema 4D Python code headlessly with the matching c4dpy.exe. Use as shared test/runtime infrastructure for Cinema 4D tool development and scripted scene production when assertions require the c4d module but not GeDialog, BaseDraw, commands, or the real host event loop. Covers version selection, licensing, bounded execution, logs, success markers, owned-process cleanup, scene save/reopen checks, and safe .pyp module loading.
---

# Cinema 4D Headless Runtime

Run `c4d` assertions without automating the Cinema GUI. This skill is an
execution layer:

- use `develop-cinema4d-tools` to design or modify reusable scripts/plugins;
- use `build-cinema4d-projects` to assemble and validate production scenes;
- use `cinema4d-gui-testing` when the assertion requires the real host.

## Required workflow

1. Identify the exact target Cinema 4D version.
2. Select the matching `c4dpy.exe`; do not silently choose another installed
   version.
3. Inspect the probe/script before execution.
4. Use [scripts/run_c4dpy.ps1](scripts/run_c4dpy.ps1) with explicit executable,
   bounded timeout, redirected stdout/stderr, and a unique success marker.
5. Print the marker only after every assertion and output/save operation passes.
6. Accept success only when the runner exits zero and finds the marker.
7. Inspect logs and expected artifacts. For saved scenes, reopen and verify the
   relevant values when persistence matters.

Always pass:

```text
g_licenseModel=LICENSEMODEL::MAXONAPP
```

Without it, c4dpy can wait indefinitely for licensing.

## Safe invocation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "<this-skill>\scripts\run_c4dpy.ps1" `
  -Script "C:\project\tests\probe.py" `
  -C4dpyExe "C:\Program Files\Maxon Cinema 4D 2026\c4dpy.exe" `
  -StdoutPath "C:\project\logs\probe_stdout.txt" `
  -StderrPath "C:\project\logs\probe_stderr.txt" `
  -TimeoutSec 300
```

Set the shell/tool timeout longer than `TimeoutSec` so the runner can collect
evidence and clean its owned process tree.

Never terminate processes by executable name. The runner may stop only the root
PID it launched and descendants of that owned process.

## Probe contract

```python
def main():
    # assertions and output saves
    print("__C4DPY_SCRIPT_DONE__")


if __name__ == "__main__":
    main()
```

- Use a fresh `c4d.documents.BaseDocument()` per isolated test.
- Call `ExecutePasses` before reading generator/cache-dependent data.
- Assert values and object state, not only object existence.
- Clean disposable artifacts or save them under a dedicated test/log folder.
- Avoid exotic console output when Windows encoding is uncertain.

## Load `.pyp` without registration

Use this to test importable non-GUI plugin logic:

```python
import importlib.util
import sys
from importlib.machinery import SourceFileLoader

module_name = "plugin_under_test"
loader = SourceFileLoader(module_name, r"C:\path\plugin.pyp")
spec = importlib.util.spec_from_loader(module_name, loader)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not create .pyp loader")
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
try:
    loader.exec_module(module)
    # call non-GUI functions
finally:
    sys.modules.pop(module_name, None)
```

Do not use `spec_from_file_location()` for `.pyp`; its non-standard suffix can
produce a spec without a loader. Inserting into `sys.modules` before execution is
required by dataclasses, typing, and similar module-level machinery.

## Boundaries and known traps

- Do not test `GeDialog`, `GeUserArea`, BaseDraw/editor behavior, global command
  dispatch, or real registration/lifecycle here.
- `GetSplinePoint` and `SplineHelp.GetPosition` may represent coarse
  tessellation; do not use them as sub-unit analytical ground truth.
- `GeClipMap.GetBitmap()` is borrowed. Retain the owning `BaseBitmap` instead of
  returning or caching the borrowed wrapper beyond the `GeClipMap` lifetime.
- A done marker proves only that the probe reached its end. The probe must
  contain meaningful assertions.

## Keep this skill learning

Store only shared headless runtime, process, import, ownership, and evidence
rules here. Put plugin architecture/UI knowledge in `develop-cinema4d-tools` and
scene-production knowledge in `build-cinema4d-projects`.
