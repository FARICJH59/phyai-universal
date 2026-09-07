from __future__ import annotations

from typing import Protocol

from src.phase7_reasoning.planners.planner import Plan, ReasoningRequest


class ReasoningAgent(Protocol):
    def reason(self, request: ReasoningRequest) -> Plan: ...


class PlannerReasoningAgent:
    """Adapter that keeps agentic reasoning behind the planner boundary."""

    def __init__(self, planner):
        self._planner = planner

    def reason(self, request: ReasoningRequest) -> Plan:
        return self._planner.plan(request)
