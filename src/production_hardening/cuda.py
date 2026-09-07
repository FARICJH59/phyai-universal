from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class CudaKernelConfig:
    kernel_id: str
    block_size: int = 256

    def __post_init__(self) -> None:
        if not self.kernel_id.strip():
            raise ValueError("kernel_id is required")
        if self.block_size <= 0:
            raise ValueError("block_size must be positive")


class CudaKernelAdapter:
    """Explicit boundary for custom CUDA kernels.

    No Python fallback is mislabeled as CUDA. A compiled extension is injected
    and must expose `run(values)`.
    """

    def __init__(self, extension: object, config: CudaKernelConfig) -> None:
        self.extension = extension
        self.config = config

    def run(self, values: Sequence[float]) -> Sequence[float]:
        runner = getattr(self.extension, "run", None)
        if runner is None:
            raise RuntimeError("CUDA extension must expose run(values)")
        return tuple(float(x) for x in runner(values))
