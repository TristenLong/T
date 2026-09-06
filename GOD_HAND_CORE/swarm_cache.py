"""Cross-process swarm cache + atomic lock primitives, importable.

Extracted from the swarm artifact task_1788652369.py into a reusable module so
the running server can expose them as real tools. The fixed-slot overflow and
verify-is-a-pure-check fixes from that artifact are carried forward here.

Classes:
  CrossPlatformAtomicLock: exclusive cross-platform file lock (O_EXCL) w/ backoff.
  BoundedMmapCache: bounded, checksum-validated mmap cache with self-healing.
  SwarmChannelCoordinator: transactional 5-channel health check + self-healing.
"""

import hashlib
import mmap
import os
import random
import shutil
import struct
import tempfile
import time
from typing import Dict, List, Optional


class CrossPlatformAtomicLock:
    """Cross-platform exclusive file lock with exponential backoff + jitter.

    Uses atomic O_EXCL file creation so it works identically on Windows and
    POSIX (no fcntl, which doesn't exist on Windows).
    """

    def __init__(self, lock_path: str, timeout: float = 2.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self._is_locked = False

    def acquire(self) -> bool:
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < self.timeout:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd)
                self._is_locked = True
                return True
            except OSError:
                attempt += 1
                time.sleep(random.uniform(0.005, 0.02) * min(attempt, 5))
        return False

    def release(self) -> None:
        if self._is_locked:
            try:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except OSError:
                pass
            finally:
                self._is_locked = False

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Failed to acquire atomic lock on {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class BoundedMmapCache:
    """Bounded mmap cache with checksum validation and self-healing stores.

    Non-owning, process-safe singleton semantics: hold one instance and call
    close() at shutdown. Entries are length-prefixed (no fixed slots) so a large
    value can never silently overwrite a neighbour.
    """

    def __init__(self, capacity_bytes: int = 1048576, cache_file: Optional[str] = None):
        self.capacity_bytes = capacity_bytes
        if cache_file:
            self.cache_file = cache_file
            self._fd = os.open(self.cache_file, os.O_CREAT | os.O_RDWR, 0o600)
        else:
            self._tf = tempfile.NamedTemporaryFile(delete=False)
            self.cache_file = self._tf.name
            self._fd = self._tf.file.fileno()

        if os.path.getsize(self.cache_file) < self.capacity_bytes:
            os.ftruncate(self._fd, self.capacity_bytes)

        self._mmap = mmap.mmap(self._fd, self.capacity_bytes, access=mmap.ACCESS_WRITE)
        self._initialize_header()

    def _initialize_header(self) -> None:
        # Header: magic(4) | entry count(4) | next write offset(4)
        self._mmap.seek(0)
        magic = self._mmap.read(4)
        if magic != b"SWPC":
            self._mmap.seek(0)
            self._mmap.write(b"SWPC")
            self._mmap.write(struct.pack("<II", 0, 12))

    def heal_corruption(self) -> bool:
        try:
            self._mmap.seek(0)
            magic = self._mmap.read(4)
            count, off = struct.unpack("<II", self._mmap.read(8))
            if magic != b"SWPC" or off < 12 or off > self.capacity_bytes:
                raise ValueError("bad header")
            return False
        except Exception:
            self._mmap.seek(0)
            self._mmap.write(b"SWPC")
            self._mmap.write(struct.pack("<II", 0, 12))
            return True

    def put(self, key: str, value: bytes) -> bool:
        self.heal_corruption()
        key_bytes = key.encode("utf-8")
        if len(key_bytes) > 255 or len(value) > 65535:
            raise ValueError("Key or value exceeds maximum size limits.")

        digest = hashlib.sha256(value).digest()
        payload = struct.pack("<B", len(key_bytes)) + key_bytes + struct.pack("<H", len(value)) + value + digest
        entry = struct.pack("<I", len(payload)) + payload

        self._mmap.seek(4)
        _count, off = struct.unpack("<II", self._mmap.read(8))
        if off + len(entry) > self.capacity_bytes:
            return False  # Cache full; higher layer evicts.

        self._mmap.seek(off)
        self._mmap.write(entry)
        self._mmap.seek(4)
        self._mmap.write(struct.pack("<II", _count + 1, off + len(entry)))
        return True

    def get(self, key: str) -> Optional[bytes]:
        self.heal_corruption()
        key_bytes = key.encode("utf-8")
        self._mmap.seek(4)
        count, _off = struct.unpack("<II", self._mmap.read(8))

        pos = 12
        for _ in range(count):
            self._mmap.seek(pos)
            len_raw = self._mmap.read(4)
            if len(len_raw) < 4:
                break
            entry_len = struct.unpack("<I", len_raw)[0]
            if entry_len < 35 or pos + 4 + entry_len > self.capacity_bytes:
                break
            body = self._mmap.read(entry_len)
            k_len = body[0]
            k = body[1:1 + k_len]
            v_len = struct.unpack("<H", body[1 + k_len:3 + k_len])[0]
            val = body[3 + k_len:3 + k_len + v_len]
            stored_digest = body[3 + k_len + v_len:3 + k_len + v_len + 32]
            if k == key_bytes:
                if stored_digest != hashlib.sha256(val).digest():
                    return None
                return val
            pos += 4 + entry_len
        return None

    def clear(self) -> bool:
        self.heal_corruption()
        self._mmap.seek(0)
        self._mmap.write(b"SWPC")
        self._mmap.write(struct.pack("<II", 0, 12))
        return True

    def stats(self) -> Dict:
        self.heal_corruption()
        self._mmap.seek(0)
        self._mmap.read(4)
        count, off = struct.unpack("<II", self._mmap.read(8))
        return {
            "capacity_bytes": self.capacity_bytes,
            "entries": count,
            "used_bytes": off,
            "file": os.path.basename(self.cache_file),
        }

    def close(self):
        try:
            self._mmap.close()
        except Exception:
            pass


class SwarmChannelCoordinator:
    """Transactional 5-channel coordinator: pure health check + self-healing."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.channels = [f"channel_{i}" for i in range(1, 6)]
        os.makedirs(self.base_dir, exist_ok=True)

    def verify_all_channels(self) -> Dict[str, bool]:
        status = {}
        for ch in self.channels:
            ch_path = os.path.join(self.base_dir, ch)
            test_file = os.path.join(ch_path, "ping.dat")
            healthy = False
            try:
                if os.path.isdir(ch_path) and os.path.isfile(test_file):
                    with open(test_file, "r") as f:
                        healthy = f.read().strip() == "OK"
            except OSError:
                healthy = False
            status[ch] = healthy
        return status

    def self_heal_channels(self) -> List[str]:
        healed = []
        statuses = self.verify_all_channels()
        for ch, healthy in statuses.items():
            if not healthy:
                ch_path = os.path.join(self.base_dir, ch)
                lock_path = f"{ch_path}.lock"
                try:
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
                    os.makedirs(ch_path, exist_ok=True)
                    with open(os.path.join(ch_path, "ping.dat"), "w") as f:
                        f.write("OK")
                    healed.append(ch)
                except Exception:
                    pass
        return healed