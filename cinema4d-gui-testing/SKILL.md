---
name: cinema4d-gui-testing
description: Run deterministic Cinema 4D Python integration tests that require the real Windows GUI, GeDialog event loop, BaseDraw, commands, focus/selection behavior, or host-only plugin lifecycle. Use as the GUI verification tier for tools designed with develop-cinema4d-tools when automated host evidence is explicitly requested or approved. Use cinema4d-c4dpy instead for headless c4d-module tests that do not require the Cinema GUI.
---

# Cinema 4D GUI testing

Run each test in a disposable Cinema 4D instance owned by the supplied Windows supervisor. Treat the driver and copied plugins as executable code.

This skill verifies real-host behavior; it does not design plugin architecture or
own the product-development workflow. Use `develop-cinema4d-tools` for that.

## Workflow

1. Prefer `cinema4d-c4dpy` when no GUI, event loop, BaseDraw, or host plugin lifecycle is required.
2. Ask the user first, in a single explicit question: will they verify in the GUI themselves, or should an automated GUI run be launched? Many users prefer to drive the real host manually and only want the headless/static tiers automated. Never launch Cinema on assumption, on a general "fix it" instruction, or because a GUI check merely looks useful. Wait for the answer.
3. Treat a Cinema GUI launch as an expensive, opt-in operation. Run it only after that answer explicitly requests or approves an automated run. If the user verifies manually, stop after headless/static checks and hand over a short, concrete manual checklist instead.
4. Read [references/safety.md](references/safety.md), [references/driver-contract.md](references/driver-contract.md), and [references/evidence.md](references/evidence.md).
5. Copy [scripts/driver_template.py](scripts/driver_template.py) into the target repository and implement only test semantics in `run(context)`.
6. Review the complete driver and every `--plugin-source` as trusted executable code. Never run an untrusted driver or plugin.
7. Run preparation first with `--dry-run`. Inspect the printed manifest and disposable root.
8. Run only after that review with an explicit `--run`. Use the matching Cinema 4D executable and a bounded timeout.
9. Accept success only when the supervisor exits zero. Preserve artifacts for failures or audit with `--keep-artifacts` or an explicit new `--root`.

```powershell
python scripts/run_cinema_gui_test.py --dry-run `
  --cinema "C:\Program Files\Maxon Cinema 4D 2026.3\Cinema 4D.exe" `
  --trusted-driver "C:\repo\tests\cinema_gui_driver.py" `
  --plugin-source "C:\repo\my_plugin"

python scripts/run_cinema_gui_test.py --run `
  --cinema "C:\Program Files\Maxon Cinema 4D 2026.3\Cinema 4D.exe" `
  --trusted-driver "C:\repo\tests\cinema_gui_driver.py" `
  --plugin-source "C:\repo\my_plugin" `
  --timeout 180 --keep-artifacts
```

The timeout of the shell/tool that launches the supervisor must be longer than
the supervisor's `--timeout`. Reserve at least 60 additional seconds for Cinema
startup, evidence parsing, and Job Object cleanup. Never wrap a 180-second GUI
run in a 10-second shell call. When the shell returns a running-cell identifier,
wait on that same cell instead of starting another Cinema process.

Add `--scene-readonly C:\path\scene.c4d` only when the driver needs a source scene. The harness fingerprints it before launch and again in `finally`; the driver must load it without saving it.

## Non-negotiable safety

- Never launch Cinema without first asking whether the user will verify in the GUI themselves and receiving an explicit request or approval for an automated run.
- Never attach to, automate, close, or reuse a Cinema instance opened by the user.
- Never enumerate or terminate processes by executable name.
- Never bypass the private Job Object, suspended launch, source fingerprints, isolated preferences, or evidence validation.
- Never reuse a previous artifact root. Supply a path that does not exist.
- Never interpret a Cinema window, process exit, or partial JSONL file as success.
- Do not add domain assertions to the supervisor; keep them in the driver via `context.check(...)`.
- Do not automatically rerun a failed GUI test. First read the complete
  `evidence.jsonl`, especially the `final` record and traceback, and distinguish
  a driver/supervisor failure from a product failure. Fix and validate everything
  possible statically or with c4dpy. A second GUI launch still requires the
  user's original explicit request or fresh approval.

The supervisor starts Cinema with `CreateProcessW(CREATE_SUSPENDED)`, assigns that exact process handle to a private `KILL_ON_JOB_CLOSE` Job Object, and only then resumes it. Any containment, protocol, crash, timeout, stale-evidence, or source-mutation failure is a failed test.

## Importing a copied plugin package from a driver

The supervisor renames every copied source. A package directory arrives as
`plugins/source-01-<name>`, and a single-file `--plugin-source` arrives as a
*directory* `plugins/source-02-<name>.py` holding the file under its real name.

Consequences for the driver:

- A package whose modules use absolute self-imports (`from mypkg.x import y`)
  cannot be imported by adding a path, because the directory no longer carries
  the package name. Register it explicitly and let submodules resolve through
  the package `__path__`:

```python
spec = importlib.util.spec_from_file_location(
    "mypkg", os.path.join(package_dir, "__init__.py"),
    submodule_search_locations=[package_dir])
