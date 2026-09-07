import pytest

from src.production_hardening.phase13_latency import EndToEndLatencyHarness


def test_latency_harness_records_complete_pipeline():
    calls = []

    def pipeline():
        calls.append(1)

    report = EndToEndLatencyHarness(target_ms=50).measure(pipeline, iterations=5)
    assert len(report.samples) == 5
    assert len(calls) == 5
    assert report.mean_ms >= 0
    assert report.p95_ms >= 0
    assert report.maximum_ms >= report.p95_ms
    assert report.passed


def test_latency_harness_fails_when_p95_exceeds_target():
    harness = EndToEndLatencyHarness(target_ms=0.001)

    def slow_pipeline():
        total = 0
        for value in range(10000):
            total += value
        return total

    report = harness.measure(slow_pipeline, iterations=3)
    assert not report.passed
    assert report.p95_ms > report.target_ms


def test_latency_harness_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="target_ms"):
        EndToEndLatencyHarness(target_ms=0)
    with pytest.raises(ValueError, match="iterations"):
        EndToEndLatencyHarness().measure(lambda: None, iterations=0)
