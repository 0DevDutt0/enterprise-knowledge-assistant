# app/api/metrics.py
from __future__ import annotations

import threading


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of data. Returns 0.0 for empty input."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = max(0, int(len(sorted_data) * p / 100.0) - 1)
    return sorted_data[min(idx, len(sorted_data) - 1)]


class MetricsStore:
    """Thread-safe in-memory store for request counts and latency percentiles.

    Records /ask and /rebuild-index request latencies so the /metrics endpoint
    can expose p50 and p95 without an external time-series system.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ask_latencies: list[float] = []
        self._ask_count: int = 0
        self._rebuild_latencies: list[float] = []
        self._rebuild_count: int = 0

    def record_ask(self, elapsed_ms: float) -> None:
        """Record a completed /ask request with its total latency."""
        with self._lock:
            self._ask_latencies.append(elapsed_ms)
            self._ask_count += 1

    def record_rebuild(self, elapsed_ms: float) -> None:
        """Record a completed /rebuild-index request with its total latency."""
        with self._lock:
            self._rebuild_latencies.append(elapsed_ms)
            self._rebuild_count += 1

    def snapshot(self) -> dict[str, object]:
        """Return a point-in-time snapshot of all metrics.

        Returns:
            Dict with request counts and p50/p95 latencies in milliseconds.
        """
        with self._lock:
            ask_lats = list(self._ask_latencies)
            ask_count = self._ask_count
            rebuild_lats = list(self._rebuild_latencies)
            rebuild_count = self._rebuild_count

        return {
            'ask_request_count': ask_count,
            'ask_p50_ms': _percentile(ask_lats, 50),
            'ask_p95_ms': _percentile(ask_lats, 95),
            'rebuild_request_count': rebuild_count,
            'rebuild_p50_ms': _percentile(rebuild_lats, 50),
            'rebuild_p95_ms': _percentile(rebuild_lats, 95),
        }
