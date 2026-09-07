from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

from src.phase1_contracts.contracts.contracts import ContractValidationError


@dataclass(frozen=True, slots=True)
class CompiledSurrogate:
    artifact: bytes
    artifact_hash: str
    compiler_id: str
    metadata: Mapping[str, str]


class SurrogateCompiler:
    """Compile solver output into a content-addressed, non-executable artifact."""

    compiler_id = "surrogate-compiler-v1"

    def compile(self, values: Mapping[str, float], metadata: Mapping[str, str] | None = None) -> CompiledSurrogate:
        if not values:
            raise ContractValidationError("cannot compile empty surrogate values")
        canonical = "\n".join(f"{key}={values[key]:.12g}" for key in sorted(values))
        artifact = canonical.encode("utf-8")
        return CompiledSurrogate(
            artifact=artifact,
            artifact_hash=sha256(artifact).hexdigest(),
            compiler_id=self.compiler_id,
            metadata=dict(metadata or {}),
        )
