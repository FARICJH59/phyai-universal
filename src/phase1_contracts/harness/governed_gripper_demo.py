"""Simulation-only governed gripper demonstration.

This harness uses an injected mock authorization provider and verifier. It is not
a production HOARE/AEGIS client, a cryptographic verifier, or a robot driver.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter_ns
from typing import Callable
from uuid import UUID

from src.phase1_contracts.contracts.contracts import ControlCommand


@dataclass(frozen=True, slots=True)
class MockAuthorizationResult:
    decision: str
    tenant_id: str
    project_id: str
    command_id: UUID
    attempt_id: UUID
    target_id: str
    command_type: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
    # Test-only marker. It is deliberately not described as a signature.
    proof: bytes = b"simulation-only"


@dataclass(frozen=True, slots=True)
class DemoResult:
    status: str
    reason: str
    actuation_attempted: bool
    evidence: tuple[dict[str, str], ...]
    elapsed_ns: int


AuthorizationProvider = Callable[[ControlCommand], MockAuthorizationResult]
AuthorizationVerifier = Callable[[MockAuthorizationResult], bool]
Clock = Callable[[], datetime]


@dataclass(slots=True)
class SimulatedGripper:
    """A bounded in-memory target; it cannot connect to physical hardware."""

    target_id: str = "sim-gripper-1"
    position_mm: float = 80.0
    attempts: list[float] = field(default_factory=list)

    def actuate(self, command: ControlCommand) -> float:
        if command.target_id != self.target_id:
            raise ValueError("target mismatch")
        if command.command_type != "set_gripper_position_mm":
            raise ValueError("unsupported simulated command")
        position = command.parameters.get("position_mm")
        if not isinstance(position, (int, float)) or isinstance(position, bool):
            raise ValueError("position_mm must be numeric")
        if not 0.0 <= float(position) <= 80.0:
            raise ValueError("position_mm outside simulated gripper limits")
        self.attempts.append(float(position))
        self.position_mm = float(position)
        return self.position_mm


class GovernedGripperDemo:
    """Exercise fail-closed admission in a simulation-only target adapter."""

    def __init__(
        self,
        gripper: SimulatedGripper,
        authorization_provider: AuthorizationProvider,
        authorization_verifier: AuthorizationVerifier,
        *,
        now: Clock,
        max_command_age: timedelta = timedelta(seconds=2),
    ) -> None:
        self.gripper = gripper
        self.authorization_provider = authorization_provider
        self.authorization_verifier = authorization_verifier
        self.now = now
        self.max_command_age = max_command_age
        self._seen_attempts: set[UUID] = set()

    def execute(self, command: ControlCommand) -> DemoResult:
        started = perf_counter_ns()
        evidence: list[dict[str, str]] = []

        def finish(status: str, reason: str, attempted: bool) -> DemoResult:
            evidence.append({
                "event": "decision",
                "status": status,
                "reason": reason,
                "attempt_id": str(command.attempt_id),
                "command_id": str(command.command_id),
            })
            return DemoResult(
                status=status,
                reason=reason,
                actuation_attempted=attempted,
                evidence=tuple(evidence),
                elapsed_ns=perf_counter_ns() - started,
            )

        now_value = self.now()
        if now_value.tzinfo is None or now_value.utcoffset() is None:
            return finish("DENY", "invalid_clock", False)
        now = now_value.astimezone(timezone.utc)
        proposed_value = command.proposed_at
        if proposed_value.tzinfo is None or proposed_value.utcoffset() is None:
            return finish("DENY", "invalid_proposal_timestamp", False)
        proposed_at = proposed_value.astimezone(timezone.utc)
        if now < proposed_at or now - proposed_at > self.max_command_age:
            return finish("DENY", "stale_or_future_proposal", False)

        if command.attempt_id in self._seen_attempts:
            return finish("DENY", "replayed_attempt", False)
        # Consume attempt identity before contacting admission, including failures.
        self._seen_attempts.add(command.attempt_id)

        try:
            authorization = self.authorization_provider(command)
        except Exception:
            return finish("DENY", "authorization_unavailable", False)

        try:
            verified = self.authorization_verifier(authorization)
        except Exception:
            verified = False
        if not verified:
            return finish("DENY", "authorization_verification_failed", False)
        if authorization.revoked:
            return finish("DENY", "authorization_revoked", False)
        if authorization.decision != "ALLOW":
            return finish("DENY", f"authorization_{authorization.decision.lower()}", False)

        exact_binding = (
            authorization.tenant_id == command.tenant_id
            and authorization.project_id == command.project_id
            and authorization.command_id == command.command_id
            and authorization.attempt_id == command.attempt_id
            and authorization.target_id == command.target_id
            and authorization.command_type == command.command_type
        )
        if not exact_binding:
            return finish("DENY", "authorization_binding_mismatch", False)

        issued_value = authorization.issued_at
        expires_value = authorization.expires_at
        if (
            issued_value.tzinfo is None or issued_value.utcoffset() is None
            or expires_value.tzinfo is None or expires_value.utcoffset() is None
        ):
            return finish("DENY", "authorization_expired_or_invalid_window", False)
        issued_at = issued_value.astimezone(timezone.utc)
        expires_at = expires_value.astimezone(timezone.utc)
        if issued_at > now or expires_at <= now or expires_at <= issued_at:
            return finish("DENY", "authorization_expired_or_invalid_window", False)

        try:
            position = self.gripper.actuate(command)
        except (TypeError, ValueError):
            return finish("DENY", "target_rejected_command", False)

        evidence.append({
            "event": "simulated_actuation",
            "target_id": self.gripper.target_id,
            "position_mm": str(position),
            "attempt_id": str(command.attempt_id),
            "command_id": str(command.command_id),
        })
        return finish("ALLOW", "simulated_actuation_completed", True)
