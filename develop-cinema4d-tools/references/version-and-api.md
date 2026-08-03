# Version and API Compatibility

## Target version

- Identify the exact Cinema 4D version before implementation or testing.
- Match `c4dpy.exe`, `Cinema 4D.exe`, plugin directory, scene version, and API
  assumptions.
- Do not silently test a 2026.1 plugin with 2026.3 and claim compatibility.

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
