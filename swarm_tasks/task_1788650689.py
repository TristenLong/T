import collections
import time
import unittest
from typing import Dict, Tuple, Any, Optional
import threading

class AdaptiveMemoryCache:
    """
    Dynamic Adaptive Cache for Swarm Knowledge Memory.
    Implements a hybrid LRU/LFU eviction policy combined with frequency-based scoring,
    adaptive time-to-live (TTL) adjustments, and thread-safe mutex locking for robust production use.
    """
    def __init__(self, capacity: int = 100, base_ttl: float = 60.0):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than zero.")
        self.capacity = capacity
        self.base_ttl = base_ttl
        # key -> (value, expiry_time, access_count, last_access_time)
        self.cache: Dict[str, Tuple[Any, float, int, float]] = {}
        self._lock = threading.RLock()

    def _calculate_adaptive_ttl(self, access_count: int) -> float:
        """Scales TTL dynamically based on access frequency."""
        return self.base_ttl * (1.0 + min(float(access_count), 10.0))

    def _evict_expired(self, current_time: float) -> None:
        """Purges expired keys from the cache."""
        expired_keys = [k for k, (_, expiry, _, _) in self.cache.items() if current_time > expiry]
        for k in expired_keys:
            del self.cache[k]

    def _evict_optimal(self) -> None:
        """
        Evicts an entry using a combined metric of access frequency and recency (LRU/LFU hybrid).
        Scores entries by access_count / (current_time - last_access_time + 1).
        Lowest score is evicted.
        """
        if not self.cache:
            return
        
        current_time = time.time()
        victim_key = min(
            self.cache.keys(),
            key=lambda k: (self.cache[k][2] / (current_time - self.cache[k][3] + 1e-5), self.cache[k][3])
        )
        del self.cache[victim_key]

    def set(self, key: str, value: Any) -> None:
        """Inserts or updates an entry in the adaptive cache with thread-safe locking."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)

            if key not in self.cache and len(self.cache) >= self.capacity:
                self._evict_optimal()

            access_count = 1
            if key in self.cache:
                access_count = self.cache[key][2] + 1

            ttl = self._calculate_adaptive_ttl(access_count)
            expiry_time = current_time + ttl
            self.cache[key] = (value, expiry_time, access_count, current_time)

    def get(self, key: str) -> Optional[Any]:
        """Retrieves an entry, updates access counts, last access timestamps, and slides TTL."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)

            if key not in self.cache:
                return None

            value, _, access_count, _ = self.cache[key]
            new_access_count = access_count + 1
            ttl = self._calculate_adaptive_ttl(new_access_count)
            expiry_time = current_time + ttl

            self.cache[key] = (value, expiry_time, new_access_count, current_time)
            return value

    def size(self) -> int:
        """Returns current item count after purging expired entries."""
        with self._lock:
            self._evict_expired(time.time())
            return len(self.cache)


class TestAdaptiveMemoryCache(unittest.TestCase):
    def test_initialization(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=10.0)
        self.assertEqual(cache.capacity, 2)
        with self.assertRaises(ValueError):
            AdaptiveMemoryCache(capacity=0)

    def test_set_and_get(self):
        cache = AdaptiveMemoryCache(capacity=5, base_ttl=10.0)
        cache.set("k1", "v1")
        self.assertEqual(cache.get("k1"), "v1")
        self.assertIsNone(cache.get("nonexistent"))

    def test_capacity_eviction(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=10.0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")  # Should trigger eviction
        self.assertLessEqual(cache.size(), 2)

    def test_thread_safety(self):
        cache = AdaptiveMemoryCache(capacity=100, base_ttl=5.0)
        def worker(start_idx):
            for i in range(50):
                key = f"key_{start_idx}_{i}"
                cache.set(key, i)
                cache.get(key)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertGreater(cache.size(), 0)


if __name__ == "__main__":
    unittest.main(argv=[''], exit=False)