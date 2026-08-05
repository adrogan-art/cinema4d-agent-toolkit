# UI and Host Lifecycle

Use this reference for design decisions. Use `cinema4d-gui-testing` for the
actual disposable-host procedure and safety contract. For storing dialog layout
and values across open/close and restart boundaries, read
[dialog-persistence.md](dialog-persistence.md).

## Command plugin hosting a dialog

The shape Maxon's own examples use. A `CommandData` owns one dialog instance and
toggles it; it does not open a second window on every invocation.

```python
class MyCommand(c4d.plugins.CommandData):
    ID_PLUGIN: int = 1000001          # from developers.maxon.net
    REF_DIALOG: "MyDialog | None" = None

    @property
    def Dialog(self) -> "MyDialog":
        if self.REF_DIALOG is None:
            self.REF_DIALOG = MyDialog()
        return self.REF_DIALOG

    def Execute(self, doc):
        # Fold an already open dialog instead of reopening it.
        if self.Dialog.IsOpen() and not self.Dialog.GetFolding():
            self.Dialog.SetFolding(True)
        else:
            self.Dialog.Open(c4d.DLG_TYPE_ASYNC, self.ID_PLUGIN,
                             defaultw=300, defaulth=300)
        return True

    def RestoreLayout(self, secret):
        # Without this the dialog does not come back after a layout switch.
        return self.Dialog.Restore(self.ID_PLUGIN, secret)

    def GetState(self, doc):
        result = c4d.CMD_ENABLED
        if self.Dialog.IsOpen() and not self.Dialog.GetFolding():
            result |= c4d.CMD_VALUE      # draws the command as active
        return result
```

- Register with an icon; a built-in one avoids shipping a bitmap:
  `c4d.bitmaps.InitResourceBitmap(c4d.RESOURCEIMAGE_MOVE)` or any command ID.
- `DLG_TYPE_ASYNC` is the normal choice. Modal dialogs block the host.
- Passing the plugin ID to `Open` is what makes `RestoreLayout` and layout
  persistence work at all.

## Dialog structure

- Keep model/state independent from gadgets.
- Build layout in `CreateLayout`, initialize values in `InitValues`, and handle
  user actions in `Command`.
- Keep timer callbacks non-structural. Update values and previews in place.
- Do not call `LayoutFlushGroup()` periodically around active edit fields;
  recreating gadgets destroys focus.
- Rebuild dynamic rows only after explicit structural changes or a document
  switch.
- A `CommandData` that caches one `GeDialog` instance reruns `CreateLayout` on
  every reopen while stored custom GUI references (FontChooser, BitmapButton,
  and similar `AddCustomGui` results) still point at gadgets of the destroyed
  window. Calling any method on such a dead native gadget crashes Cinema with
  an access violation. Clear those references in `DestroyWindow` and again at
  the top of `CreateLayout`; keep only model state across reopens.

## Edit-text round trips

`AddMultiLineEditText` does not return the exact string it was given. Verified in
Cinema 4D 2026.3.3: text written as `"a\nb\n"` reads back as `"a\r\nb"` — line
endings become `\r\n` and the trailing newline is dropped.

Never compare gadget text with stored text directly to decide whether the user
edited something. Normalize both sides first (unify `\r\n` and `\r` to `\n`, then
strip leading and trailing newlines) and store the normalized form, so the next
round trip compares equal. Without this, every read of the gadget looks like an
edit, and dirty-state, versioning, or autosave logic fires on unchanged content.

Keep that comparison in pure code so it is testable without the host; the host
only supplies the raw string.

## TreeView

- For flat Python-backed lists, prefer `LV_TREE` for the main text column.
- When using `LV_USER` or `LV_USERTREE`, implement a positive
  `GetLineHeight()` based on the current font.
- Give custom columns explicit minimum widths.
- Use `TREEVIEW_FIXED_LAYOUT` when row heights are uniform.
- Test selection, double-click, keyboard navigation, scrolling, and scaling in
  the real host when those behaviors matter.

## Commands and plugin lifecycle

- Avoid calling `c4d.CallCommand()` merely to open a dialog for inspection from
  a bootstrap timer; global dispatch can re-enter the host event path.
- For dialog-focused tests, load the copied `.pyp`, instantiate its dialog, and
  open it asynchronously inside the approved GUI driver.
- Use command dispatch only when dispatch itself is under test, with a
  multi-phase event-loop-aware driver.
- Distinguish registration failure, driver control-flow failure, event-loop
  failure, and product failure from the evidence.

## Documents and events

- Expect document switches, closed documents, invalid links, and object deletion.
- Avoid holding stale document/object references across callbacks without
  validation.
- Prevent feedback loops between document messages, timers, and UI updates.
- Define which callback owns a state transition; do not let several callbacks
  independently rebuild the same state.

