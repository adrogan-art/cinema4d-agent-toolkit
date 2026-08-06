# Version and API Compatibility

## Target version

- Identify the exact Cinema 4D version before implementation or testing.
- Match `c4dpy.exe`, `Cinema 4D.exe`, plugin directory, scene version, and API
  assumptions.
- Do not silently test a 2026.1 plugin with 2026.3 and claim compatibility.
- The install directory name is not the version. `Maxon Cinema 4D 2026` can be
  2026.1.0 while `Maxon Cinema 4D 2026.3.3` sits beside it. Read the executable's
  file version, and log `c4d.GetC4DVersion()` from inside the run.
- Maxon publishes an *SDK Change Notes* page per release listing the API delta
  since the previous one. Between 2026.0.0 and 2026.3.0 that delta is empty —
  so a symbol missing in 2026.3 was very likely never there, whereas anything
  introduced in 2026.2 (`RENDERFLAGS_AUTO_SETUP`, `c4d.bitmaps.AllocateRenderBitmap`)
  is absent from 2026.0 and 2026.1.

## Python runtime

| Cinema 4D | Python core | Library search path | Env var |
| --- | --- | --- | --- |
| R20–R21 | 2.7 | `%APPDATA%/MAXON/python27/libs` | `PYTHONPATH` / `C4DPYTHONPATH` |
| R23 | 3.7 | `%APPDATA%/MAXON/python37/libs` | `C4DPYTHONPATH37` |
| S24–2023.1 | 3.9 | `%APPDATA%/MAXON/python39/libs` | `C4DPYTHONPATH39` |
| 2023.2 | 3.10 | `%APPDATA%/MAXON/python310/libs` | `C4DPYTHONPATH310` |
| 2024.0+ | 3.11.4 | `%APPDATA%/MAXON/python311/libs` | `C4DPYTHONPATH311` |

- The interpreter is derived from CPython but is not identical to it, and a
  system CPython cannot be substituted. Pure-Python packages usually work;
  C-extension packages (numpy among them) may fail or work only partially.
  Maxon supports none of them.
- Multiple search paths are separated by `;` on Windows and `:` on macOS.
- Per-app preference directories share a hash and differ by suffix: none for
  Cinema 4D, `_p` for c4dpy, `_x` for commandline, `_c`/`_s` for Team Render
  client/server, `_w` for Cineware. They exist only after that app has run once.
- A `python_init.py` placed at the root of either search path runs before plugin
  registration during boot, with `doc`, `op`, and `tp` injected. Use
  `PluginMessage` for per-plugin boot work instead; reserve `python_init.py` for
  environment-level setup.

## Threading contract

Cinema 4D threads its whole execution and drawing pipeline. These run off the
main thread: `TagData.Execute`, `TagData.Draw`, `ObjectData.GetVirtualObjects`,
`ObjectData.Execute`, `ObjectData.Draw`, `ObjectData.DrawShadow`, every other
`Draw`/`Execute`, and all embedded scripting elements (Python generator, tag,
effector, field).

Inside them it is **forbidden** to:

- change document structure — `InsertBefore`, `InsertAfter`, `InsertUnder`,
  `InsertUnderLast`, `Remove`. Doing so while an expression evaluates crashes
  the application, it does not merely misbehave;
- call `EventAdd()`;
- change materials;
- create undos;
- call any `Draw()` function;
- perform GUI work of any kind — messages, dialogs, popups;
- do file I/O *during drawing* (during execution it is allowed).

Changing parameters of attached elements is tolerated but not recommended
outside tags. `GetVirtualObjects` may freely build and modify the hierarchy it
returns, because that hierarchy is not in the document yet.

Before mutating the active document from a `CommandData`, dialog, or timer, call
`c4d.StopAllThreads()` — including from the main thread, since other threads may
be reading the document. Assert the context where it matters:
`c4d.threading.GeIsMainThreadAndNoDrawThread()`.

## Localization

- Supported string folders: `strings_en-US` (mandatory fallback), `ar-AR`,
  `cs-CZ`, `de-DE`, `es-ES`, `fr-FR`, `it-IT`, `ja-JP`, `ko-KR`, `pl-PL`,
  `pt-BR`, `ru-RU`, `zh-CN`.
- Non-ASCII characters in `.str` files must be written as ASCII escape
  sequences, not as literal characters: `é` becomes `\u00e9`, `ä` becomes
  `\u00e4`, `品` becomes `\u54c1`. This affects German, French, Russian,
  Chinese, Japanese and Korean resources. Cinema ships no tool for the
  conversion, so it belongs in the build step, never in manual editing.
- Develop in one language, then copy the folder and translate.

## Symbols and parameters

- Prefer named `c4d` constants over numeric IDs.
- When a renderer/plugin object exposes version-specific parameters, verify the
  symbols with matching c4dpy and read values back after assignment.
- Use numeric IDs only when the API provides no stable symbol; centralize them,
  name the target version, and add a probe.
- Guard optional APIs with explicit capability checks and a meaningful fallback
  or failure.

### Verified in Cinema 4D 2026.3

- `Description.GetParameterI()` requires a `DescID`. A bare `DescLevel` raises
  `TypeError: expected DescID identifier`. In `GetDDescription()`, write
  `description.GetParameterI(c4d.DescID(c4d.DescLevel(param_id)), None)`.
- `c4d.BaseTag` has no `GetGUID()`; only `BaseObject` does. Compare two tag
  wrappers with `==`, which correctly matches two wrappers around the same live
  tag. A `GetGUID()`-based helper silently returns `False` for every tag when it
  swallows `AttributeError`, so status/ownership checks never fire.
  For sets, dict keys, and change detection use `hash(node)` — Maxon's own 2026
  examples rely on it, and it is the node's GeMarker UUID, so it is stable for
  the element's lifetime and equal across two wrappers of the same tag.
