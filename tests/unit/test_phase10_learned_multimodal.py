from src.production_hardening.learned_multimodal import (
    EncodedMultimodalFusion,
    LearnedMultimodalRepresentation,
    TensorModalityInput,
)
from src.production_hardening.multimodal import ModalityInput


class Encoder:
    def __init__(self, modality: str, value: float):
        self.modality = modality
        self.value = value

    def encode(self, modality: ModalityInput) -> TensorModalityInput:
        return TensorModalityInput(
            modality=self.modality,
            features=(self.value,),
            timestamp_ns=modality.timestamp_ns,
            confidence=modality.confidence,
        )


class Fusion:
    encoder_id = "test-learned-fusion-v1"

    def fuse(self, tenant_id, project_id, inputs):
        return LearnedMultimodalRepresentation(
            tenant_id=tenant_id,
            project_id=project_id,
            timestamp_ns=max(x.timestamp_ns for x in inputs),
            modality_order=tuple(x.modality for x in inputs),
            features=tuple(v for x in inputs for v in x.features),
            confidence=min(x.confidence for x in inputs),
            encoder_id=self.encoder_id,
        )


def inputs():
    return [
        ModalityInput("language", b"pick", "utf8", 14, 0.90),
        ModalityInput("rgb", b"rgb", "jpeg", 10, 0.98),
        ModalityInput("depth", b"depth", "float32", 11, 0.96),
    ]


def test_learned_multimodal_fusion_is_temporally_ordered_and_deterministic():
    encoders = {"rgb": Encoder("rgb", 1.0), "depth": Encoder("depth", 2.0), "language": Encoder("language", 3.0)}
    fusion = EncodedMultimodalFusion(encoders, Fusion())
    first = fusion.fuse("t1", "p1", inputs())
    second = fusion.fuse("t1", "p1", inputs())
    assert first == second
    assert first.modality_order == ("rgb", "depth", "language")
    assert first.features == (1.0, 2.0, 3.0)
    assert first.confidence == 0.90


def test_unknown_modality_fails_closed():
    fusion = EncodedMultimodalFusion({"rgb": Encoder("rgb", 1.0)}, Fusion())
    try:
        fusion.fuse("t1", "p1", inputs())
    except ValueError as exc:
        assert "no encoder registered" in str(exc)
    else:
        raise AssertionError("unknown modality must fail")


def test_encoder_cannot_change_modality_identity():
    encoders = {"rgb": Encoder("depth", 1.0), "depth": Encoder("depth", 2.0), "language": Encoder("language", 3.0)}
    fusion = EncodedMultimodalFusion(encoders, Fusion())
    try:
        fusion.fuse("t1", "p1", inputs())
    except ValueError as exc:
        assert "changed modality identity" in str(exc)
    else:
        raise AssertionError("modality identity mutation must fail")


def test_learned_fusion_cannot_change_tenant_or_project():
    class BadFusion(Fusion):
        def fuse(self, tenant_id, project_id, inputs):
            return LearnedMultimodalRepresentation(
                tenant_id="other", project_id=project_id, timestamp_ns=1,
                modality_order=tuple(x.modality for x in inputs), features=(1.0,),
                confidence=0.9, encoder_id=self.encoder_id,
            )

    encoders = {"rgb": Encoder("rgb", 1.0), "depth": Encoder("depth", 2.0), "language": Encoder("language", 3.0)}
    fusion = EncodedMultimodalFusion(encoders, BadFusion())
    try:
        fusion.fuse("t1", "p1", inputs())
    except PermissionError as exc:
        assert "tenant/project identity" in str(exc)
    else:
        raise AssertionError("identity mutation must fail")
