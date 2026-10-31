from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import (
    GovernedHoareClient,
    TransportAdmission,
)
from src.production_hardening.phase17_evidence import (
    DurableReceipt,
    ExecutionEvidence,
    ExecutionIdentity,
    EvidenceVerifier,
    HMACSHA256Signer,
    InMemoryEvidenceStore,
    sign_admission,
)
from src.production_hardening.phase18_receipt_chain import (
    InMemoryReceiptChainStore,
    ReceiptChain,
    ReceiptChainEntry,
    ReceiptChainVerifier,
)


def verified_receipts_pair():
    command = ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(), sequence=1,
        proposed_at=datetime.now(timezone.utc), target_id="arm-1", command_type="position", parameters={"x": 0.1},
        confidence=0.95, safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )
    context = {"tenant_id": "tenant-a", "project_id": "project-a", "policy_digest": "policy"}
    artifact_hash = "artifact"
    request_digest = GovernedHoareClient.digest_request(command, artifact_hash, context)

    class _Transport:
        def admit(self, request):
            return TransportAdmission(
                accepted=True,
                attempt_id=request.command.attempt_id,
                capability_id="cap-1",
                lease_id="lease-1",
                fence_id="fence-1",
                reason="admitted",
                request_digest=request.request_digest,
            )

    admission = GovernedHoareClient(_Transport()).admit(command, artifact_hash, context)
    assert admission.request_digest == request_digest
    identity = ExecutionIdentity.from_governed_admission(command, "artifact", "policy", admission, policy_context=context)
    signer = HMACSHA256Signer("key-1", b"secret")
    signed = sign_admission(identity, signer)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    first = verifier.commit_verified_evidence(signed, ExecutionEvidence(identity.digest(), command.attempt_id, "jetson-1", 1, 10, "result-a", signed.signature), signer, expected_device_id="jetson-1")
    second = verifier.commit_verified_evidence(signed, ExecutionEvidence(identity.digest(), command.attempt_id, "jetson-1", 2, 11, "result-b", signed.signature), signer, expected_device_id="jetson-1")
    return first, second


def test_chain_links_verified_receipts():
    first, second = verified_receipts_pair()
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    first_entry = chain.append(first)
    second_entry = chain.append(second)
    assert first_entry.previous_receipt_digest is None
    assert second_entry.previous_receipt_digest == first_entry.chain_digest
    assert ReceiptChainVerifier().verify(store.entries()).valid


def test_chain_rejects_unverified_receipt_construction():
    attempt = uuid4()
    digest = DurableReceipt.compute_digest("identity", attempt, 1, "result")
    with pytest.raises(PermissionError, match="must originate from verified evidence"):
        DurableReceipt("identity", attempt, 1, "result", digest)


