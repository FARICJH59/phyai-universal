from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .multimodal import ModalityInput


@dataclass(frozen=True, slots=True)
class TensorModalityInput:
    """Explicit numeric representation for one synchronized modality."""

    modality: str
    features: Sequence[float]
    timestamp_ns: int
    confidence: float

    def __post_init__(self) -> None:
        if not self.modality.strip():
            raise ValueError("modality is required")
        if not self.features:
            raise ValueError("features must not be empty")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LearnedMultimodalRepresentation:
    tenant_id: str
    project_id: str
    timestamp_ns: int
    modality_order: tuple[str, ...]
    features: tuple[float, ...]
    confidence: float
    encoder_id: str

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        if not self.features:
            raise ValueError("features must not be empty")
        if not self.encoder_id.strip():
            raise ValueError("encoder_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


class ModalityEncoder(Protocol):
    def encode(self, modality: ModalityInput) -> TensorModalityInput: ...


class LearnedMultimodalEncoder(Protocol):
    encoder_id: str

    def fuse(
        self,
        tenant_id: str,
        project_id: str,
        inputs: Sequence[TensorModalityInput],
    ) -> LearnedMultimodalRepresentation: ...


class EncodedMultimodalFusion:
    """Explicit bridge from domain modalities into a learned representation.

    Domain payload bytes are never interpreted as tensors here. Each modality
    requires an injected encoder, after which a learned fusion backend receives
    only validated numeric representations.
    """

    def __init__(self, encoders: dict[str, ModalityEncoder], fusion: LearnedMultimodalEncoder) -> None:
        if not encoders:
            raise ValueError("encoders must not be empty")
        if not getattr(fusion, "encoder_id", "").strip():
            raise ValueError("fusion must expose an encoder_id")
        self._encoders = dict(encoders)
        self._fusion = fusion

    def fuse(
        self,
        tenant_id: str,
        project_id: str,
        inputs: Sequence[ModalityInput],
    ) -> LearnedMultimodalRepresentation:
        if not tenant_id.strip() or not project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        if not inputs:
            raise ValueError("inputs must not be empty")
        ordered = tuple(sorted(inputs, key=lambda item: (item.timestamp_ns, item.modality)))
        encoded: list[TensorModalityInput] = []
        for item in ordered:
            encoder = self._encoders.get(item.modality)
            if encoder is None:
                raise ValueError(f"no encoder registered for modality: {item.modality}")
            result = encoder.encode(item)
            if result.modality != item.modality:
                raise ValueError("modality encoder changed modality identity")
            encoded.append(result)
        result = self._fusion.fuse(tenant_id, project_id, tuple(encoded))
        if result.tenant_id != tenant_id or result.project_id != project_id:
            raise PermissionError("learned fusion changed tenant/project identity")
        if result.modality_order != tuple(item.modality for item in ordered):
            raise ValueError("learned fusion changed modality ordering")
        return result
