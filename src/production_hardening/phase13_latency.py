from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from time import perf_counter_ns
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class LatencySample:
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class EndToEndLatencyReport:
    samples: tuple[LatencySample, ...]
    mean_ms: float
    p95_ms: float
    maximum_ms: float
    target_ms: float
    passed: bool


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("latency values must not be empty")
    if not 0.0 <= percentile <= 100.0:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(float(x) for x in values)
    rank = (len(ordered) - 1) * percentile / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


class EndToEndLatencyHarness:
    """Measures a complete injected software control path; never claims hardware timing."""

    def __init__(self, target_ms: float = 50.0) -> None:
        if target_ms <= 0:
            raise ValueError("target_ms must be positive")
        self.target_ms = target_ms

    def measure(self, pipeline: Callable[[], object], iterations: int = 100) -> EndToEndLatencyReport:
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        samples: list[LatencySample] = []
        for _ in range(iterations):
            start = perf_counter_ns()
            pipeline()
            elapsed = (perf_counter_ns() - start) / 1_000_000
            samples.append(LatencySample(elapsed))
        values = tuple(sample.elapsed_ms for sample in samples)
        p95 = _percentile(values, 95.0)
        return EndToEndLatencyReport(
            samples=tuple(samples),
            mean_ms=mean(values),
            p95_ms=p95,
            maximum_ms=max(values),
            target_ms=self.target_ms,
            passed=p95 <= self.target_ms,
        )
