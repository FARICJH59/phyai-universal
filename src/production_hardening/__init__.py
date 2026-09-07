"""Production hardening capabilities for Physical AI workloads."""

from .world_model import ActionCondition, ActionConditionedReferenceWorldModel, WorldModelRequest
from .trajectory import AutoregressiveTrajectoryGenerator, Trajectory
from .multimodal import ModalityInput, MultimodalFusion, UnifiedRepresentation
from .robustness import MultimodalPerturbation, OutputSensitivity, SensorNoiseHarness, TrajectoryDeviation
from .learned_world_model import (
    EncodedLearnedWorldModelAdapter,
    LearnedWorldModelRequest,
    PyTorchTensorModel,
    TensorWorldModelInput,
    VideoFrame,
    action_feature_encoder,
)
from .learned_multimodal import (
    EncodedMultimodalFusion,
    LearnedMultimodalRepresentation,
    ModalityEncoder,
    LearnedMultimodalEncoder,
    TensorModalityInput,
)
from .phase12_acceleration import (
    CudaExecutionResult,
    TensorRTExecutionAdapter,
    TensorRTExecutionResult,
    TimedCudaKernel,
)
from .phase13_latency import EndToEndLatencyHarness, EndToEndLatencyReport, LatencySample
from .phase14_robustness import RobustnessEvaluation, RobustnessThreshold, SimToRealRobustnessHarness, perturb_modalities
from .phase17_evidence import (
    DurableReceipt,
    ExecutionEvidence,
    ExecutionIdentity,
    EvidenceVerifier,
    HMACSHA256Signer,
    InMemoryEvidenceStore,
    SignedAdmissionArtifact,
    sign_admission,
    verify_admission,
)
from .phase18_receipt_chain import (
    InMemoryReceiptChainStore,
    ReceiptChain,
    ReceiptChainEntry,
    ReceiptChainVerification,
    ReceiptChainVerifier,
)

__all__ = [
    "ActionCondition",
    "ActionConditionedReferenceWorldModel",
    "WorldModelRequest",
    "AutoregressiveTrajectoryGenerator",
    "Trajectory",
    "ModalityInput",
    "MultimodalFusion",
    "UnifiedRepresentation",
    "MultimodalPerturbation",
    "OutputSensitivity",
    "SensorNoiseHarness",
    "TrajectoryDeviation",
    "EncodedLearnedWorldModelAdapter",
    "LearnedWorldModelRequest",
    "PyTorchTensorModel",
    "TensorWorldModelInput",
    "VideoFrame",
    "action_feature_encoder",
    "EncodedMultimodalFusion",
    "LearnedMultimodalRepresentation",
    "ModalityEncoder",
    "LearnedMultimodalEncoder",
    "TensorModalityInput",
    "TensorRTExecutionAdapter",
    "TensorRTExecutionResult",
    "TimedCudaKernel",
    "CudaExecutionResult",
    "EndToEndLatencyHarness",
    "EndToEndLatencyReport",
    "LatencySample",
    "RobustnessEvaluation",
    "RobustnessThreshold",
    "SimToRealRobustnessHarness",
    "perturb_modalities",
    "ExecutionIdentity",
    "SignedAdmissionArtifact",
    "HMACSHA256Signer",
    "sign_admission",
    "verify_admission",
    "ExecutionEvidence",
    "EvidenceVerifier",
    "InMemoryEvidenceStore",
    "ReceiptChainEntry",
    "ReceiptChainVerification",
    "ReceiptChainVerifier",
    "ReceiptChain",
    "InMemoryReceiptChainStore",
]
