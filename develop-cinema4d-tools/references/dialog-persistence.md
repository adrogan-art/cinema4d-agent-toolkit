# Dialog Persistence

How a `GeDialog` keeps its layout and values across three different boundaries.
Read this only when a dialog must remember something.

## Pick the cheapest boundary that satisfies the requirement

| Boundary | What is needed |
| --- | --- |
| Open → close → reopen in one session | `BFM_LAYOUT_GETDATA` / `BFM_LAYOUT_SETDATA` |
| Layout switch | the same two messages |
| Cinema 4D restart | the above **plus** custom serialization to disk |

Cinema 4D's own dialogs rely on layout files, but a third-party plugin usually
is not part of the user's layout file, so restart persistence has to be built.
Do not implement the disk tier unless restart persistence is actually required —
it roughly doubles the size of the dialog code.

## Layout messages

```python
def Message(self, msg, result):
    mid = msg.GetId()

    if mid == c4d.BFM_LAYOUT_GETDATA:
        # Cinema asks us to write our state into `result`.
        result.SetId(MyCommand.ID_PLUGIN)   # MANDATORY
        return self.SaveValues(result)

    if mid == c4d.BFM_LAYOUT_SETDATA:
        # The payload is nested one level deep under the message id itself.
        return self.LoadValues(msg.GetContainer(c4d.BFM_LAYOUT_SETDATA))

    return c4d.gui.GeDialog.Message(self, msg, result)
```

- `result.SetId(...)` is not optional. The container's default id is `-1` and
  Cinema silently discards data written under it — the dialog then looks like it
  simply never persisted anything.
- `BFM_LAYOUT_SETDATA` arrives **after** `CreateLayout()`, never before. Any
  state that must exist while the layout is being built (group weights in
  particular) has to be loaded by other means on the first open.

## Resizable groups and their weights

```python
self.GroupBegin(self.ID_GRP_MAIN, flags, 2, 2, "", c4d.BFV_GRIDGROUP_ALLOW_WEIGHTS)
...                                     # sub-groups A B / C D
self.GroupWeightsLoad(self.ID_GRP_MAIN, self._weights)
self.GroupEnd()
```

- `BFV_GRIDGROUP_ALLOW_WEIGHTS` on a grid group gives the user drag splitters
  between the child groups.
- `GroupWeightsLoad()` must be called **before** the group is closed with
  `GroupEnd()`, unless the dialog lives in a layout file.
- Save with `GroupWeightsSave(groupId)`, which returns a `BaseContainer`.
- React to user resizing via `BFM_WEIGHTS_CHANGED`; the changed group id is
  `msg.GetInt32(c4d.BFM_WEIGHTS_CHANGED)`. Only handle it when something in the
  UI depends on the weights — persistence itself does not need it.
- The values `GroupWeightsSave()` returns are normalized and generally are not
  the numbers that were originally set.

## Restart persistence via HyperFile

```python
hf = c4d.storage.HyperFile()
path = os.path.join(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS), "myplugin.state")
if not hf.Open(ident=MyCommand.ID_PLUGIN, filename=path,
               mode=c4d.FILEOPEN_WRITE, error=c4d.FILEDIALOG_NONE):
    return False
try:
    hf.WriteContainer(container)
finally:
    hf.Close()          # always; an unclosed HyperFile keeps the file locked
```

- The `ident` used on write must match the one used on read.
- HyperFile is positional: values come back in exactly the order written, so any
  change to the layout of what you write is a format break. Version the payload
  (write an int version first) or store a `BaseContainer` whose ids are stable.
- Write on `AskClose` (return `False` afterwards so the close proceeds), and
  load in `CreateLayout` when no layout data has arrived yet.
- Put the file under `C4D_PATH_PREFS`, not next to the plugin — the plugin
  directory may be read-only and is shared between users.
