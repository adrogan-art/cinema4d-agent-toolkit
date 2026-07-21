"""Prepare and supervise one isolated Cinema 4D GUI integration test."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Callable


SCHEMA_VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent


class _JobBasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JobIoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimit),
        ("IoInfo", _JobIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _StartupInfoW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint(path: Path) -> dict[str, object]:
    path = path.resolve()
    if path.is_file():
        stat = path.stat()
        return {
            "kind": "file", "sha256": _sha256(path), "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    if not path.is_dir():
        raise FileNotFoundError(path)
    files = []
    for item in sorted(path.rglob("*"), key=lambda value: value.as_posix().lower()):
        if item.is_symlink():
            raise RuntimeError(f"Symlinked source input is not allowed: {item}")
        if item.is_file():
            stat = item.stat()
            files.append({
                "path": item.relative_to(path).as_posix(), "sha256": _sha256(item),
                "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            })
    return {"kind": "directory", "files": files}


def verify_sources(manifest: dict[str, object]) -> None:
    for source in manifest["sources"]:
        path = Path(source["path"])
        actual = source_fingerprint(path)
        if actual != source["fingerprint"]:
            raise RuntimeError(f"Source input changed during GUI test: {path}")


def _copy_source(source: Path, destination: Path) -> Path:
    if source.is_dir():
        shutil.copytree(source, destination)
        return destination
    destination.mkdir(parents=True)
    target = destination / source.name
    shutil.copy2(source, target)
    return target


def prepare(
    root: Path,
    driver: Path,
    plugin_sources: list[Path],
    scene_readonly: Path | None,
) -> dict[str, object]:
    root = root.resolve()
    if root.exists():
        raise RuntimeError(f"Artifact root already exists; choose a new path: {root}")
    for source in (driver, *plugin_sources):
        resolved = source.resolve()
        if resolved.is_dir() and root.is_relative_to(resolved):
            raise RuntimeError(f"Artifact root cannot be inside a source directory: {resolved}")
    root.mkdir(parents=True)
    prefs = root / "prefs"
    plugins = root / "plugins"
    artifacts = root / "artifacts"
    copied_inputs = root / "inputs"
    prefs.mkdir()
    plugins.mkdir()
    artifacts.mkdir()
    copied_inputs.mkdir()

    originals = [driver.resolve(), *(path.resolve() for path in plugin_sources)]
    if scene_readonly is not None:
        originals.append(scene_readonly.resolve())
    source_records = [
        {"path": str(path), "fingerprint": source_fingerprint(path)} for path in originals
    ]

    driver_copy_dir = copied_inputs / "driver"
    copied_driver = _copy_source(driver.resolve(), driver_copy_dir)
    copied_plugin_paths = []
    for index, source in enumerate(plugin_sources, 1):
        safe_name = source.name or f"plugin-{index}"
        destination = plugins / f"source-{index:02d}-{safe_name}"
        copied_plugin_paths.append(str(_copy_source(source.resolve(), destination)))

    bootstrap_dir = plugins / "cinema4d_gui_test_bootstrap"
    bootstrap_dir.mkdir()
    shutil.copy2(SCRIPT_DIR / "gui_test_bootstrap.pyp", bootstrap_dir / "gui_test_bootstrap.pyp")

    run_id = str(uuid.uuid4())
    results = root / "evidence.jsonl"
    config = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "results": str(results),
        "driver": str(copied_driver),
        "artifacts": str(artifacts),
        "plugin_paths": copied_plugin_paths,
        "scene_readonly": str(scene_readonly.resolve()) if scene_readonly else None,
    }
    (root / "run-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "root": str(root),
        "prefs": str(prefs),
        "plugins": str(plugins),
        "artifacts": str(artifacts),
        "results": str(results),
        "driver_copy": str(copied_driver),
        "plugin_copies": copied_plugin_paths,
        "scene_readonly": str(scene_readonly.resolve()) if scene_readonly else None,
        "sources": source_records,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    verify_sources(manifest)
    return manifest


class WindowsKillJob:
    KILL_ON_JOB_CLOSE = 0x00002000
    EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Cinema GUI test containment requires Windows.")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _JobExtendedLimit()
        info.BasicLimitInformation.LimitFlags = self.KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            self._handle, self.EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        ):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process_handle) -> None:
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


class Win32OwnedProcess:
    CREATE_SUSPENDED = 0x00000004
    STILL_ACTIVE = 259
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    def __init__(self, process_handle, thread_handle, pid, kernel32):
        self.process_handle = process_handle
        self.thread_handle = thread_handle
        self.pid = int(pid)
        self.returncode = None
        self._kernel32 = kernel32

    @classmethod
    def create(cls, command: list[str], cwd: str):
        if os.name != "nt":
            raise RuntimeError("Cinema GUI test launcher requires Windows.")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
            ctypes.POINTER(_StartupInfoW), ctypes.POINTER(_ProcessInformation),
        ]
        kernel32.CreateProcessW.restype = wintypes.BOOL
        kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
        kernel32.ResumeThread.restype = wintypes.DWORD
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        startup = _StartupInfoW()
        startup.cb = ctypes.sizeof(startup)
        info = _ProcessInformation()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        if not kernel32.CreateProcessW(
            None, command_line, None, None, False, cls.CREATE_SUSPENDED, None, cwd,
            ctypes.byref(startup), ctypes.byref(info),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return cls(info.hProcess, info.hThread, info.dwProcessId, kernel32)

    def resume(self) -> None:
        if not self.thread_handle:
            raise RuntimeError("Primary thread handle is closed.")
        result = self._kernel32.ResumeThread(self.thread_handle)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        self._kernel32.CloseHandle(self.thread_handle)
        self.thread_handle = None

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        code = wintypes.DWORD()
        if not self._kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value == self.STILL_ACTIVE:
            return None
        self.returncode = int(code.value)
        return self.returncode

    def wait(self, timeout=None):
        milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
        result = self._kernel32.WaitForSingleObject(self.process_handle, milliseconds)
        if result == self.WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired(["CreateProcessW"], timeout)
        if result != self.WAIT_OBJECT_0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = self.poll()
        if code is None:
            raise RuntimeError("Process signaled without an exit code.")
        return code

    def kill(self) -> None:
        if self.poll() is None and not self._kernel32.TerminateProcess(self.process_handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.thread_handle:
            self._kernel32.CloseHandle(self.thread_handle)
            self.thread_handle = None
        if self.process_handle:
            self._kernel32.CloseHandle(self.process_handle)
            self.process_handle = None


def spawn_in_job(
    command: list[str],
    cwd: str,
    *,
    process_factory: Callable = Win32OwnedProcess.create,
    job_factory: Callable = WindowsKillJob,
):
    job = job_factory()
    process = None
    try:
        process = process_factory(command, cwd)
        job.assign(process.process_handle)
        process.resume()
        return process, job
    except Exception:
        job.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.close()
        raise


def parse_evidence(path: Path, expected_run_id: str):
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="strict")
    if not content or not content.endswith("\n"):
        return None
    records = []
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            raise RuntimeError(f"Blank evidence record at line {line_number}.")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed evidence at line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise RuntimeError(f"Non-object evidence at line {line_number}.")
        records.append(record)
    if any(record.get("schema_version") != SCHEMA_VERSION for record in records):
        raise RuntimeError("Evidence schema version mismatch.")
    if any(record.get("run_id") != expected_run_id for record in records):
        raise RuntimeError("Evidence contains a stale or foreign run_id.")
    if [record.get("seq") for record in records] != list(range(1, len(records) + 1)):
        raise RuntimeError("Evidence sequence is incomplete or non-continuous.")
    monotonic_values = [record.get("monotonic_ns") for record in records]
    if (
        any(not isinstance(value, int) for value in monotonic_values)
        or any(left >= right for left, right in zip(monotonic_values, monotonic_values[1:]))
    ):
        raise RuntimeError("Evidence monotonic timestamps are missing or non-increasing.")
    finals = [record for record in records if record.get("event") == "final"]
    if not finals:
        return None
    if len(finals) != 1 or records[-1] is not finals[0]:
        raise RuntimeError("Evidence must contain exactly one final record, last.")
    if sum(record.get("event") == "program_started" for record in records) != 1:
        raise RuntimeError("Evidence must contain exactly one program_started record.")
    if sum(record.get("event") == "cleanup_complete" for record in records) != 1:
        raise RuntimeError("Evidence must contain exactly one cleanup_complete record.")
    if records[0].get("event") != "program_started":
        raise RuntimeError("program_started must be the first evidence record.")
    if len(records) < 2 or records[-2].get("event") != "cleanup_complete":
        raise RuntimeError("cleanup_complete must immediately precede final evidence.")
    if records[-2].get("ok") is not True:
        raise RuntimeError("GUI cleanup did not complete successfully.")
    if finals[0].get("ok") is not True:
        raise RuntimeError(f"GUI test final record failed: {finals[0]}")
    checks = [record for record in records if record.get("event") == "check"]
    if any(record.get("ok") is not True for record in checks):
        raise RuntimeError("One or more driver checks failed.")
    if any(record.get("error") or record.get("traceback") for record in records):
        raise RuntimeError("Evidence contains an error or traceback.")
    return records


def run(manifest: dict[str, object], cinema: Path, timeout: float):
    results = Path(manifest["results"])
    if results.exists():
        raise RuntimeError("Stale evidence exists before Cinema launch.")
    command = [
        str(cinema),
        "g_licenseModel=LICENSEMODEL::MAXONAPP",
        f"g_prefspath={manifest['prefs']}",
        f"g_additionalModulePath={manifest['plugins']}",
    ]
    process = None
    job = None
    deadline = time.monotonic() + timeout
    verify_sources(manifest)
    try:
        process, job = spawn_in_job(command, str(manifest["root"]))
        while time.monotonic() < deadline:
            records = parse_evidence(results, str(manifest["run_id"]))
            if records is not None:
                return records
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"Owned Cinema PID {process.pid} exited with {return_code} before valid final evidence."
                )
            time.sleep(0.2)
        raise TimeoutError(f"Cinema GUI test timed out after {timeout:.1f} seconds.")
    finally:
        try:
            if job is not None:
                job.close()
                if process is not None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
            elif process is not None and process.poll() is None:
                process.kill()
            if process is not None:
                process.close()
        finally:
            verify_sources(manifest)


def _config_defaults(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("--config must contain a JSON object.")
    allowed = {
        "cinema", "trusted_driver", "plugin_sources", "scene_readonly",
        "timeout", "root", "keep_artifacts",
    }
    unknown = set(data) - allowed
    if unknown:
        raise SystemExit(f"Unknown config keys: {sorted(unknown)}")
    return data


def parse_args(argv=None):
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path)
    preliminary, _ = config_parser.parse_known_args(argv)
    defaults = _config_defaults(preliminary.config)
    parser = argparse.ArgumentParser(parents=[config_parser])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Prepare only; never launch Cinema.")
    mode.add_argument("--run", action="store_true", help="Launch one isolated owned Cinema test.")
    parser.add_argument("--cinema", type=Path, default=defaults.get("cinema"))
    parser.add_argument("--trusted-driver", type=Path, default=defaults.get("trusted_driver"))
    parser.add_argument(
        "--plugin-source", dest="plugin_sources", type=Path, action="append",
        default=[Path(value) for value in defaults.get("plugin_sources", [])],
    )
    parser.add_argument("--scene-readonly", type=Path, default=defaults.get("scene_readonly"))
    parser.add_argument("--timeout", type=float, default=float(defaults.get("timeout", 300.0)))
    parser.add_argument("--root", type=Path, default=defaults.get("root"))
    parser.add_argument(
        "--keep-artifacts", action="store_true", default=bool(defaults.get("keep_artifacts", False))
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    if os.name != "nt":
        raise SystemExit("cinema4d-gui-testing is Windows-only.")
    args = parse_args(argv)
    if args.cinema is None:
        raise SystemExit("--cinema is required (or set cinema in --config).")
    if args.trusted_driver is None:
        raise SystemExit("--trusted-driver is required (or set trusted_driver in --config).")
    cinema = Path(args.cinema).resolve()
    driver = Path(args.trusted_driver).resolve()
    plugins = [Path(path).resolve() for path in args.plugin_sources]
    scene = Path(args.scene_readonly).resolve() if args.scene_readonly else None
    if not cinema.is_file():
        raise SystemExit(f"Cinema executable not found: {cinema}")
    if not driver.is_file():
        raise SystemExit(f"Trusted driver not found: {driver}")
    for source in plugins:
        if not source.exists():
            raise SystemExit(f"Plugin source not found: {source}")
    if scene is not None and not scene.is_file():
        raise SystemExit(f"Read-only scene not found: {scene}")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive.")

    auto_root = args.root is None
    root = (
        Path(tempfile.gettempdir()) / f"cinema4d_gui_test_{uuid.uuid4().hex}"
        if auto_root else Path(args.root).resolve()
    )
    manifest = None
    try:
        manifest = prepare(root, driver, plugins, scene)
        manifest["cinema"] = str(cinema)
        manifest["timeout"] = args.timeout
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if args.dry_run:
            return 0
        records = run(manifest, cinema, args.timeout)
        print(json.dumps({"ok": True, "root": str(root), "records": len(records)}, indent=2))
        return 0
    finally:
        if manifest is not None:
            verify_sources(manifest)
        if auto_root and not args.keep_artifacts and root.exists():
            deadline = time.monotonic() + 15
            while root.exists():
                try:
                    shutil.rmtree(root)
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
