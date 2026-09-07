from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class RobustnessCase:
    name: str
    perturbation: Callable[[bytes], bytes]


@dataclass(frozen=True, slots=True)
class RobustnessResult:
    name: str
    baseline_digest: str
    perturbed_digest: str
    changed: bool


class SensorNoiseHarness:
    """Deterministic byte-level perturbation harness for sim-to-real evaluation."""

    @staticmethod
    def bit_flip(mask: int = 1) -> RobustnessCase:
        if not 0 <= mask <= 255:
            raise ValueError("mask must be between 0 and 255")

        def perturb(payload: bytes) -> bytes:
            if not payload:
                raise ValueError("payload must not be empty")
            data = bytearray(payload)
            data[0] ^= mask
            return bytes(data)

        return RobustnessCase("bit-flip", perturb)

    @staticmethod
    def evaluate(payload: bytes, case: RobustnessCase) -> RobustnessResult:
        if not payload:
            raise ValueError("payload must not be empty")
        baseline = sha256(payload).hexdigest()
        perturbed = sha256(case.perturbation(payload)).hexdigest()
        return RobustnessResult(case.name, baseline, perturbed, baseline != perturbed)
