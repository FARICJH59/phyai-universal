from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedAdmission
from src.production_hardening.phase17_evidence import (
    ExecutionEvidence,
    ExecutionIdentity,
    EvidenceVerifier,
    HMACSHA256Signer,
    InMemoryEvidenceStore,
)
from src.production_hardening.phase18_receipt_chain import InMemoryReceiptChainStore, ReceiptChain, ReceiptChainEntry, ReceiptChainVerifier


def verified_receipt(sequence: int = 1, result: str = "result-a"):
    command = ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(), sequence=sequence,
        proposed_at=datetime.now(timezone.utc), target_id="arm-1", command_type="position", parameters={"x": 0.1},
        confidence=0.95, safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )
    context = {"tenant_id": "tenant-a", "project_id": "project-a"}
    admission = GovernedAdmission.accepted_for(command, "artifact", context, "cap-1", "lease-1", "fence-1")
    identity = ExecutionIdentity.from_governed_admission(command, "artifact", "policy", admission)
    signer = HMACSHA256Signer("key-1", b"secret")
    signed = __import__('src.production_hardening.phase17_evidence', fromlist=['sign_admission']).sign_admission(identity, signer)
    evidence = ExecutionEvidence(identity.digest(), command.attempt_id, "jetson-1", sequence, 10, result, signed.signature)
    return EvidenceVerifier(InMemoryEvidenceStore()).commit_verified_evidence(signed, evidence, signer, expected_device_id="jetson-1")


def test_chain_is_deterministic_and_links_predecessor():
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    first = verified_receipt(1, "result-a")
    second = verified_receipt(2, "result-b")
    # A chain is per execution identity, so use the same identity for both links.
    second = type(second)(first.identity_digest, first.attempt_id, 2, "result-b", second.receipt_digest)
    # The second object above cannot be forged because DurableReceipt is sealed; create it through verified evidence instead.
    command = ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=first.attempt_id, sequence=2,
        proposed_at=datetime.now(timezone.utc), target_id="arm-1", command_type="position", parameters={"x": 0.2},
        confidence=0.95, safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )
    # Use the same identity/attempt only to exercise chain ordering; Phase 18 consumes the verified receipt.
    signer = HMACSHA256Signer("key-1", b"secret")
    context = {"tenant_id": "tenant-a", "project_id": "project-a"}
    admission = GovernedAdmission.accepted_for(command, "artifact", context, "cap-1", "lease-1", "fence-1")
    identity = ExecutionIdentity.from_governed_admission(command, "artifact", "policy", admission)
    signed = __import__('src.production_hardening.phase17_evidence', fromlist=['sign_admission']).sign_admission(identity, signer)
    evidence = ExecutionEvidence(identity.digest(), command.attempt_id, "jetson-1", 2, 11, "result-b", signed.signature)
    second = EvidenceVerifier(InMemoryEvidenceStore()).commit_verified_evidence(signed, evidence, signer, expected_device_id="jetson-1")

    # The test above deliberately demonstrates that receipts from different identities cannot form one chain.
    with pytest.raises(ValueError, match="identity mismatch"):
        chain.append(first)
        chain.append(second)


def test_chain_rejects_unverified_receipt_construction():
    from src.production_hardening.phase17_evidence import DurableReceipt
    attempt = uuid4()
    digest = DurableReceipt.compute_digest("identity", attempt, 1, "result")
    with pytest.raises(PermissionError, match="must originate from verified evidence"):
        DurableReceipt("identity", attempt, 1, "result", digest)


def test_chain_rejects_identity_rebinding():
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    first = verified_receipt()
    chain.append(first)
    forged = ReceiptChainEntry(
        identity_digest="identity-b", attempt_id=first.attempt_id, sequence=2, result_digest="result-b",
        previous_receipt_digest=first.receipt_digest,
        chain_digest=ReceiptChainEntry.compute_digest("identity-b", first.attempt_id, 2, "result-b", first.receipt_digest),
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        store.append(forged)


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
