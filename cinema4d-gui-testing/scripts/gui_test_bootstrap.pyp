"""Disposable Cinema 4D host bootstrap. Do not install outside the supervisor root."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import traceback
from importlib.machinery import SourceFileLoader

import c4d
from c4d import gui


SCHEMA_VERSION = 1
_runner_dialog = None


def _root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_config():
    path = os.path.join(_root(), "run-config.json")
    with open(path, "r", encoding="utf-8") as stream:
        config = json.load(stream)
    required = ("run_id", "results", "driver", "artifacts")
    if any(not config.get(key) for key in required):
        raise RuntimeError("Disposable run configuration is incomplete.")
    return config


class TestContext:
    def __init__(self, config):
        self.run_id = str(config["run_id"])
        self.scene_readonly = config.get("scene_readonly") or None
        self.plugin_paths = tuple(config.get("plugin_paths") or ())
        self.artifacts_dir = os.path.abspath(config["artifacts"])
        self._results = os.path.abspath(config["results"])
        self._sequence = 0
        self._last_monotonic_ns = 0
        self._cleanup = []
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def _next_monotonic_ns(self):
        value = time.monotonic_ns()
        if value <= self._last_monotonic_ns:
            value = self._last_monotonic_ns + 1
        self._last_monotonic_ns = value
        return value

    def emit(self, event, **payload):
        if not isinstance(event, str) or not event or event == "final":
            raise ValueError("Driver event must be a non-empty name other than 'final'.")
        self._sequence += 1
        record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self._sequence,
            "event": event,
            "monotonic_ns": self._next_monotonic_ns(),
        }
        reserved = set(record)
        if reserved.intersection(payload):
            raise ValueError("Driver payload uses a reserved evidence field.")
        record.update(payload)
        with open(self._results, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    def check(self, name, condition, details=None):
        ok = bool(condition)
        self.emit("check", name=str(name), ok=ok, details=details)
        if not ok:
            raise AssertionError("GUI check failed: %s" % name)
        return True

    def artifact(self, name, value, media_type=None):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("._")
        if not safe or safe in (".", ".."):
            raise ValueError("Artifact name is empty or unsafe.")
        if isinstance(value, bytes):
            data = value
            suffix = "bin"
            media = media_type or "application/octet-stream"
        elif isinstance(value, str):
            data = value.encode("utf-8")
            suffix = "txt"
            media = media_type or "text/plain; charset=utf-8"
        else:
            data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            suffix = "json"
            media = media_type or "application/json"
        if "." not in safe:
            safe = safe + "." + suffix
        path = os.path.abspath(os.path.join(self.artifacts_dir, safe))
        if os.path.commonpath((path, self.artifacts_dir)) != self.artifacts_dir:
            raise ValueError("Artifact path escapes the disposable artifact directory.")
        with open(path, "wb") as stream:
            stream.write(data)
        self.emit(
            "artifact",
            name=safe,
            path=os.path.relpath(path, self.artifacts_dir),
            media_type=media,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        return path

    def add_cleanup(self, callback):
        if not callable(callback):
            raise TypeError("Cleanup must be callable.")
        self._cleanup.append(callback)

    def run_cleanup(self):
        failures = []
        while self._cleanup:
            callback = self._cleanup.pop()
            try:
                callback()
            except Exception as exc:
                failures.append({"error": str(exc), "traceback": traceback.format_exc()})
        return failures

    def final(self, ok, **payload):
        self._sequence += 1
        record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self._sequence,
            "event": "final",
            "monotonic_ns": self._next_monotonic_ns(),
            "ok": bool(ok),
        }
        record.update(payload)
        with open(self._results, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()


def _import_driver(path):
    name = "cinema4d_gui_test_driver_copy"
    loader = SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    if not callable(getattr(module, "run", None)):
        raise RuntimeError("Trusted driver must define run(context).")
    return module


class RunnerDialog(gui.GeDialog):
    def __init__(self, context, driver_path):
        super().__init__()
        self._context = context
        self._driver_path = driver_path
        self._ran = False

    def CreateLayout(self):
        self.SetTitle("Cinema 4D GUI Test Runner")
        return True

    def InitValues(self):
        self.SetTimer(200)
        return True

    def Timer(self, message):
        del message
        global _runner_dialog
        if self._ran:
            return
        self._ran = True
        self.SetTimer(0)
        error = None
        error_traceback = None
        summary = None
        try:
            driver = _import_driver(self._driver_path)
            summary = driver.run(self._context)
            if summary is not None:
                self._context.emit("driver_result", result=summary)
        except Exception as exc:
            error = str(exc)
            error_traceback = traceback.format_exc()
        cleanup_failures = self._context.run_cleanup()
        try:
            self.Close()
        except Exception as exc:
            cleanup_failures.append({"error": str(exc), "traceback": traceback.format_exc()})
        _runner_dialog = None
        self._context.emit(
            "cleanup_complete", ok=not cleanup_failures, failures=cleanup_failures
        )
        if error is None and not cleanup_failures:
            self._context.final(True)
        else:
            self._context.final(
                False,
                error=error or "cleanup failed",
                traceback=error_traceback,
                cleanup_failures=cleanup_failures,
            )


def PluginMessage(message_id, data):
    del data
    global _runner_dialog
    if message_id != c4d.C4DPL_PROGRAM_STARTED or _runner_dialog is not None:
        return True
    context = None
    try:
        config = _load_config()
        context = TestContext(config)
        context.emit("program_started")
        _runner_dialog = RunnerDialog(context, config["driver"])
        opened = _runner_dialog.Open(
            dlgtype=c4d.DLG_TYPE_ASYNC,
            pluginid=0,
            defaultw=260,
            defaulth=90,
        )
        if not opened:
            context.emit("cleanup_complete", ok=True, failures=[])
            context.final(False, error="RunnerDialog.Open returned False.", traceback=None)
            _runner_dialog = None
    except Exception:
        # Configuration failures may happen before a context exists. Build one
        # only if possible, then publish one fail-closed cleanup/final pair.
        try:
            if context is None:
                config = _load_config()
                context = TestContext(config)
                context.emit("program_started")
            context.emit("cleanup_complete", ok=True, failures=[])
            context.final(False, error="bootstrap initialization failed", traceback=traceback.format_exc())
        except Exception:
            pass
        _runner_dialog = None
    return True
