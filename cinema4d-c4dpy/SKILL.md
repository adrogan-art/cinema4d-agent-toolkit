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
   version. **The install directory name does not state the version.** On this
   machine `C:\Program Files\Maxon Cinema 4D 2026\c4dpy.exe` is 2026.1.0, while
   2026.3.0 and 2026.3.3 live in their own directories. Read the file version
   before choosing, and print `c4d.GetC4DVersion()` from inside the probe so the
   log proves which runtime produced the evidence:

   ```powershell
   Get-ChildItem "C:\Program Files\Maxon Cinema 4D*\c4dpy.exe" |
     ForEach-Object { "$($_.FullName) -> $($_.VersionInfo.FileVersion)" }
   ```

   Picking the wrong one fails in the most misleading way possible: symbols
   introduced in 2026.2 (`RENDERFLAGS_AUTO_SETUP`, `AllocateRenderBitmap`, …)
   are simply absent, which reads as "the API does not exist" rather than
   "wrong runtime".
3. Inspect the probe/script before execution.
4. Use [scripts/run_c4dpy.ps1](scripts/run_c4dpy.ps1) with explicit executable,
   bounded timeout, redirected stdout/stderr, and a unique success marker.
5. Print the marker only after every assertion and output/save operation passes.
6. Accept success only when the runner exits zero and finds the marker.
7. Inspect logs and expected artifacts. For saved scenes, reopen and verify the
   relevant values when persistence matters.
8. Count technical attempts separately from successful scene/render stages.
   After preflight, allow one automatic corrective retry per technical stage.
   If it also fails, stop blind retries and use only an already verified
   fallback or report the blocker.

Always pass:

```text
g_licenseModel=LICENSEMODEL::MAXONAPP
```

Without it, c4dpy can wait indefinitely for licensing. The other accepted models
are `LICENSEMODEL::MAXONACCOUNT` (needs `-g_licenseUsername` and
`-g_licensePassword`, and does not work for accounts federated through Apple,
Google, or Facebook), `LICENSEMODEL::RLM`, and `LICENSEMODEL::LICENSESERVER`.
Run the executable interactively once before any automation: the first launch
prompts for a login and no unattended run succeeds until that is done.

Other c4dpy arguments worth knowing: `-c "<code>"` to execute a string, `-m` to
run a module, `-B` to suppress `.pyc` writes, `-E` to ignore `PYTHON*` env vars,
`-S` to skip `site`, and `-g_encryptPypFile=<path>` to encrypt a `.pyp` exactly
as the *Extensions ▸ Tools ▸ Source Protector* menu command does.

A script passed to c4dpy is a plain Python script, **not** a Script Manager
script: `doc` and `op` are not defined for you.

## API preflight for launch-limited work

When the task limits c4dpy launches, do not spend a launch discovering avoidable
API mistakes. Before the first run, check every newly used `c4d.*` symbol and
object method against the matching installed SDK stubs or a working local
example from that Cinema version.

Set document units with the value type required by Cinema 4D 2026:

```python
unit_scale = c4d.UnitScaleData()
unit_scale.SetUnitScale(1.0, c4d.DOCUMENT_UNIT_CM)
doc[c4d.DOCUMENT_DOCUNIT] = unit_scale
```

Do not assign `c4d.DOCUMENT_UNIT_CM` directly to `DOCUMENT_DOCUNIT`; Cinema 4D
2026 expects `UnitScaleData`.

For headless render-camera selection:

```python
doc.ForceCreateBaseDraw()
base_draw = doc.GetRenderBaseDraw()
if base_draw is None:
    raise RuntimeError("Document has no render BaseDraw")
base_draw.SetSceneCamera(camera)
```

- Do not call `BaseDocument.SetRenderBaseDraw()`; that method is not present in
  the Cinema 4D 2026 Python API.
- After reopening a saved scene, select the render camera again and assert that
  `base_draw.GetSceneCamera(doc)` resolves to the intended camera before
  rendering.
