from __future__ import annotations

import argparse

from src.production_hardening.inference_backends import benchmark_backend, load_onnx_runtime_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark an ONNX Runtime model on the current machine.")
    parser.add_argument("model", help="Path to an ONNX model")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--input-size", type=int, default=16)
    args = parser.parse_args()
    backend = load_onnx_runtime_backend(args.model)
    result = benchmark_backend(backend, [0.0] * args.input_size, args.iterations)
    print(f"backend={result.backend_id} average_ms={result.elapsed_ms:.3f} iterations={args.iterations}")
    print(f"target_50ms={'PASS' if result.elapsed_ms <= 50.0 else 'FAIL'}")


if __name__ == "__main__":
    main()
