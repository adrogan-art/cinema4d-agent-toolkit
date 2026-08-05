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

Follow the existing repository first. The structure Cinema 4D itself expects is:

```text
plugin/
├── plugin.pyp                        # or .pypv when encrypted
├── core.py
├── cinema_adapter.py
├── ui.py
├── res/
│   ├── c4d_symbols.h                 # non-description (dialog) IDs
│   ├── description/
│   │   ├── myobject.h                # description IDs
│   │   └── myobject.res              # Attribute Manager layout
│   ├── dialogs/
│   │   └── mydialog.res              # GeDialog layout
│   ├── strings_en-US/                # mandatory; the fallback language
│   │   ├── c4d_strings.str
│   │   ├── description/myobject.str
│   │   └── dialogs/mydialog.str
│   └── strings_de-DE/                # one folder per additional language
└── tests/
```

- `res/` and `res/c4d_symbols.h` must exist even when empty. A missing or broken
  resource folder produces `Could not find required '__res__'.` in the console at
  startup and the plugin does not load.
- String folders are `strings_en-US`, not the pre-R20 `strings_us`. Cinema 4D
  2026.3 ships no `strings_us` folder; a resource placed there is ignored
  silently and every label renders blank while the layout still loads.
- Keep `.pyp` registration thin.
- Do not perform document mutation, dialog opening, network access, or expensive
  discovery at module import.
- Resolve resources relative to the plugin module, not the current directory.
- Keep import paths deterministic when the plugin is loaded from a copied test
  root.

## Local modules and symbols

A plugin's own directory is **not** on the Python search path. Use
`mxutils.LocalImportPath`, which adds the path, imports, and cleans up:

```python
from mxutils import LocalImportPath

IS_DEBUG: bool = False

# Exposes the directory containing this .pyp as a search path for the block.
with LocalImportPath(__file__, autoReload=IS_DEBUG):
    import myplg_libs.myplg_urllib3 as urllib3
```

- `autoReload=True` re-imports the package's dependency tree on every execution
  of the block, so *Reload Python Plugins* picks up changes in local modules.
  Turn it off in release builds. Modules with order-sensitive reloads must still
  be reloaded manually.
- `sys.modules` keys are global across every plugin in the installation. Two
  plugins shipping a module named `urllib3` will fight over one entry and one of
  them stops working. Prefix everything you bundle (`myplg_urllib3`,
  `myplg_math`), never ship a package under its common name.
- Prefer installing shared libraries globally over bundling them.

Do not retype resource IDs in Python. `mxutils.ImportSymbols` parses the `.h`
and `.res` files so the symbol table has exactly one source of truth:

```python
import mxutils

# Into the caller's global scope ...
mxutils.ImportSymbols(os.path.join(os.path.dirname(__file__), "res"))
print(ID_MY_BUTTON)

# ... or into a dict when you want to keep the namespace clean.
symbols: dict[str, int] = mxutils.ImportSymbols(path, output=dict)
```

## State and ownership

- A `NodeData` subclass is **not** the scene element. Cinema 4D pairs an
  invisible `ObjectData`/`TagData`/`ShaderData` instance with a visible
  `BaseObject`/`BaseTag`/`BaseShader` that holds the user's parameters and acts
  as the controller. When the user edits a parameter, the old base node is
  pushed onto the undo stack and **replaced**. Store per-element state in the
  node's container, never as an attribute of the `*Data` instance.
- Cinema calls `NodeData.Init()` after the constructor and `NodeData.Free()`
  before the destructor. Allocate and release element-scoped resources there,
  not in `__init__`/`__del__`.
- Registration functions that take an *instance* (`CommandData`, `MessageData`)
  keep that one object for the whole session; those that take a *class*
  (`ObjectData`, `TagData`, …) allocate one per node.
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
  plugin. Production IDs come from the Plugin ID generator on
  developers.maxon.net and from nowhere else — when two plugins claim the same
  ID, Cinema 4D loads only one of them at startup and reports nothing useful.
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
