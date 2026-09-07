from typing import Protocol


class SpatialAcceleration(Protocol):
    """Optional acceleration boundary; implementations must preserve semantics."""

    def accelerate(self, representation: bytes) -> bytes: ...


class IdentitySpatialAcceleration:
    """Portable fallback used when CUDA is unavailable."""

    def accelerate(self, representation: bytes) -> bytes:
        if not representation:
            raise ValueError("representation must not be empty")
        return representation
