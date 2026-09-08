from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from src.production_hardening.phase17_evidence import DurableReceipt


@dataclass(frozen=True, slots=True)
class ReceiptChainEntry:
    """One tamper-evident link in a governed execution receipt chain."""

    identity_digest: str
    attempt_id: UUID
    sequence: int
    result_digest: str
    previous_receipt_digest: str | None
    chain_digest: str

    def __post_init__(self) -> None:
        for name, value in (("identity_digest", self.identity_digest), ("result_digest", self.result_digest)):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if self.sequence < 0:
            raise ValueError("sequence must be nonnegative")
        if self.previous_receipt_digest is not None and not self.previous_receipt_digest.strip():
            raise ValueError("previous_receipt_digest cannot be empty")
        if self.chain_digest != self.compute_digest(self.identity_digest, self.attempt_id, self.sequence, self.result_digest, self.previous_receipt_digest):
            raise ValueError("chain digest mismatch")

    @staticmethod
    def compute_digest(identity_digest: str, attempt_id: UUID, sequence: int, result_digest: str, previous_receipt_digest: str | None) -> str:
        canonical = "|".join((identity_digest, str(attempt_id), str(sequence), result_digest, previous_receipt_digest or "GENESIS"))
        return sha256(canonical.encode("utf-8")).hexdigest()


class ReceiptChainStore(Protocol):
    def append(self, entry: ReceiptChainEntry) -> None: ...
    def entries(self) -> tuple[ReceiptChainEntry, ...]: ...


class InMemoryReceiptChainStore:
    """Reference append-only store; production storage is injected at the boundary."""

    def __init__(self) -> None:
        self._entries: list[ReceiptChainEntry] = []

    def append(self, entry: ReceiptChainEntry) -> None:
        if self._entries:
            previous = self._entries[-1]
            if entry.previous_receipt_digest != previous.chain_digest:
                raise ValueError("receipt chain predecessor mismatch")
            if entry.identity_digest != previous.identity_digest:
                raise ValueError("receipt chain identity mismatch")
            if entry.attempt_id != previous.attempt_id:
                raise ValueError("receipt chain attempt mismatch")
            if entry.sequence <= previous.sequence:
                raise ValueError("receipt chain sequence must increase")
        elif entry.previous_receipt_digest is not None:
            raise ValueError("first receipt must reference genesis")
        self._entries.append(entry)

    def entries(self) -> tuple[ReceiptChainEntry, ...]:
        return tuple(self._entries)


@dataclass(frozen=True, slots=True)
class ReceiptChainVerification:
    valid: bool
    entries_verified: int
    terminal_digest: str | None
    reason: str


class ReceiptChainVerifier:
    """Fail-closed verifier for ordering, identity binding, and predecessor integrity."""

    def verify(self, entries: tuple[ReceiptChainEntry, ...]) -> ReceiptChainVerification:
        previous: ReceiptChainEntry | None = None
        for entry in entries:
            try:
                ReceiptChainEntry(identity_digest=entry.identity_digest, attempt_id=entry.attempt_id, sequence=entry.sequence, result_digest=entry.result_digest, previous_receipt_digest=entry.previous_receipt_digest, chain_digest=entry.chain_digest)
            except ValueError as exc:
                return ReceiptChainVerification(False, 0, None, str(exc))
            if previous is None:
                if entry.previous_receipt_digest is not None:
                    return ReceiptChainVerification(False, 0, None, "invalid genesis predecessor")
            else:
                if entry.previous_receipt_digest != previous.chain_digest:
                    return ReceiptChainVerification(False, 0, previous.chain_digest, "predecessor digest mismatch")
                if entry.identity_digest != previous.identity_digest:
                    return ReceiptChainVerification(False, 0, previous.chain_digest, "identity changed within chain")
                if entry.attempt_id != previous.attempt_id:
                    return ReceiptChainVerification(False, 0, previous.chain_digest, "attempt changed within chain")
                if entry.sequence <= previous.sequence:
                    return ReceiptChainVerification(False, 0, previous.chain_digest, "sequence regression")
            previous = entry
        return ReceiptChainVerification(True, len(entries), previous.chain_digest if previous else None, "valid")


class ReceiptChain:
    """Builds append-only receipt links from verified Phase 17 durable receipts."""

    def __init__(self, store: ReceiptChainStore) -> None:
        self._store = store

    def append(self, receipt: DurableReceipt) -> ReceiptChainEntry:
        existing = self._store.entries()
        previous = existing[-1] if existing else None
        entry = ReceiptChainEntry(
            identity_digest=receipt.identity_digest,
            attempt_id=receipt.attempt_id,
            sequence=receipt.sequence,
            result_digest=receipt.result_digest,
            previous_receipt_digest=previous.chain_digest if previous else None,
            chain_digest=ReceiptChainEntry.compute_digest(receipt.identity_digest, receipt.attempt_id, receipt.sequence, receipt.result_digest, previous.chain_digest if previous else None),
        )
        self._store.append(entry)
        return entry
