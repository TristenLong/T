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

            if key in self.cache:
                _, _, access_count, _ = self.cache[key]
                access_count += 1
            else:
                access_count = 1

            if len(self.cache) >= self.capacity and key not in self.cache:
                self._evict_optimal()

            ttl = self._calculate_adaptive_ttl(access_count)
            expiry = current_time + ttl
            self.cache[key] = (value, expiry, access_count, current_time)

    def get(self, key: str) -> Optional[Any]:
        """Retrieves an entry, updating access statistics and returning value if unexpired."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)

            if key not in self.cache:
                return None

            value, expiry, access_count, _ = self.cache[key]
            if current_time > expiry:
                del self.cache[key]
                return None

            # Update access telemetry
            new_access_count = access_count + 1
            new_ttl = self._calculate_adaptive_ttl(new_access_count)
            self.cache[key] = (value, current_time + new_ttl, new_access_count, current_time)
            return value

    def size(self) -> int:
        """Returns the current valid item count."""
        with self._lock:
            current_time = time.time()
            self._evict_expired(current_time)
            return len(self.cache)


class FleetConsensusAutomatedScript:
    """
    Automated Fleet Consensus Controller.
    Manages telemetry, state consensus loops, and high-load remediation triggers.
    """
    def __init__(self, cache_capacity: int = 50):
        self.cache = AdaptiveMemoryCache(capacity=cache_capacity)
        self.node_states: Dict[str, str] = {}
        self._state_lock = threading.Lock()

    def register_node_telemetry(self, node_id: str, load_metric: float, memory_pressure: float) -> str:
        """Evaluates node metrics and determines consensus action under pressure."""
        with self._state_lock:
            status = "HEALTHY"
            if load_metric > 85.0 or memory_pressure > 90.0:
                status = "CRITICAL_REMEDIATION_REQUIRED"
            elif load_metric > 70.0 or memory_pressure > 75.0:
                status = "WARNING"
            
            self.node_states[node_id] = status
            self.cache.set(f"node_telemetry:{node_id}", {"load": load_metric, "memory": memory_pressure, "status": status})
            return status

    def get_fleet_consensus(self) -> str:
        """Synthesizes fleet-wide status consensus."""
        with self._state_lock:
            if not self.node_states:
                return "IDLE"
            
            statuses = list(self.node_states.values())
            if any(s == "CRITICAL_REMEDIATION_REQUIRED" for s in statuses):
                return "EMERGENCY_ANOMALY_REMEDIATION"
            if any(s == "WARNING" for s in statuses):
                return "DEGRADED_OPERATION"
            return "OPTIMAL"


class TestAdaptiveCacheAndFleetConsensus(unittest.TestCase):
    def test_cache_basic_operations(self):
        cache = AdaptiveMemoryCache(capacity=2, base_ttl=5.0)
        cache.set("alpha", 100)
        cache.set("beta", 200)
        self.assertEqual(cache.get("alpha"), 100)
        self.assertEqual(cache.get("beta"), 200)
        
        # Test capacity enforcement and eviction
        cache.set("gamma", 300)
        self.assertEqual(cache.size(), 2)

    def test_fleet_consensus_workflow(self):
        controller = FleetConsensusAutomatedScript(cache_capacity=10)
        
        # Normal nodes
        s1 = controller.register_node_telemetry("node-1", 45.0, 50.0)
        s2 = controller.register_node_telemetry("node-2", 60.0, 55.0)
        self.assertEqual(s1, "HEALTHY")
        self.assertEqual(controller.get_fleet_consensus(), "OPTIMAL")

        # Trigger high resource pressure anomaly
        s3 = controller.register_node_telemetry("node-3", 92.0, 95.0)
        self.assertEqual(s3, "CRITICAL_REMEDIATION_REQUIRED")
        self.assertEqual(controller.get_fleet_consensus(), "EMERGENCY_ANOMALY_REMEDIATION")


if __name__ == "__main__":
    unittest.main(argv=[''], exit=False)