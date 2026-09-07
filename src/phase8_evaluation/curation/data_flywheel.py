from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from src.phase8_evaluation.evaluator import EvaluationResult


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    record_id: UUID
    tenant_id: str
    project_id: str
    result: EvaluationResult
    metadata: Mapping[str, str]


class DataFlywheel:
    """Immutable evaluation-record curation boundary for later training and analysis."""

    def curate(self, record: EvaluationRecord) -> EvaluationRecord:
        if not record.tenant_id.strip() or not record.project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        return record
