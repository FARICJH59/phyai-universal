from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from uuid import UUID

from src.phase1_contracts.contracts import ControlCommand


@dataclass(frozen=True, slots=True)
class ExecutionProposal:
    """Transport envelope from PHyAI into HOARE; it carries proposal, not authority."""

    command: ControlCommand
    artifact_hash: str
    policy_context: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.artifact_hash.strip():
            raise ValueError("artifact_hash is required")
        if any(not k.strip() for k in self.policy_context):
            raise ValueError("policy context keys must be non-empty")


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    accepted: bool
    attempt_id: UUID
    reason: str


class HoareAdmissionClient(Protocol):
    def submit_proposal(self, proposal: ExecutionProposal) -> AdmissionDecision: ...


class HoareExecutionBoundary:
    """Explicit PHyAI→HOARE boundary.

    PHyAI can submit a ControlCommand proposal. It cannot mint authorization,
    capabilities, leases, fences, dispatch identities, or execution receipts.
    The injected client is the only path to admission.
    """

    def __init__(self, client: HoareAdmissionClient) -> None:
        self._client = client

    def submit(self, proposal: ExecutionProposal) -> AdmissionDecision:
        if proposal.command.tenant_id != proposal.policy_context.get("tenant_id"):
            raise PermissionError("tenant mismatch")
        if proposal.command.project_id != proposal.policy_context.get("project_id"):
            raise PermissionError("project mismatch")
        return self._client.submit_proposal(proposal)
