# Evidence protocol

Evidence is newline-delimited UTF-8 JSON, flushed after every record. Every record contains:

- `schema_version` (currently `1`)
- one supervisor-generated `run_id`
- continuous `seq` starting at `1`
- `event`
- `monotonic_ns`

The bootstrap emits one `program_started`, driver events/checks, one `cleanup_complete`, and exactly one last `final` record.

The supervisor exits zero only when all of these hold:

- evidence is complete JSONL with a trailing newline;
- every record has the expected schema, run id, and sequence;
- exactly one `program_started`, `cleanup_complete`, and `final` exist;
- `final` is last and has `ok: true`;
- every `check` has `ok: true`;
- no record contains a non-empty `error` or `traceback`;
- Cinema did not crash, exit early, or exceed the timeout;
- all original driver/plugin inputs and the optional scene have unchanged SHA-256, size, and nanosecond mtime.

Missing, stale, partial, malformed, duplicated, or contradictory evidence is failure. The supervisor validates semantics supplied by the driver, but never invents test counts or domain-specific assertions.
