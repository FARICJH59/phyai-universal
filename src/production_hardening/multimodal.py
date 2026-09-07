from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ModalityInput:
    modality: str
    payload: bytes
    encoding: str
    timestamp_ns: int
    confidence: float

    def __post_init__(self) -> None:
        if not self.modality.strip() or not self.encoding.strip():
            raise ValueError("modality and encoding are required")
        if not self.payload:
            raise ValueError("payload must not be empty")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class UnifiedRepresentation:
    tenant_id: str
    project_id: str
    timestamp_ns: int
    modality_order: Sequence[str]
    feature_digest: str
    confidence: float


class MultimodalFusion:
    """Deterministic representation-space boundary for multimodal sensor fusion.

    The reference implementation hashes canonical modality metadata rather than
    pretending to be a learned latent encoder. Real encoders can replace it while
    retaining tenant/project isolation and temporal provenance.
    """

    def fuse(
        self,
        tenant_id: str,
        project_id: str,
        inputs: Sequence[ModalityInput],
    ) -> UnifiedRepresentation:
        if not tenant_id.strip() or not project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        if not inputs:
            raise ValueError("inputs must not be empty")
        ordered = tuple(sorted(inputs, key=lambda x: (x.timestamp_ns, x.modality)))
        canonical = b"|".join(
            f"{x.modality}:{x.encoding}:{x.timestamp_ns}:{x.confidence:.9f}:".encode()
            + sha256(x.payload).hexdigest().encode()
            for x in ordered
        )
        return UnifiedRepresentation(
            tenant_id=tenant_id,
            project_id=project_id,
            timestamp_ns=max(x.timestamp_ns for x in ordered),
            modality_order=tuple(x.modality for x in ordered),
            feature_digest=sha256(canonical).hexdigest(),
            confidence=min(x.confidence for x in ordered),
        )
