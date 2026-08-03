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
