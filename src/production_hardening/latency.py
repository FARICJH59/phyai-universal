from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Callable, Generic, Sequence, TypeVar


T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class LatencyMeasurement:
    samples_ms: tuple[float, ...]
    average_ms: float
    p95_ms: float
    maximum_ms: float
    target_ms: float
    passed: bool


class ControlLoopLatencyHarness(Generic[T, U]):
    """Measure an actual sensor-to-proposal pipeline without simulating timing."""

    def __init__(
        self,
        pipeline: Callable[[T], U],
        target_ms: float = 50.0,
    ) -> None:
        if target_ms <= 0:
            raise ValueError("target_ms must be positive")
        self.pipeline = pipeline
        self.target_ms = target_ms

    def measure(self, inputs: Sequence[T], warmup: int = 0) -> LatencyMeasurement:
        if not inputs:
            raise ValueError("inputs must not be empty")
        if warmup < 0:
            raise ValueError("warmup must not be negative")

        for value in inputs[:warmup]:
            self.pipeline(value)

        samples: list[float] = []
        for value in inputs[warmup:]:
            start = perf_counter_ns()
            self.pipeline(value)
            samples.append((perf_counter_ns() - start) / 1_000_000)

        if not samples:
            raise ValueError("warmup consumed all inputs")

        ordered = sorted(samples)
        # Nearest-rank p95: rank = ceil(0.95 * N), converted to zero-based index.
        p95_rank = max(1, int(len(ordered) * 0.95 + 0.999999999))
        p95_index = min(len(ordered) - 1, p95_rank - 1)
        average = sum(samples) / len(samples)
        maximum = max(samples)
        p95 = ordered[p95_index]
        return LatencyMeasurement(
            samples_ms=tuple(samples),
            average_ms=average,
            p95_ms=p95,
            maximum_ms=maximum,
            target_ms=self.target_ms,
            passed=p95 <= self.target_ms,
        )