- Match camera and renderer families. In scene-production tasks, never render a
  Redshift Camera through the Standard renderer; set and read back the verified
  Redshift engine for the exact installed version.
- Do not use `c4d.SCENEFILTER_ALL`; it is not present in the Cinema 4D 2026
  Python API. Pass only explicit, matching-runtime flags to `LoadDocument`,
  such as `c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS`.
- Compare `base_draw.GetSceneCamera(doc)` to the intended camera by identity
  data such as `GetName()`/`GetGUID()`, not with Python `is`: the binding
  returns a fresh wrapper object each call, so `is` fails even when the correct
  camera is active (verified in Cinema 4D 2026.3).
- Redshift colour parameters are split between two value types and reject the
  wrong one with a `TypeError`. Verified in Cinema 4D 2026.3:
  `RSCAMERAOBJECT_BACKGROUND_COLOR` requires `c4d.Vector4d(r, g, b, 1.0)`,
  while `REDSHIFT_OBJECT_MATTE_SHADOW_COLOR` requires plain `c4d.Vector`.
  Do not generalize either type to other RS colour parameters; when writing an
  unverified one, try the documented type and fall back to the other inside the
  same run, then record which one succeeded.
- Reading a `CUSTOMDATATYPE_RSFILE` path sub-channel (for example the Dome
  Light HDRI) returns a `file:///C:/...` URI even when a plain Windows path was
  just written. Verify by normalizing the URI back to a filesystem path and
  asserting that file exists; never compare the raw strings for equality.
- `c4d.plugins.FilterPluginList(...)` returns a Python list in Cinema 4D 2026;
  iterate it directly instead of walking `GetNext()`.
- Continue to treat viewport drawing and editor-state behavior as GUI-only.
  Using the render BaseDraw to select a render camera does not prove viewport
  behavior.

## Headless Redshift render evidence

Two proven infinite-hang triggers (Cinema 4D 2026.3, isolated by one-line A/B
probes; the hang shows `Context: Busy:Render Waiting until idle` in the
Redshift log and near-zero CPU):

- Never insert a Redshift video post manually. Assigning
  `rd[c4d.RDATA_RENDERENGINE] = 1036219` already creates it; an extra
  `rd.InsertVideoPost(c4d.documents.BaseVideoPost(1036219))` produces two
  Redshift video posts and every subsequent `RenderDocument` hangs forever.
  After switching, walk `rd.GetFirstVideoPost()` and assert exactly one
  Redshift entry.
- Never write `RDATA_FILMASPECT` before a headless render. `RDATA_XRES` and
  `RDATA_YRES` are sufficient; an explicit film aspect hangs the render the
  same way.

Canonical proven render call (all successful runs use exactly this shape):

```python
rd = doc.GetActiveRenderData()          # active data, not a clone
rdata = rd.GetDataInstance()
rdata[c4d.RDATA_XRES] = float(width)
rdata[c4d.RDATA_YRES] = float(height)
rdata[c4d.RDATA_SAVEIMAGE] = False      # save the bitmap yourself
bmp = c4d.bitmaps.MultipassBitmap(int(width), int(height), c4d.COLORMODE_RGB)
res = c4d.documents.RenderDocument(
    doc, rdata, bmp,
    c4d.RENDERFLAGS_EXTERNAL | c4d.RENDERFLAGS_NODOCUMENTCLONE)
```

From 2026.2 onward prefer the documented base flag and let Cinema allocate the
bitmap; both are absent in earlier runtimes, so guard with `getattr` when the
script must also run on 2026.0/2026.1:

```python
bmp = c4d.bitmaps.AllocateRenderBitmap(rdata)   # matches the render settings
res = c4d.documents.RenderDocument(
    doc, rdata, bmp, c4d.RENDERFLAGS_AUTO_SETUP, prog=OnProgress, wprog=OnWrite)
```

- `RENDERFLAGS_AUTO_SETUP` (16385) is an alias for
  `EXTERNAL | OCIO_RAW_RENDERING` and is the documented base for programmatic
  rendering.