### Tracking scene state without a feedback loop

A dialog that watches the scene listens for `EVMSG_CHANGE` in `CoreMessage`. If
it also calls `EventAdd()` after writing to the scene, it re-triggers itself.
Gate on an identity hash of what you track and return early when nothing moved:

```python
def CoreMessage(self, mid, msg):
    if mid == c4d.EVMSG_CHANGE:
        self.GatherData()
    return super().CoreMessage(mid, msg)

def GatherData(self) -> bool:
    tracked = [t for t in FindInterestingTags(doc)]
    # hash(node) is the node's GeMarker UUID: stable for the lifetime of the
    # element and comparable across wrappers.
    newHash: set[int] = {hash(t) for t in tracked}
    if newHash == self._selectionHash and not self._isFinalized:
        return True                      # our own EventAdd came back; ignore it
    self._selectionHash = newHash
    ...
```

- `hash(node)` is the reliable identity for a `BaseTag` (which has no
  `GetGUID()`) as well as for objects. Prefer it over name or index comparison.
- Validate before touching anything you stored: `node.IsAlive()`, and
  `node.GetDocument() is not None` when you intend to create undos.
- Guard scene mutation explicitly, even in code you believe is main-thread only:

  ```python
  if not c4d.threading.GeIsMainThreadAndNoDrawThread():
      raise RuntimeError("scene mutation from a non-main thread")
  ```

- After writing tag data, mark both the tag and its host object dirty, or the
  viewport keeps the old cache:
  `tag.SetDirty(c4d.DIRTYFLAGS_DATA)` and `obj.SetDirty(c4d.DIRTYFLAGS_DATA)`.

### Tool finalization (rolling edits on a snapshot)

For a tool that gives live viewport feedback while the user drags a control,
each edit must derive from a snapshot, not from the previous edit — otherwise
edits compound and dragging back does not return to the original.

1. On gaining focus or on a selection change, take the snapshot: copy the source
   data out of the scene and store it beside the node references.
2. On every change, recompute from the snapshot and write the result to the
   scene without creating undos. Call `EventAdd()` once at the end.
3. On **Apply**, do the finalize pass: reset the scene to the snapshot without
   an event, `doc.StartUndo()`, `doc.AddUndo(c4d.UNDOTYPE_CHANGE, node)` per
   touched node, write the final values, `doc.EndUndo()`. Then re-snapshot so
   the new state becomes the baseline.
4. On `BFM_LOSTFOCUS`, in `AskClose`, and before locking onto a new selection,
   roll back to the snapshot if the user never finalized.

The reset-then-undo-then-write ordering matters: `AddUndo` records the state at
the moment it is called, so the node must be back at the snapshot value first or
the undo step restores an intermediate preview instead of the original.

## Resource-defined dialogs and menus

`CreateLayout` can load a markup file instead of building gadgets by hand. This
is the officially recommended form because it is the only one that gets
localization for free:

```python
def CreateLayout(self):
    return self.LoadDialogResource(MY_DIALOG)   # res/dialogs/my_dialog.res
```

- Labels come from `res/strings_<lang>/dialogs/my_dialog.str`; look up other
  strings with `c4d.plugins.GeLoadString(ID)`.
- A programmatic `CreateLayout` loses localization entirely unless every string
  goes through `GeLoadString` by hand.
- Menus cannot be defined in resources. Build them in `CreateLayout` with
  `MenuFlushAll()` / `MenuSubBegin()` / `MenuAddString()` / `MenuSubEnd()` /
  `MenuFinished()`, and wrap the labels in `GeLoadString` for localization.

## Boot and shutdown hooks

A module-level `PluginMessage(id, data)` in the `.pyp` receives application
lifecycle events. The ones that matter:

| Message | Use it for |
| --- | --- |
| `C4DPL_STARTACTIVITY` | Work that must run after **all** plugins registered — license validation, cross-plugin discovery |
| `C4DPL_ENDACTIVITY` | Close dialogs, stop threads, drop temporary buffers, before any shutdown begins |
| `C4DPL_SHUTDOWNTHREADS` | Last point at which threads may still exist; start no new ones after |
| `C4DPL_ENDPROGRAM` | Cinema is about to quit; `data['cancel'] = True` aborts the quit |
| `C4DPL_BUILDMENU` | Add entries to the main menu via `gui.GetMenuResource("M_EDITOR")`; outside this message call `gui.UpdateMenus()` |
| `C4DPL_RELOADPYTHONPLUGINS` | *Reload Python Plugins* was invoked — `importlib.reload()` local modules and close sockets/files, since only the `.pyp` itself is recompiled |
| `C4DPL_COMMANDLINEARGS` | Read `sys.argv`; arguments consumed by Cinema modules are already removed |

Return `True` when the message was handled, `False` otherwise.
