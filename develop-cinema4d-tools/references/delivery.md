# Tool Delivery Contract

Before handoff, verify:

- target Cinema 4D version is stated;
- source files and resources are in the expected plugin/script structure;
- plugin IDs and description symbols are stable and non-conflicting;
- no debug files, probe objects, caches, or temporary test artifacts ship;
- pure and applicable c4dpy tests pass;
- GUI behavior is either verified through the approved harness or clearly marked
  for manual verification;
- installation changed only the requested target location/version;
- settings or serialized-data migrations are documented and tested;
- known limitations and reproduction steps for any remaining issue are concise.

Report the actual evidence. Do not call a tool production-ready merely because it
imports, registers, or opens a window.

## Distribution and encryption

- Plugin IDs come from the Plugin ID generator on developers.maxon.net. An ID
  collision means one of the two plugins silently fails to load at startup.
- `.pypv` is an encrypted plugin module. Encryption is available both from
  *Extensions ▸ Tools ▸ Source Protector* and headlessly:
  `c4dpy dummy.py -g_encryptPypFile=C:\path\myplugin.pyp`.
- Encryption is not protection. Python source must reach the interpreter as
  plain text, so Cinema's own encryption, `pyarmor`, and `nuitka` are all
  defeatable by a mildly motivated attacker. Say so plainly to anyone who asks
  for "protected" Python; do not let a licensing scheme imply guarantees it
  cannot make.

## Licensing checks

Maxon's position for Python plugins is *keep honest users honest*. Within that
limit, `c4d.ExportLicenses()` returns the data worth binding to:

```python
data = c4d.ExportLicenses()
# userid       stable per Maxon Account
# systemid     stable per machine
# currentproduct  e.g. "net.maxon.license.app.cinema4d-release~commercial"
# accountlicenses dict of product id -> seat count
```

- Product ids follow `net.maxon.license.app.{product}[~{modifier}][-floating]`.
  Modifiers are `~commercial`, `~education`, `~student`, `~trial`,
  `~commandline`; `~beta` does not exist. Detect classroom/student installs with
  a regex on `currentproduct` when features must be limited.
- A user may have no dedicated Cinema 4D license and still run it legitimately
  through a bundle such as Maxon One — check `accountlicenses`, not only
  `currentproduct`, before refusing to run.
- Node-locking is a hash over `userid` + `systemid` + your own salt. Validate by
  regenerating and comparing, not by storing the plaintext key.
- `PluginMessage` with `C4DPL_STARTACTIVITY` is the right place for startup
  validation, including a call to an online service.
- The list of Maxon products changes; do not hard-code an exhaustive list.
