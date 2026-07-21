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