- A description `.res` for a Python plugin must **not** contain
  `NAME <containername>;`. `CONTAINER` resolves through the registered plugin
  description, but `NAME` resolves against the resource symbol table, which
  holds only built-in plugin types such as `Trsobject`. Cinema then refuses the
  file with `Symbol '<containername>' not found`. Omit the line; the title comes
  from the container-name entry in the string table.
- Object Manager traffic lights: `MODE_ON = 0`, `MODE_OFF = 1`,
  `MODE_UNDEF = 2`. `MODE_UNDEF` is the inherited default, not `0`.
- To grey out a description row, implement `NodeData.GetDEnabling()`. Cinema
  polls it per parameter and disables whatever returns `False`:

  ```python
  def GetDEnabling(self, node, descid, t_data, flags, itemdesc):
      return False if descid[0].id == SOME_PARAM else True
  ```

  Do **not** reach for `DESC_EDITABLE` (26): it does not grey out a row declared
  in a `.res` file, verified in the host by logging `GetDDescription()` — the
  flag was applied to the group and both checkboxes and nothing changed.
  `DESC_HIDE` works but removes the row and shifts the panel. Use
  `GetDDescription` only when the set of parameters itself must change, not to
  enable or disable existing ones.
- `GetDDescription()` is called with **partial** descriptions as well as full
  ones — single parameter queries in which your own IDs are absent entirely.
  Check every `GetParameterI()` result for `None`; code that assumes the full
  description silently does nothing on most calls.
- `TagData.Execute()` must not return `EXECUTIONRESULT_USERBREAK` on an internal
  error: that aborts the whole expression pass, so one faulty tag silently stops
  every other expression in the scene. Log the failure and return
  `EXECUTIONRESULT_OK`.
- `BaseObject.GetTag(type)` returns the **last** tag of that type, not the
  first. Many tags are unique per object anyway — inserting a second `Trsobject`
  or `Tphong` removes the first — but do not rely on `GetTag` for a stable
  choice; walk `GetFirstTag()`/`GetNext()` when the identity must not drift.
- Before inventing a mechanism for a plugin-UI behaviour, grep the user's other
  installed plugins for one that already does it. A working local example beats
  reasoning from the constant list: `DESC_EDITABLE` looks like the obvious
  answer for greying a row out and is simply the wrong call.
- `SCALE_V` on the outer `ID_TAGPROPERTIES` group distributes the free vertical
  space inside that group and opens a large empty gap above the first subgroup.
  Put `SCALE_V` only on the element that should actually grow, and place
  `HIDDEN` rows last.
- Redshift node materials are reachable from Python and behave predictably once
  two traps are known.
  `NodeMaterial.CreateDefaultGraph(maxon.Id("com.redshift3d.redshift4c4d.class.nodespace"))`
  builds the usual `standardmaterial` + `output` pair, and
  `maxon.GraphModelHelper.FindNodesByAssetId(graph, "com.redshift3d.redshift4c4d.nodes.core.standardmaterial", True, out)`
  finds the node. Then:
  - `GetInputs().FindChild()` takes a **`maxon.InternedId`**, not a `maxon.Id`.
    Passing `maxon.Id` raises
    `TypeError: unable to convert builtins.NativePyData to @net.maxon.datatype.internedid`.
  - A port written inside `with graph.BeginTransaction()` still reads back its
    **old** value until `transaction.Commit()`. Verifying before the commit
    reports every write as silently ignored, which sends you looking for a type
    mismatch that is not there.

  Port ids are the asset id plus a suffix (`…standardmaterial.emission_color`,
  `.emission_weight`, `.base_color`, `.refl_weight`). `SetPortValue` takes
  `maxon.Color` for colours and a plain `float` for scalars.
- Redshift lights an otherwise unlit scene from a default environment, and the
  standard material's `refl_weight` starts at **1**. A material meant to read as
  a flat colour therefore renders with a large specular hotspot until the
  reflection weight is taken to zero — including in a pixel-measuring test,
  where the hotspot is indistinguishable from the thing being measured.
- MoGraph Text has no `c4d` symbol; it is type **1019268**. `c4d.Omotext` does
  not exist in 2026.3. Its caps are built in the XY plane facing **-Z**, so an
  unrotated instance already presents its front to a camera looking down +Z.
  "Rotating it to face the camera" is the bug, not the fix: a 180° heading maps
  local +X onto camera -X and the string renders in reverse. A bounding-box
  assertion cannot see this — the box is symmetric — so test reading direction
  by comparing the camera-space X of two glyphs from `GetCache()`, which yields
  one child object per character.
- String tables belong in `res/strings_en-US/`, not the legacy
  `res/strings_us/`. Cinema 4D 2026.3 ships no `strings_us` folder anywhere; a
  resource placed there is ignored without any warning and every parameter
  renders with a blank label while the layout itself loads correctly. Confirm
  the folder naming against a shipped plugin before assuming the old form.

## Compatibility changes

- Treat plugin IDs, description symbols, resource filenames, preference keys,
  serialized containers, and scene data as stable interfaces.
- Add migrations for persisted data; do not silently reinterpret old values.
- Keep version branches narrow and documented.
- Test both the supported path and the intentional unsupported-version failure.

## Documentation and evidence

- Prefer installed SDK stubs, shipped examples, and executable probes over
  memory when exact API behavior matters.
- Record the verified version alongside unusual constants or lifecycle rules.
- Reverify general rules when upgrading the target Cinema version.