- `RENDERFLAGS_NODOCUMENTCLONE` is a performance shortcut that Maxon documents
  as *not recommended for final renderings*. Keep it for fast iteration probes;
  drop it for anything delivered.
- Read the resolution as `RDATA_XRES_VIRTUAL or RDATA_XRES` when honoring the
  user's render settings — the virtual fields win when they are set.
- Pass a progress hook. It is the only thing that distinguishes "slow" from
  "hung" inside a blocking `RenderDocument`, and it costs three lines:

  ```python
  def OnProgress(percent: float, progressType: int) -> bool:
      print(f"[render] {progressType} {percent * 100:.0f}%", flush=True)
      return True
  ```

  `RENDERPROGRESSTYPE_BEFORERENDERING` / `DURINGRENDERING` / `AFTERRENDERING` /
  `CANCELLED` cover every engine; the GI and AO stages are Standard/Physical
  only. Output only reaches the log after the call returns, but a truncated log
  then still shows the last stage reached.

Because a hang is indistinguishable from a slow render without evidence, use
staged timeouts: give the first launch of any new build script a short runner
budget (90-150 s) that only has to reach its first low-res mask `render done`
print, and grant the full multi-minute budget only to a script whose first
render is already proven. Print a flushed stage marker before and after every
render so a stalled log is diagnostic. A hung run wastes its whole timeout;
short first budgets turn a 15-minute loss into a 2-minute one.

- `RenderDocument` with `RENDERFLAGS_EXTERNAL` fills the alpha channel with
  `255` everywhere even when `RDATA_ALPHACHANNEL` is enabled (verified in
  Cinema 4D 2026.3). Any alpha-based measurement silently reports full-frame
  coverage; measure silhouettes with the chroma-key procedure defined in
  `build-cinema4d-projects/references/camera-framing.md`.
- The same external path ignores `RDATA_SAVEIMAGE`/`RDATA_PATH` (logs
  `CRITICAL: Stop [ge_container.h]`, writes no file, still returns
  `RENDERRESULT_OK`). Save the rendered `MultipassBitmap` yourself and assert
  the file exists.

### OCIO colour of the returned buffer

Re-verified in Cinema 4D **2026.3.3** with an A/B/C probe (OCIO document,
Standard engine pinned on both the render data and the settings clone so the
`flags=0` reference renders the same image; max 8-bit channel deviation over a
sampled grid).

Whether the returned buffer is raw render space is **not** a property of
`RENDERFLAGS_EXTERNAL`. It is controlled by
`RDATA_BAKE_OCIO_VIEW_TRANSFORM_RENDER` in the settings container you pass:

