# Driver contract

The supervisor copies the trusted driver into the disposable test root. The bootstrap imports that copy on Cinema's main thread and calls:

```python
def run(context):
    ...
```

`context` exposes:

- `run_id`: unique identifier shared by every evidence record.
- `scene_readonly`: copied configuration value for an optional source scene. Never save it.
- `plugin_paths`: copied plugin input paths under the disposable root.
- `artifacts_dir`: writable test-owned output directory.
- `emit(event, **payload)`: append a schema-versioned JSONL event.
- `check(name, condition, details=None)`: emit a check; raise on false.
- `artifact(name, value, media_type=None)`: write bytes, text, or JSON below `artifacts_dir`, then emit its digest and size.
- `add_cleanup(callback)`: register cleanup in reverse order. Cleanup runs before the one final record.

Rules:

1. Keep all Cinema API and UI work inside `run(context)`; it runs from a retained asynchronous `GeDialog.Timer` after `C4DPL_PROGRAM_STARTED`.
2. Use asynchronous dialogs. Never block on user input.
3. Register cleanup immediately after creating a document, dialog, temporary object, or external resource.
4. Express every semantic acceptance condition with a uniquely named `context.check`.
5. Write only inside `context.artifacts_dir`. Do not modify source plugins, driver, or `scene_readonly`.
6. Return an optional JSON-serializable summary. Do not write a `final` event; the bootstrap owns it.

The neutral template demonstrates a temporary document and a small `GeDialog`. Copy it rather than importing it in place.
