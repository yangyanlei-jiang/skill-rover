"""Locked, atomic local state. Never silently reset corrupt state."""
import copy
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

class Store:
    def __init__(self, directory):
        self.root = Path(directory).expanduser().absolute()
        self.path = self.root / "state.json"

    @contextmanager
    def _lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or self.path.is_symlink():
            raise ValueError("state root and state file must not be symlinks")
        lockpath = self.root / ".lock"
        if lockpath.is_symlink():
            raise ValueError("state lock must not be a symlink")
        with lockpath.open("a+b") as lock:
            if os.name == "nt":
                lock.seek(0)
                if not lock.read(1):
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self):
        if not self.path.exists():
            return {"version": 1, "entries": {}, "uses": {}, "history": [], "notices": {}}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != 1 or not isinstance(state["entries"], dict) or not isinstance(state["uses"], dict):
                raise ValueError("unsupported state schema")
            if not isinstance(state["history"], list) or not isinstance(state["notices"], dict):
                raise ValueError("unsupported state schema")
            return state
        except (ValueError, KeyError, AttributeError) as exc:
            raise ValueError("invalid state; preserved for recovery: " + str(self.path)) from exc

    def read(self):
        with self._lock():
            return self._read()

    @contextmanager
    def transaction(self):
        with self._lock():
            state = self._read()
            before = copy.deepcopy(state)
            yield state
            if state != before or not self.path.exists():
                atomic_json(self.path, state)

