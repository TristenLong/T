#!/usr/bin/env python3
"""
CODEX Terminal Engine - Task 1788651024
Topic: Deterministic Memory-Mapped Safe Cache Pruning Service
Standard: AGENTS.md Compliant | Cross-Platform (Windows & Linux)
"""

import os
import sys
import mmap
import time
import tempfile
import unittest
from typing import Dict, Any, Optional

class MmapBoundedCache:
    """
    Deterministic memory-mapped bounded cache manager.
    Enforces hard byte-limit constraints without risking process deadlocks.
    """

    def __init__(self, cache_file_path: str, max_size_bytes: int = 1048576):
        self.cache_file_path = cache_file_path
        self.max_size_bytes = max_size_bytes
        self._ensure_cache_file()

    def _ensure_cache_file(self) -> None:
        """Initializes the binary cache container if absent."""
        if not os.path.exists(self.cache_file_path):
            parent = os.path.dirname(self.cache_file_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            with open(self.cache_file_path, "wb") as f:
                f.write(b"\x00" * 1024)

    def write_payload(self, data: bytes) -> int:
        """Appends bytes to the cache file."""
        with open(self.cache_file_path, "ab") as f:
            return f.write(data)

    def prune_safe_cache(self) -> Dict[str, Any]:
        """
        Enforces deterministic size bounds on the cache file.
        Cross-platform safe for both Windows and Linux.
        """
        if not os.path.exists(self.cache_file_path):
            return {"status": "NOOP", "reason": "File does not exist", "size": 0}

        current_size = os.path.getsize(self.cache_file_path)
        if current_size <= self.max_size_bytes:
            return {
                "status": "NOMINAL",
                "current_size": current_size,
                "max_size": self.max_size_bytes,
                "pruned": False
            }

        # Truncate and compact under hard byte-limit constraint
        try:
            with open(self.cache_file_path, "r+b") as f:
                # Read tail if compaction requires preserving recent entries
                f.seek(-self.max_size_bytes, os.SEEK_END)
                preserved_data = f.read(self.max_size_bytes)
                f.seek(0)
                f.write(preserved_data)
                f.truncate(self.max_size_bytes)
                f.flush()

            new_size = os.path.getsize(self.cache_file_path)
            return {
                "status": "PRUNED",
                "previous_size": current_size,
                "current_size": new_size,
                "max_size": self.max_size_bytes,
                "freed_bytes": current_size - new_size,
                "pruned": True
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "current_size": current_size}

    def read_mmap(self) -> bytes:
        """Inspects content via memory mapping."""
        with open(self.cache_file_path, "rb") as f:
            if os.path.getsize(self.cache_file_path) == 0:
                return b""
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                return mm.read()


class TestMmapBoundedCache(unittest.TestCase):
    """Automated unit test suite enforcing AGENTS.md verification standard."""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.cache = MmapBoundedCache(self.temp_file.name, max_size_bytes=2048)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            try:
                os.remove(self.temp_file.name)
            except OSError:
                pass

    def test_nominal_within_bounds(self):
        result = self.cache.prune_safe_cache()
        self.assertEqual(result["status"], "NOMINAL")
        self.assertFalse(result["pruned"])

    def test_pruning_enforces_hard_limit(self):
        # Exceed 2048 bytes
        oversized = b"X" * 4096
        self.cache.write_payload(oversized)
        self.assertGreater(os.path.getsize(self.temp_file.name), 2048)

        result = self.cache.prune_safe_cache()
        self.assertEqual(result["status"], "PRUNED")
        self.assertTrue(result["pruned"])
        self.assertEqual(result["current_size"], 2048)
        self.assertEqual(os.path.getsize(self.temp_file.name), 2048)

    def test_mmap_read(self):
        self.cache.write_payload(b"CODEX_QUANTUM_TELEMETRY")
        content = self.cache.read_mmap()
        self.assertIn(b"CODEX_QUANTUM_TELEMETRY", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
