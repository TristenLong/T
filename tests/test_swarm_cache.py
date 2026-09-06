"""Pure-logic tests for the cross-process swarm cache (no server needed)."""
import os

from swarm_cache import BoundedMmapCache


def test_put_get_roundtrip(tmp_path):
    path = os.path.join(str(tmp_path), "cache.bin")
    cache = BoundedMmapCache(100000, path)
    try:
        assert cache.put("alpha", b"hello")
        assert cache.get("alpha") == b"hello"
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["used_bytes"] > 12
    finally:
        cache.close()


def test_get_missing_returns_none(tmp_path):
    cache = BoundedMmapCache(100000, os.path.join(str(tmp_path), "c.bin"))
    try:
        assert cache.get("nope") is None
    finally:
        cache.close()


def test_oversized_value_raises_valueerror(tmp_path):
    path = os.path.join(str(tmp_path), "c.bin")
    cache = BoundedMmapCache(1000, path)
    try:
        try:
            cache.put("big", b"x" * 70000)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for oversized value")
    finally:
        cache.close()


def test_capacity_exhaustion_returns_false(tmp_path):
    # Header is 12 bytes; each entry is 43 bytes for these tiny keys/values.
    path = os.path.join(str(tmp_path), "c.bin")
    cache = BoundedMmapCache(60, path)
    try:
        assert cache.put("one", b"1")
        assert not cache.put("two", b"2")  # second entry does not fit
    finally:
        cache.close()


def test_persist_reopen(tmp_path):
    path = os.path.join(str(tmp_path), "c.bin")
    first = BoundedMmapCache(100000, path)
    first.put("k", b"v")
    first.close()
    second = BoundedMmapCache(100000, path)
    try:
        assert second.get("k") == b"v"
    finally:
        second.close()