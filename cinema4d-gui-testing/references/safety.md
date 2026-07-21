# Safety boundary

This harness is Windows-only because containment depends on Win32 process handles and Job Objects.

The supervisor creates the exact Cinema process suspended, assigns its real process handle to a new private Job Object configured with `KILL_ON_JOB_CLOSE`, and resumes only after successful assignment. If creation, assignment, or resume fails, it closes the job and the owned handles and reports failure. It never searches for Cinema processes and never kills by name.

Each run uses isolated preferences, plugins, configuration, evidence, and artifacts. A user-supplied root must not exist; an automatically allocated root is new. This prevents old evidence from being mistaken for a current result.

Before execution:

1. Inspect the complete driver and all plugin sources; they execute with the current user's permissions.
2. Verify that `--cinema` matches the plugin/API version under test.
3. Run `--dry-run`, inspect the manifest, then use a separate explicit `--run` command.
4. Close neither the user's Cinema nor any unrelated process. The private job owns only the process tree created by this run.

Source inputs are copied and fingerprinted. An optional scene is read from its original path so the driver must never save it; the supervisor detects any byte, size, or mtime change even after test failure.

When a GUI driver calls Win32 through `ctypes`, declare `argtypes` and `restype`
for every function before the first call. Use pointer-sized types for `HWND`,
`HDC`, `HBITMAP`, and other handles. Python's implicit `c_int` return type can
truncate 64-bit handles and crash the hosted Cinema process; a non-null value is
not proof that an untyped handle is valid.
