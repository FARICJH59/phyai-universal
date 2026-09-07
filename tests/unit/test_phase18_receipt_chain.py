from uuid import uuid4

import pytest

from src.production_hardening.phase18_receipt_chain import (
    InMemoryReceiptChainStore,
    ReceiptChain,
    ReceiptChainEntry,
    ReceiptChainVerifier,
)


def test_chain_is_deterministic_and_links_predecessor() -> None:
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    attempt = uuid4()

    first = chain.append(identity_digest="identity", attempt_id=attempt, sequence=1, result_digest="result-a")
    second = chain.append(identity_digest="identity", attempt_id=attempt, sequence=2, result_digest="result-b")

    assert first.previous_receipt_digest is None
    assert second.previous_receipt_digest == first.chain_digest
    assert ReceiptChainVerifier().verify(store.entries()).valid


def test_chain_rejects_identity_rebinding() -> None:
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    attempt = uuid4()
    chain.append(identity_digest="identity-a", attempt_id=attempt, sequence=1, result_digest="result")

    with pytest.raises(ValueError, match="identity mismatch"):
        chain.append(identity_digest="identity-b", attempt_id=attempt, sequence=2, result_digest="result")


def test_chain_rejects_sequence_replay() -> None:
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    attempt = uuid4()
    chain.append(identity_digest="identity", attempt_id=attempt, sequence=4, result_digest="result-a")

    with pytest.raises(ValueError, match="sequence must increase"):
        chain.append(identity_digest="identity", attempt_id=attempt, sequence=4, result_digest="result-b")


def test_tampered_entry_fails_closed() -> None:
    attempt = uuid4()
    entry = ReceiptChainEntry(
        identity_digest="identity",
        attempt_id=attempt,
        sequence=1,
        result_digest="result",
        previous_receipt_digest=None,
        chain_digest=ReceiptChainEntry.compute_digest("identity", attempt, 1, "result", None),
    )
    tampered = ReceiptChainEntry.__new__(ReceiptChainEntry)
    object.__setattr__(tampered, "identity_digest", entry.identity_digest)
    object.__setattr__(tampered, "attempt_id", entry.attempt_id)
    object.__setattr__(tampered, "sequence", entry.sequence)
    object.__setattr__(tampered, "result_digest", "tampered-result")
    object.__setattr__(tampered, "previous_receipt_digest", entry.previous_receipt_digest)
    object.__setattr__(tampered, "chain_digest", entry.chain_digest)

    report = ReceiptChainVerifier().verify((tampered,))
    assert not report.valid
    assert report.entries_verified == 0


def test_empty_chain_is_valid_genesis_state() -> None:
    report = ReceiptChainVerifier().verify(())
    assert report.valid
    assert report.entries_verified == 0
    assert report.terminal_digest is None
