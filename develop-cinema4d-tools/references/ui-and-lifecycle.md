# UI and Host Lifecycle

Use this reference for design decisions. Use `cinema4d-gui-testing` for the
actual disposable-host procedure and safety contract.

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
