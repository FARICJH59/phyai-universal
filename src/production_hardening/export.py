from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    format: str
    path: str
    opset: int


class PyTorchONNXExporter:
    """Production adapter around torch.onnx.export; dependency is intentionally optional."""

    def export(
        self,
        model: Any,
        example_inputs: Any,
        output_path: str,
        opset: int = 18,
    ) -> ExportArtifact:
        if opset < 17:
            raise ValueError("opset must be >= 17")
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch is required for ONNX export") from exc
        torch.onnx.export(
            model,
            example_inputs,
            str(destination),
            opset_version=opset,
            dynamo=True,
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("ONNX export produced no artifact")
        return ExportArtifact("onnx", str(destination), opset)
