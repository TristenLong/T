import collections
import time
import unittest
from typing import Dict, Tuple, Any, Optional

class AdaptiveMemoryCache:
    """
    Dynamic Adaptive Cache for Swarm Knowledge Memory.
    Implements a hybrid LRU/LFU eviction policy combined with frequency-based scoring
    and adaptive time-to-live (TTL) adjustments for growing multi-agent codebases.
    """
    def __init__(self, capacity: int = 100, base_ttl: float = 60.0):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than zero.")
        self.capacity = capacity
        self.base_ttl = base_ttl
        # key -> (value, expiry_time, access_count, last_access_time)
        self.cache: Dict[str, Tuple[Any, float, int, float]] = {}

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
        # Find key with the lowest score
        victim_key = min(
            self.cache.keys(),
            key=lambda k: (self.cache[k][2] / (current_time - self.cache[k][3] + 1e-5), self.cache[k][3])
        )
        del self.cache[victim_key]

    def set(self, key: str, value: Any) -> None:
        """Inserts or updates an entry in the adaptive cache."""
        current_time = time.time()
        self._evict_expired(current_time)

        if key in self.cache:
            _, _, count, _ = self.cache[key]
            count += 1
        else:
            count = 1

        if len(self.cache) >= self.capacity and key not in self.cache:
            self._evict_optimal()

        ttl = self._calculate_adaptive_ttl(count)
        self.cache[key] = (value, current_time + ttl, count, current_time)

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a value if present and unexpired, updating metrics."""
        current_time = time.time()
        self._evict_expired(current_time)

        if key not in self.cache:
            return None

        value, expiry, count, _ = self.cache[key]
        if current_time > expiry:
            del self.cache[key]
            return None

        # Update access count, extend TTL dynamically, and refresh last access time
        count += 1
        ttl = self._calculate_adaptive_ttl(count)
        self.cache[key] = (value, current_time + ttl, count, current_time)
        return value

    def __len__(self) -> int:
        current_time = time.time()
        self._evict_expired(current_time)
        return len(self.cache)


class TestAdaptiveMemoryCache(unittest.TestCase):
    def test_basic_set_and_get(self):
        cache = AdaptiveMemoryCache(capacity=10, base_ttl=10.0)
        cache.set("agent_state", "active")
        self.assertEqual(cache.get("agent_state"), "active")

    def test_capacity_eviction(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=10.0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        # Access k1 to increase its score/recency
        cache.get("k1")
        
        # Adding k3 should trigger eviction of k2 (lower relative score/recency)
        cache.set("k3", "v3")
        
        self.assertIsNotNone(cache.get("k1"))
        self.assertIsNotNone(cache.get("k3"))
        self.assertIsNone(cache.get("k2"))

    def test_ttl_expiration(self):
        # Extremely short TTL to test forced expiration
        cache = AdaptiveMemoryCache(capacity=5, base_ttl=0.001)
        cache.set("temp", "data")
        time.sleep(0.01)
        self.assertIsNone(cache.get("temp"))

    def test_adaptive_ttl_scaling(self):
        cache = AdaptiveMemoryCache(capacity=5, base_ttl=1.0)
        cache.set("frequent", "val")
        # Simulate multiple hits to scale TTL
        for _ in range(5):
            cache.get("frequent")
        
        # Check internal storage structure to ensure count increased
        _, expiry, count, _ = cache.cache["frequent"]
        self.assertGreater(count, 1)


if __name__ == "__main__":
    unittest.main(argv=[''], exit=False)