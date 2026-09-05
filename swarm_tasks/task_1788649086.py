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
            
            # If key exists, preserve access count/time or initialize
            if key in self.cache:
                _, _, count, last_access = self.cache[key]
                count += 1
            else:
                count = 1
                last_access = current_time

            expiry = current_time + self._calculate_adaptive_ttl(count)

            if key not in self.cache and len(self.cache) >= self.capacity:
                self._evict_optimal()

            self.cache[key] = (value, expiry, count, last_access)

    def get(self, key: str) -> Optional[Any]:
        """Retrieves an entry, updating access metadata and TTL dynamically."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)

            if key not in self.cache:
                return None

            value, expiry, count, _ = self.cache[key]
            if current_time > expiry:
                del self.cache[key]
                return None

            # Increment access count and refresh last access time and TTL
            new_count = count + 1
            new_expiry = current_time + self._calculate_adaptive_ttl(new_count)
            self.cache[key] = (value, new_expiry, new_count, current_time)
            return value

    def invalidate(self, key: str) -> bool:
        """Explicitly invalidates and removes a cache entry."""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self) -> None:
        """Flushes the entire cache."""
        with self._lock:
            self.cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Returns diagnostic metrics for the self-healing service."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)
            return {
                "size": len(self.cache),
                "capacity": self.capacity,
                "keys": list(self.cache.keys())
            }


class TestAdaptiveMemoryCache(unittest.TestCase):
    def test_initialization(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=10.0)
        self.assertEqual(cache.capacity, 2)
        with self.assertRaises(ValueError):
            AdaptiveMemoryCache(capacity=0)

    def test_basic_set_get(self):
        cache = AdaptiveMemoryCache(capacity=5, base_ttl=30.0)
        cache.set("alpha", "consensus_v1")
        self.assertEqual(cache.get("alpha"), "consensus_v1")
        self.assertIsNone(cache.get("nonexistent"))

    def test_capacity_and_eviction(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=30.0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        # Access k1 to increase its frequency score
        cache.get("k1")
        
        # Adding k3 should trigger eviction of k2 (lower score)
        cache.set("k3", "v3")
        self.assertEqual(cache.get("k1"), "v1")
        self.assertIsNone(cache.get("k2"))
        self.assertEqual(cache.get("k3"), "v3")

    def test_expiration(self):
        cache = AdaptiveMemoryCache(capacity=5, base_ttl=0.01)
        cache.set("temp", "data")
        time.sleep(0.05)
        self.assertIsNone(cache.get("temp"))

    def test_thread_safety(self):
        cache = AdaptiveMemoryCache(capacity=100, base_ttl=10.0)
        def worker(thread_id: int):
            for i in range(50):
                key = f"t_{thread_id}_{i}"
                cache.set(key, i)
                cache.get(key)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        
        self.assertLessEqual(cache.stats()["size"], 100)


if __name__ == "__main__":
    unittest.main(argv=[''], exit=False, verbosity=2)