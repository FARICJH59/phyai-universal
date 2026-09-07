from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Critique:
    passed: bool
    score: float
    reasons: tuple[str, ...]


class DeterministicCritic:
    """Framework-neutral critic; model/VLM critics can implement the same boundary."""

    def critique(self, metrics: Mapping[str, float], *, tolerance: float = 0.05) -> Critique:
        error = float(metrics.get("max_absolute_error", float("inf")))
        if error < 0:
            raise ValueError("error metric must be non-negative")
        score = max(0.0, 1.0 - min(error, 1.0))
        return Critique(error <= tolerance, score, () if error <= tolerance else ("parameter_error_above_tolerance",))
