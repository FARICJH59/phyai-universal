from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Protocol
from uuid import UUID

from src.phase1_contracts.contracts import ControlCommand


@dataclass(frozen=True, slots=True)
class GovernedExecutionRequest:
    command: ControlCommand
    artifact_hash: str
    policy_context: Mapping[str, str]
    request_digest: str

    def __post_init__(self) -> None:
        if not self.artifact_hash.strip() or not self.request_digest.strip():
            raise ValueError("artifact_hash and request_digest are required")
        if self.command.tenant_id != self.policy_context.get("tenant_id"):
            raise PermissionError("tenant mismatch")
        if self.command.project_id != self.policy_context.get("project_id"):
            raise PermissionError("project mismatch")


@dataclass(frozen=True, slots=True)
class GovernedAdmission:
    accepted: bool
    attempt_id: UUID
    capability_id: str | None
    lease_id: str | None
    fence_id: str | None
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("admission reason is required")
        if self.accepted and not all((self.capability_id, self.lease_id, self.fence_id)):
            raise ValueError("accepted admission requires capability, lease, and fence")
        if not self.accepted and any((self.capability_id, self.lease_id, self.fence_id)):
            raise ValueError("denied admission cannot carry execution authority")


class HoareGovernanceTransport(Protocol):
    """Real transport boundary to an external HOARE/AEGIS/TCX deployment."""

    def admit(self, request: GovernedExecutionRequest) -> GovernedAdmission: ...


class GovernedHoareClient:
    """PHyAI client for the governed execution contract.

    This client never creates authority locally. Capability, lease, and fence
    identifiers are accepted only when returned by the configured HOARE
    transport after admission.
    """

    def __init__(self, transport: HoareGovernanceTransport) -> None:
        self._transport = transport

    @staticmethod
    def digest_request(command: ControlCommand, artifact_hash: str) -> str:
        canonical = "|".join(
            (
                command.tenant_id,
                command.project_id,
                str(command.command_id),
                str(command.attempt_id),
                str(command.sequence),
                command.target_id,
                command.command_type,
                artifact_hash,
            )
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    def admit(
        self,
        command: ControlCommand,
        artifact_hash: str,
        policy_context: Mapping[str, str],
    ) -> GovernedAdmission:
        request_digest = self.digest_request(command, artifact_hash)
        request = GovernedExecutionRequest(command, artifact_hash, policy_context, request_digest)
        admission = self._transport.admit(request)
        if admission.attempt_id != command.attempt_id:
            raise ValueError("HOARE admission attempt identity mismatch")
        return admission
