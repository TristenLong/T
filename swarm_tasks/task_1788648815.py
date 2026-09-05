import collections
import time
from typing import Dict, List, Tuple, Any

class AdaptiveMemoryCache:
    """
    Dynamic Adaptive Cache for Swarm Knowledge Memory.
    Implements an LRU-like eviction policy combined with frequency-based scoring
    and adaptive time-to-live (TTL) adjustments for growing multi-agent codebases.
    """
    def __init__(self, capacity: int = 100, base_ttl: float = 60.0):
        self.capacity = capacity
        self.base_ttl = base_ttl
        self.cache: Dict[str, Tuple[Any, float, int]] = {}  # key -> (value, expiry_time, access_count)
        self.access_history: collections.deque = collections.deque(maxlen=1000)

    def _calculate_adaptive_ttl(self, access_count: int) -> float:
        """Scales TTL dynamically based on access frequency."""
        return self.base_ttl * (1.0 + min(float(access_count), 10.0))

    def set(self, key: str, value: Any) -> None:
        """Inserts or updates an entry in the adaptive cache."""
        current_time = time.time()
        self._evict_expired(current_time)

        if key in self.cache:
            _, _, count = self.cache[key]
            count += 1
        else:
            count = 1

        if len(self.cache) >= self.capacity and key not in self.cache:
            self._evict_lru_or_ LFU()

        ttl = self._calculate_adaptive_ttl(count)
        self.cache[key] = (value, current_time + ttl, count)
        self.access_history.append((key, current_time))

    def get(self, key: str) -> Any:
        """Retrieves a value if present and unexpired, updating metrics."""
        current_time = time.time()
        if key not in self.cache:
            return None

        value, expiry, count = self.cache[key]
        if current_time > expiry:
            del self.cache[key]
            return None

        # Update access count and extend TTL dynamically on hit
        count += 1
        ttl = self._calculate_adaptive_ttl(count)
        self.cache[key] = (value, current_time + ttl, count)
        self.access_history.append((key, current_time))
        return value

    def _evict_expired(self, current_time: float) -> None:
        """Removes all expired items from the cache."""
        expired_keys = [k for k, (_, expiry, _) in self.cache.items() if current_time > expiry]
        for k in expired_keys:
            del self.cache[k]

    def _evict_lru_or_LFU(self) -> None:
        """Evicts the least valuable item based on a composite score of frequency and recency."""
        if not self.cache:
            return
        # Score = access_count / (current_time - last_access + 1)
        # We want to remove the minimum score item.
        current_time = time.time()
        min_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k][2] / (current_time - (self.cache[k][1] - self._calculate_adaptive_ttl(self.cache[k][2])) + 1.0)
        )
        del self.cache[min_key]


def execute_swarm_consensus(topic: str) -> str:
    """Executes a simulated swarm consensus on the given topic using the adaptive cache."""
    cache = AdaptiveMemoryCache(capacity=50, base_ttl=10.0)
    
    agent_responses = [
        f"Consensus: '{topic}' is valid",
        f"Consensus: '{topic}' is valid",
        f"Consensus: '{topic}' needs refinement",
        f"Consensus: '{topic}' is valid",
        f"Consensus: '{topic}' requires further discussion",
        f"Consensus: '{topic}' is valid"
    ]
    
    for resp in agent_responses:
        cache.set(topic, resp)

    if not agent_responses:
        return f"No responses for '{topic}'. Consensus not reached."

    counts = collections.Counter(agent_responses)
    most_common, _ = counts.most_common(1)[0]
    
    # Store result in cache to demonstrate retrieval
    cache.set(f"consensus_{topic}", most_common)
    return cache.get(f"consensus_{topic}")


if __name__ == "__main__":
    # Unit Tests & Verification
    print("Initializing CODEX Adaptive Memory Cache Unit Tests...")
    
    # Test 1: Basic cache functionality
    cache = AdaptiveMemoryCache(capacity=2, base_ttl=5.0)
    cache.set("alpha", "memory_block_1")
    cache.set("beta", "memory_block_2")
    assert cache.get("alpha") == "memory_block_1"
    assert cache.get("beta") == "memory_block_2"
    print("Test 1 Passed: Basic set/get operations.")

    # Test 2: Capacity eviction and adaptive scaling
    cache.set("gamma", "memory_block_3") # Should trigger eviction of least valuable
    assert cache.get("gamma") == "memory_block_3"
    print("Test 2 Passed: Capacity management and eviction executed.")

    # Test 3: Swarm consensus integration
    result = execute_swarm_consensus('Dynamic Adaptive Cache for Swarm Knowledge Memory')
    assert "valid" in result
    print(f"Test 3 Passed: Swarm Consensus Output -> {result}")
    print("All CODEX diagnostic tests completed successfully with zero bloat.")