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
        for name, value in (("identity_digest", self.identity_digest), ("result_digest", self.result_digest), ("chain_digest", self.chain_digest)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.attempt_id, UUID):
            raise ValueError("attempt_id must be a UUID")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        if self.previous_receipt_digest is not None and (
            not isinstance(self.previous_receipt_digest, str) or not self.previous_receipt_digest.strip()
        ):
            raise ValueError("previous_receipt_digest must be a non-empty string when provided")
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



class SQLiteReceiptChainStore:
    """Persistent, transactionally append-only SQLite receipt-chain store.

    The database is scoped to one identity/attempt chain, matching the current
    Phase 18 contract. It is not a multi-host consensus or replication service.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS phase18_receipt_chain (
            ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_digest TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence >= 0),
            result_digest TEXT NOT NULL,
            previous_receipt_digest TEXT,
            chain_digest TEXT NOT NULL UNIQUE,
            UNIQUE(identity_digest, attempt_id, sequence)
        )
    """

    def __init__(self, database_path: str, *, timeout_seconds: float = 5.0) -> None:
        import math
        import os
        import sqlite3

        if not isinstance(database_path, str) or not database_path.strip():
            raise ValueError("database_path must be a non-empty filesystem path")
        if database_path == ":memory:":
            raise ValueError("SQLiteReceiptChainStore requires a persistent database file")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive finite number")
        self._database_path = os.fspath(database_path)
        self._timeout_seconds = float(timeout_seconds)
        with sqlite3.connect(self._database_path, timeout=self._timeout_seconds) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(self._SCHEMA)

    def append(self, entry: ReceiptChainEntry) -> None:
        import sqlite3

        if not isinstance(entry, ReceiptChainEntry):
            raise TypeError("entry must be a validated ReceiptChainEntry")
        connection = sqlite3.connect(
            self._database_path, timeout=self._timeout_seconds, isolation_level=None
        )
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                """
                SELECT identity_digest, attempt_id, sequence, chain_digest
                FROM phase18_receipt_chain ORDER BY ordinal DESC LIMIT 1
                """
            ).fetchone()
            if previous is None:
                if entry.previous_receipt_digest is not None:
                    raise ValueError("first receipt must reference genesis")
            else:
                previous_identity, previous_attempt, previous_sequence, previous_digest = previous
                if entry.previous_receipt_digest != previous_digest:
                    raise ValueError("receipt chain predecessor mismatch")
                if entry.identity_digest != previous_identity:
                    raise ValueError("receipt chain identity mismatch")
                if str(entry.attempt_id) != previous_attempt:
                    raise ValueError("receipt chain attempt mismatch")
                if entry.sequence <= previous_sequence:
                    raise ValueError("receipt chain sequence must increase")
            connection.execute(
                """
                INSERT INTO phase18_receipt_chain
                    (identity_digest, attempt_id, sequence, result_digest,
                     previous_receipt_digest, chain_digest)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.identity_digest, str(entry.attempt_id), entry.sequence,
                    entry.result_digest, entry.previous_receipt_digest, entry.chain_digest,
                ),
            )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ValueError("duplicate receipt chain entry") from exc
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def entries(self) -> tuple[ReceiptChainEntry, ...]:
        import sqlite3

        with sqlite3.connect(self._database_path, timeout=self._timeout_seconds) as connection:
            rows = connection.execute(
                """
                SELECT identity_digest, attempt_id, sequence, result_digest,
                       previous_receipt_digest, chain_digest
                FROM phase18_receipt_chain ORDER BY ordinal ASC
                """
            ).fetchall()
        return tuple(
            ReceiptChainEntry(
                identity_digest=row[0],
                attempt_id=UUID(row[1]),
                sequence=row[2],
                result_digest=row[3],
                previous_receipt_digest=row[4],
                chain_digest=row[5],
            )
            for row in rows
        )