def test_chain_rejects_identity_rebinding():
    first, _ = verified_receipts_pair()
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    first_entry = chain.append(first)
    forged = ReceiptChainEntry(
        identity_digest="identity-b", attempt_id=first.attempt_id, sequence=2, result_digest="result-b",
        previous_receipt_digest=first_entry.chain_digest,
        chain_digest=ReceiptChainEntry.compute_digest("identity-b", first.attempt_id, 2, "result-b", first_entry.chain_digest),
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        store.append(forged)


def test_chain_rejects_sequence_replay():
    first, _ = verified_receipts_pair()
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    chain.append(first)
    with pytest.raises(ValueError, match="sequence must increase"):
        chain.append(first)


def test_tampered_entry_fails_closed():
    attempt = uuid4()
    entry = ReceiptChainEntry("identity", attempt, 1, "result", None, ReceiptChainEntry.compute_digest("identity", attempt, 1, "result", None))
    tampered = ReceiptChainEntry.__new__(ReceiptChainEntry)
    object.__setattr__(tampered, "identity_digest", entry.identity_digest)
    object.__setattr__(tampered, "attempt_id", entry.attempt_id)
    object.__setattr__(tampered, "sequence", entry.sequence)
    object.__setattr__(tampered, "result_digest", "tampered-result")
    object.__setattr__(tampered, "previous_receipt_digest", entry.previous_receipt_digest)
    object.__setattr__(tampered, "chain_digest", entry.chain_digest)
    report = ReceiptChainVerifier().verify((tampered,))
    assert not report.valid and report.entries_verified == 0


def test_empty_chain_is_valid_genesis_state():
    report = ReceiptChainVerifier().verify(())
    assert report.valid and report.entries_verified == 0 and report.terminal_digest is None


@pytest.mark.parametrize("sequence", [True, -1, 1.5, "2"])
def test_receipt_chain_entry_rejects_invalid_sequence_types(sequence):
    attempt = uuid4()
    digest = ReceiptChainEntry.compute_digest("identity", attempt, sequence, "result", None)
    with pytest.raises(ValueError, match="sequence"):
        ReceiptChainEntry("identity", attempt, sequence, "result", None, digest)


@pytest.mark.parametrize("attempt_id", ["not-a-uuid", None, 1])
def test_receipt_chain_entry_requires_uuid_attempt(attempt_id):
    with pytest.raises(ValueError, match="attempt_id"):
        ReceiptChainEntry("identity", attempt_id, 1, "result", None, "digest")


@pytest.mark.parametrize(
    "field_values, message",
    [
        ((None, "result", "chain"), "identity_digest"),
        (("identity", None, "chain"), "result_digest"),
        (("identity", "result", None), "chain_digest"),
    ],
)
def test_receipt_chain_entry_requires_nonempty_string_digests(field_values, message):
    identity_digest, result_digest, chain_digest = field_values
    with pytest.raises(ValueError, match=message):
        ReceiptChainEntry(identity_digest, uuid4(), 1, result_digest, None, chain_digest)


@pytest.mark.parametrize("previous", ["", 1, None])
def test_receipt_chain_entry_validates_optional_predecessor_type(previous):
    if previous is None:
        pytest.skip("None is the valid genesis predecessor")
    with pytest.raises(ValueError, match="previous_receipt_digest"):
        ReceiptChainEntry("identity", uuid4(), 1, "result", previous, "digest")



def test_sqlite_receipt_chain_persists_ordered_chain_across_reopen(tmp_path):
    from src.production_hardening.phase18_receipt_chain import SQLiteReceiptChainStore

    first, second = verified_receipts_pair()
    database_path = str(tmp_path / "phase18-chain.sqlite3")
    first_store = SQLiteReceiptChainStore(database_path)
    chain = ReceiptChain(first_store)
    first_entry = chain.append(first)
    second_entry = chain.append(second)
    assert second_entry.previous_receipt_digest == first_entry.chain_digest

    reopened_store = SQLiteReceiptChainStore(database_path)
    restored = reopened_store.entries()
    assert len(restored) == 2
    assert restored[0] == first_entry
    assert restored[1] == second_entry
    assert ReceiptChainVerifier().verify(restored).valid


def test_sqlite_receipt_chain_serializes_competing_genesis_appends(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.production_hardening.phase18_receipt_chain import SQLiteReceiptChainStore

    first, _ = verified_receipts_pair()
    database_path = str(tmp_path / "phase18-concurrency.sqlite3")
    store = SQLiteReceiptChainStore(database_path)

    def append_same_receipt():
        try:
            ReceiptChain(store).append(first)
            return "committed"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=12) as executor:
        outcomes = list(executor.map(lambda _: append_same_receipt(), range(24)))

    assert outcomes.count("committed") == 1
    assert outcomes.count("rejected") == 23
    assert len(store.entries()) == 1
    assert ReceiptChainVerifier().verify(store.entries()).valid


def test_sqlite_receipt_chain_rejects_in_memory_database():
    from src.production_hardening.phase18_receipt_chain import SQLiteReceiptChainStore

    with pytest.raises(ValueError, match="persistent database file"):
        SQLiteReceiptChainStore(":memory:")
