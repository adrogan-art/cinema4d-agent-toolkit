# Tool and Plugin Architecture

## Contents

1. Boundaries
2. Plugin structure
3. State and ownership
4. Registration
5. Change strategy

## Boundaries

Prefer four layers when the tool is substantial:

1. Pure domain logic: calculations, parsing, state transitions, validation.
2. Cinema adapter: `c4d` objects, documents, selections, undo, messages.
3. UI/controller: `GeDialog`, TreeView, commands, user interaction.
4. Registration/bootstrap: IDs, icons, resources, plugin classes.

Small scripts may combine layers, but keep pure functions independently
callable. Avoid importing the GUI merely to test math or scene rules.

## Plugin structure

Follow the existing repository first. A useful default is:

```text
plugin/
├── plugin.pyp
├── core.py
├── cinema_adapter.py
├── ui.py
├── res/
│   ├── c4d_symbols.h
│   ├── description/
│   └── strings_us/
└── tests/
```

- Keep `.pyp` registration thin.
- Do not perform document mutation, dialog opening, network access, or expensive
  discovery at module import.
- Resolve resources relative to the plugin module, not the current directory.
- Keep import paths deterministic when the plugin is loaded from a copied test
  root.

## State and ownership

- Distinguish document state, plugin preferences, transient dialog state, and
  derived caches.
- Use unique, versioned preference keys when persistence format can evolve.
- Do not retain borrowed C4D wrappers beyond their owner's lifetime.
- `GeClipMap.GetBitmap()` is borrowed. When initialized from an owning
  `BaseBitmap`, retain and return the owning bitmap rather than caching the
  borrowed wrapper.
- Use a fresh `BaseDocument` in isolated tests to avoid state bleed.
- Pair document mutations with the appropriate undo operations when the user
  expects undoable behavior.

## Registration

- Preserve assigned plugin IDs. Never invent a production ID by copying another
  plugin.
- Keep command, object, tag, and message plugin responsibilities separate.
- Registration success proves only that Cinema accepted the registration call.
- `plugins.FindPlugin()` returns plugin metadata/a `BasePlugin`, not the original
  Python `CommandData` instance.

## Change strategy

- Reproduce the bug with the smallest fixture before a broad refactor.
- Patch the narrowest responsible layer.
- Add a regression test at the lowest valid tier.
- Treat serialized scene data, preferences, IDs, and resource symbols as
  compatibility surfaces.