module = importlib.util.module_from_spec(spec)
sys.modules["mypkg"] = module
spec.loader.exec_module(module)
```

- For a plugin-root module, put the *containing directory* on `sys.path`, and
  probe both the supplied path and its parent so the wrapper-directory detail
  does not matter.
- Supply every module the package imports at module scope as its own
  `--plugin-source`. Grep the package for non-stdlib top-level imports before
  the first launch instead of discovering them one failed run at a time.

## Keep the artifact root path short

Choose a short `--root` such as `C:\Temp\c4dgui1`. The run root nests
`plugins/source-NN-<original name>/<original name>`, adding well over 100
characters, and Windows still applies `MAX_PATH` (260) to these APIs: with a long
root, `os.path.isfile()` silently returns `False` for a file that exists, so the
driver reports a missing plugin source instead of a path-length failure. Never
diagnose such a "missing module" without first checking the path length.

## Opening plugin UI from a driver

Avoid `c4d.CallCommand()` from the bootstrap timer merely to obtain and inspect an
asynchronous dialog. It can re-enter the host command/event path and stall the
driver before evidence is written. `plugins.FindPlugin()` returns a `BasePlugin`,
not the registered Python `CommandData`, so do not call `.Execute()` on it.

For dialog-focused verification, load the copied `.pyp` with
`SourceFileLoader`, register the module in `sys.modules` before execution,
instantiate its `GeDialog`, and call `Open(DLG_TYPE_ASYNC, pluginid=0, ...)`.
Do not use `spec_from_file_location()` for `.pyp`: its non-standard suffix can
yield a spec with no loader. Use global command dispatch only when command
dispatch itself is the behavior under test; in that case, design an event-loop
aware multi-phase driver instead of inspecting the dialog synchronously after
`CallCommand()`.

When evidence stops after command registration, do not conclude that the plugin
or its icons failed. Inspect the final evidence record first; missing downstream
checks usually indicate driver control-flow or event-loop failure.

## TreeView layout guardrail

For flat Python-backed lists, prefer `LV_TREE` for the primary name column so
Cinema 4D owns its text drawing and selection behavior. When any column uses
`LV_USER` or `LV_USERTREE`, implement `TreeViewFunctions.GetLineHeight()` with a
positive font-based height (for example `max(22, area.DrawGetFontHeight() + 8)`).
Without it, multiple rows can collapse onto one baseline under some UI scaling
and asynchronous dialog layouts. Give custom columns explicit minimum widths via
`GetColumnWidth()` and enable `TREEVIEW_FIXED_LAYOUT` when every row has the same
height.

## Dynamic layout focus guardrail

Do not call `LayoutFlushGroup()` or otherwise recreate dynamic row gadgets from
a periodic `GeDialog.Timer()` merely to poll model state. Replacing an active
`AddEditNumber`, `AddEditText`, LinkBox, or similar gadget destroys keyboard
focus, often making the field appear editable for only one timer interval. Keep
timer work non-structural (for example preview synchronization), rebuild rows
only for explicit structural changes or document switches, and update existing
gadgets in place for value-only changes.

## Dynamic layout state guardrail

`LayoutFlushGroup()` destroys the gadgets it rebuilds, so any value that lives
only in a gadget is lost. This is a separate defect from the focus loss above
and survives every workaround for it: rows come back looking correct while a
number field, a ComboBox selection, or a LinkBox link silently reverts.

Before rebuilding dynamic rows, read every editable gadget back into the model,
and when rebuilding, write every one of them back out. Reading first also
rescues an edit the user typed but never committed with Enter or a focus
change. Verify one field of each kind, not just the first: a bench that stored
the row label and the number still lost the ComboBox and the LinkBox.

Assert this in the driver by editing each control, triggering the rebuild, and
comparing the values afterwards. Comparing the link must use `GetGUID()`;
Cinema hands out fresh Python wrappers, so `==` and `is` both mislead.

## Row drag-reordering in a GeDialog

Both strategies work in Cinema 4D 2026.3, so choose on measured behavior rather
than on availability.

`GeUserArea.HandleMouseDrag` accepts `DRAGTYPE_ATOMARRAY` with a list holding
one `BaseObject` and then delivers `BFM_DRAGRECEIVE` normally. It raises
`SystemError: returned NULL without setting an exception` for `DRAGTYPE_ICON`
with a `BaseContainer` and with `None`, and Python exposes neither
`DRAGTYPE_PRIVATE` nor `GeDialog.HandleMouseDrag`. The payload can therefore
only be scene atoms: the atom list is a carrier, and a row identity has to
travel out of band on the dialog. Probe the payload shapes in that order before
concluding that a drag type is unusable; a single failed shape proves nothing.

Prefer letting an explicit drag handle own the mouse: a small `GeUserArea` that
calls `MouseDragStart`, loops on `MouseDrag`, and ends with `MouseDragEnd`.
Cinema's nested drag loop is never entered, so rebuilding rows immediately after
the drag ends is safe, and the insertion target stays defined for every sample.
Under `BFM_DRAGRECEIVE` one measured drag left `CheckDropArea` with no hit for
46% of its samples, because it answers only for an exact gadget rectangle: the
marker stalls whenever the pointer crosses the gap between rows or leaves the
handle column sideways.

Drive the insertion index from the absolute pointer position read through
`GetInputState`, not from the accumulated `MouseDrag` delta. One measured drag
reported a pointer offset of +79 px against a delta sum of -79: the delta runs
opposite to the pointer, and accumulating it also drifts over a long drag.

## Deterministic screenshot geometry

A driver that captures pixels must fix the window geometry itself before
reading `GetItemDim()` or calling `PrintWindow`. An asynchronous dialog,
especially one wrapped in a `ScrollGroupBegin`, does not honour the `defaulth`
passed to `Open()`; Cinema may pick a shorter window, so the same driver can
yield different capture heights and silently omit controls near the bottom on
one run and include them on the next.

Call `SetWindowPos` with `SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE` for an
explicit client size, let the layout settle, then capture. Assert that the
bottom-most gadget of interest fits inside the captured height, so a clipped
capture fails the test instead of producing a plausible but incomplete image.

`c4d.GeSleep()` does not exist in the Python API. Use `time.sleep()` for the
short settle window after resizing; `SetWindowPos` already delivers `WM_SIZE`
synchronously, so a brief pause is enough and no message pump is required.

## Keep this skill learning

Cinema's embedded Python can return the same `time.monotonic_ns()` value for
several evidence records emitted in one host tick. The bootstrap must normalize
each timestamp to `max(time.monotonic_ns(), previous + 1)` so the evidence
protocol remains strictly increasing without weakening supervisor validation.

When this workflow exposes a failure that is confirmed, reproducible,
generalizable to future Cinema 4D tests, and preventable with a concrete rule,
update this skill before finishing the task. Add the smallest useful guardrail
and a correct recipe or validation step. Do not add project-specific incidents,
unconfirmed guesses, transient environment failures, or duplicate guidance.
Tell the user when the skill was updated and why.
