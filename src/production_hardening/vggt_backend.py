from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class VGGTBackendConfig:
    model_id: str = "vggt"
    device: str = "cuda"


class VGGTBackend:
    """Optional adapter for a real VGGT-compatible model.

    The repository's contract layer remains model-agnostic. This adapter requires
    an injected callable/model object and never substitutes the deterministic
    Phase-5 reference predictor for real inference.
    """

    def __init__(self, predictor: Any, config: VGGTBackendConfig | None = None) -> None:
        self.predictor = predictor
        self.config = config or VGGTBackendConfig()

    def predict(self, inputs: Sequence[Any]) -> Any:
        if not inputs:
            raise ValueError("VGGT inputs must not be empty")
        if hasattr(self.predictor, "predict"):
            return self.predictor.predict(inputs)
        if callable(self.predictor):
            return self.predictor(inputs)
        raise TypeError("predictor must be callable or expose predict()")