| Flags | Deviation vs `flags=0` |
| --- | --- |
| `EXTERNAL` (settings' `BAKE_..._RENDER` False) | **1** — already view-transformed |
| `AUTO_SETUP` (= `EXTERNAL \| OCIO_RAW_RENDERING`) | **63** — raw render space |
| `AUTO_SETUP \| OCIO_BAKE_RENDERING` | **1** — round-trips back |

So `RENDERFLAGS_OCIO_BAKE_RENDERING` is **not** a no-op: it bakes the view
transform and lands within one 8-bit step of the `flags=0` target. The earlier
"no-op" reading comes from pairing it with bare `EXTERNAL`; with the settings
already producing a view-transformed buffer there is nothing left to bake, and
the flag changes nothing. It only does work when something put the buffer into
raw render space first — which is exactly what `OCIO_RAW_RENDERING` (and
therefore `AUTO_SETUP`) does.

Practical rules:

- To get a saveable, Picture-Viewer-looking image in one call, use
  `RENDERFLAGS_AUTO_SETUP | RENDERFLAGS_OCIO_BAKE_RENDERING`.
- To keep render-space data for pixel work, use `RENDERFLAGS_AUTO_SETUP` alone,
  and bake at the end.
- Never assume; **read** `settings.GetBool(c4d.RDATA_BAKE_OCIO_VIEW_TRANSFORM_RENDER)`
  and log it next to the flags. The same flag set produces different colour on
  two documents whose render settings differ.
- `c4d.documents.BakeOcioViewToBitmap(bmp, settings, savebit)` exists but
  returned `None` ("no baking necessary") for every `savebit` tried against an
  `AUTO_SETUP` result in this probe, while the flag on the same render did bake.
  Do not treat the manual call as equivalent — if you use it, assert it returned
  a bitmap instead of falling back with `baked or bmp`, or the conversion
  silently does not happen.
- Applying the colour converter to a buffer that is already view-transformed
  double-transforms it (deviation 58). The converter path remains valid only for
  a confirmed raw render-space buffer:
  `doc.GetColorConverter().TransformColors(rows,
  c4d.COLORSPACETRANSFORMATION_OCIO_RENDERING_TO_VIEW)`.
  `..._RENDERING_TO_DISPLAY` overshoots (deviation 85, extra display encoding).
  Full-HD row-batched conversion costs ~0.5 s. The converter produces correct
  ACES numbers headlessly even when `DOCUMENT_OCIO_VIEW_TRANSFORM_NAME` reads
  `None` in c4dpy.
- `AUTO_SETUP`, `OCIO_RAW_RENDERING`, `OCIO_BAKE_RENDERING` and
  `AllocateRenderBitmap` do not exist before 2026.2.

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
- Print `c4d.GetC4DVersion()` first, so the log identifies its own runtime.

## Use `mxutils` in probes

`mxutils` ships with Cinema 4D and is pure Python. It removes most of the
boilerplate a probe would otherwise hand-roll.

```python
import mxutils

# Assert and unwrap in one step; raises with the inferred symbol name.
doc = mxutils.CheckType(c4d.documents.GetActiveDocument())
mats = mxutils.CheckIterable(doc.GetMaterials(), tElement=c4d.BaseMaterial, minCount=1)

# Iterative hierarchy walk; safe and fast on large trees.
for node in mxutils.IterateTree(doc.GetFirstObject(), yieldSiblings=True):
    ...
```

- `CheckType` / `CheckIterable` beat bare `assert x is not None`: the failure
  message names the symbol and the expected type.
- On failure, dump structure instead of guessing: `GetSceneGraphString(node)`,
  `GetParameterTreeString(node)`, `GetContainerTreeString(bc)`. These turn an
  opaque "wrong value" into a diffable log.
- `SymbolTranslationCache` / `g_c4d_symbol_translation_cache` maps an integer
  back to its `c4d` symbol name — use it when reporting an unexpected id.
- Build fixtures deterministically with `mxutils.Random(seed=...)` and
  `mxutils.SceneFaker`, which generates objects, materials, tags, layers, render
  data and tracks. A seeded faker gives a reproducible scene without shipping a
  `.c4d` file.
- `IterateTree` is iterative (fast, no recursion limit); `RecurseTree` is
  marginally faster only below ~100 nodes. `RecurseGraph` also yields
  non-hierarchical relations such as caches.
- `@mxutils.TIMEIT(...)` for timing, `@mxutils.SET_STATUS(...)` for status-bar
  output in the host (a no-op worth avoiding in pure headless probes).

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
- A render/save return code does not prove a usable image. When the calling
  scene workflow defines signal, framing, or clipping gates, print the success
  marker only after those image assertions pass.

## Keep this skill learning

Store only shared headless runtime, process, import, ownership, and evidence
rules here. Put plugin architecture/UI knowledge in `develop-cinema4d-tools` and
scene-production knowledge in `build-cinema4d-projects`.

When an exact-version log and a successful correction prove a failure is
universal, add the narrow runtime/API/process rule here before completing the
task. Add a deterministic regression check when practical, validate the skill,
follow repository synchronization rules, and report the learned rule. Do not
store speculative or project-specific workarounds.
