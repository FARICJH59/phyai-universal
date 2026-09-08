from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
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
        if self.request_digest != GovernedHoareClient.digest_request(self.command, self.artifact_hash, self.policy_context):
            raise ValueError("request digest mismatch")


@dataclass(frozen=True, slots=True)
class GovernedAdmission:
    accepted: bool
    attempt_id: UUID
    capability_id: str | None
    lease_id: str | None
    fence_id: str | None
    reason: str
    request_digest: str = ""

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("admission reason is required")
        if self.accepted and not all((self.capability_id, self.lease_id, self.fence_id)):
            raise ValueError("accepted admission requires capability, lease, and fence")
        if not self.accepted and any((self.capability_id, self.lease_id, self.fence_id)):
            raise ValueError("denied admission cannot carry execution authority")
        if self.accepted and not self.request_digest.strip():
            raise ValueError("accepted admission requires request digest")

    @classmethod
    def accepted_for(
        cls,
        command: ControlCommand,
        artifact_hash: str,
        policy_context: Mapping[str, str],
        capability_id: str,
        lease_id: str,
        fence_id: str,
        reason: str = "admitted",
    ) -> "GovernedAdmission":
        return cls(True, command.attempt_id, capability_id, lease_id, fence_id, reason, GovernedHoareClient.digest_request(command, artifact_hash, policy_context))


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
    def digest_request(
        command: ControlCommand,
        artifact_hash: str,
        policy_context: Mapping[str, str] | None = None,
    ) -> str:
        context = dict(policy_context or {})
        canonical = {
            "tenant_id": command.tenant_id,
            "project_id": command.project_id,
            "command_id": str(command.command_id),
            "attempt_id": str(command.attempt_id),
            "sequence": command.sequence,
            "proposed_at": command.proposed_at.isoformat(),
            "target_id": command.target_id,
            "command_type": command.command_type,
            "parameters": command.parameters,
            "confidence": command.confidence,
            "safety_precondition_ids": list(command.safety_precondition_ids),
            "scene_id": str(command.scene_id),
            "source_observation_ids": [str(item) for item in command.source_observation_ids],
            "provenance_uri": command.provenance_uri,
            "schema_version": command.schema_version,
            "artifact_hash": artifact_hash,
            "policy_context": {key: context[key] for key in sorted(context)},
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return sha256(payload).hexdigest()

    def admit(
        self,
        command: ControlCommand,
        artifact_hash: str,
        policy_context: Mapping[str, str],
    ) -> GovernedAdmission:
        request_digest = self.digest_request(command, artifact_hash, policy_context)
        request = GovernedExecutionRequest(command, artifact_hash, policy_context, request_digest)
        admission = self._transport.admit(request)
        if admission.attempt_id != command.attempt_id:
            raise ValueError("HOARE admission attempt identity mismatch")
        if admission.accepted and admission.request_digest != request_digest:
            raise ValueError("HOARE admission request binding mismatch")
        return admission
