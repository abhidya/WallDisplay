"""Lightweight performance smoke tests for helper code.

This file intentionally avoids external load-test frameworks during normal
pytest runs. The repo no longer treats Locust as required test infrastructure.
"""

from dataclasses import dataclass
import statistics

import pytest


@dataclass
class PerformanceMetrics:
    operation: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    p95_time: float
    p99_time: float
    requests_per_second: float


@pytest.mark.performance
def test_performance_metrics_container_round_trips_values():
    metrics = PerformanceMetrics(
        operation="sample",
        total_requests=10,
        successful_requests=9,
        failed_requests=1,
        min_time=0.1,
        max_time=0.9,
        avg_time=0.4,
        median_time=0.35,
        p95_time=0.8,
        p99_time=0.9,
        requests_per_second=25.0,
    )

    assert metrics.operation == "sample"
    assert metrics.total_requests == 10
    assert metrics.successful_requests == 9
    assert metrics.failed_requests == 1
    assert metrics.requests_per_second == 25.0


@pytest.mark.performance
def test_basic_percentile_calculation_shape():
    samples = [0.1, 0.2, 0.3, 0.4, 0.5]
    samples.sort()

    assert statistics.mean(samples) == pytest.approx(0.3)
    assert statistics.median(samples) == pytest.approx(0.3)
    assert samples[int(len(samples) * 0.95)] == pytest.approx(0.5)
    assert samples[int(len(samples) * 0.99)] == pytest.approx(0.5)
