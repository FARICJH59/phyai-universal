import time

from src.production_hardening.latency import ControlLoopLatencyHarness


def test_latency_harness_reports_average_p95_and_maximum():
    harness = ControlLoopLatencyHarness(lambda value: value + 1, target_ms=50.0)
    result = harness.measure([1, 2, 3, 4])
    assert len(result.samples_ms) == 4
    assert result.average_ms >= 0.0
    assert result.p95_ms >= 0.0
    assert result.maximum_ms >= result.p95_ms
    assert result.passed


def test_latency_harness_uses_p95_for_pass_fail():
    def slow(value):
        if value == 2:
            time.sleep(0.01)
        return value

    harness = ControlLoopLatencyHarness(slow, target_ms=1.0)
    result = harness.measure([1, 2, 3])
    assert result.p95_ms >= 1.0
    assert not result.passed


def test_latency_harness_warmup_is_not_measured():
    calls = []
    harness = ControlLoopLatencyHarness(lambda value: calls.append(value), target_ms=50.0)
    result = harness.measure([1, 2, 3], warmup=1)
    assert result.samples_ms
    assert calls == [1, 2, 3]
