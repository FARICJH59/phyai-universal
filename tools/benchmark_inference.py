from __future__ import annotations

import argparse

from src.production_hardening.inference_backends import (
    benchmark_backend,
    build_benchmark_input,
    load_onnx_runtime_backend,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark an ONNX Runtime model on the current machine.")
    parser.add_argument("model", help="Path to an ONNX model")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument(
        "--dynamic-dimension",
        type=int,
        default=1,
        help="Concrete size used for dynamic ONNX dimensions",
    )
    parser.add_argument("--target-ms", type=float, default=50.0)
    args = parser.parse_args()

    backend = load_onnx_runtime_backend(args.model)
    input_spec = backend.input_spec
    inputs = build_benchmark_input(input_spec, args.dynamic_dimension)
    result = benchmark_backend(backend, inputs, args.iterations)

    print(f"backend={result.backend_id}")
    print(f"input_name={input_spec.name}")
    print(f"input_shape={input_spec.shape}")
    print(f"input_type={input_spec.element_type}")
    print(f"average_ms={result.elapsed_ms:.3f} iterations={args.iterations}")
    print(f"target_{args.target_ms:g}ms={'PASS' if result.elapsed_ms <= args.target_ms else 'FAIL'}")


if __name__ == "__main__":
    main()
