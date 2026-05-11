"""Routing functions for conditional edges."""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Determine the next node after classification.


    """
    route = state.get("route", Route.SIMPLE.value)
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }
    return mapping.get(route, "answer")


def route_after_retry(state: AgentState) -> str:
    """Check attempt counter to bound the retry loop.


    """
    if int(state.get("attempt", 0)) >= int(state.get("max_attempts", 3)):
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Determine if we should retry or provide an answer.


    """
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Route based on human approval/rejection.


    """
    approval = state.get("approval") or {}
    return "tool" if approval.get("approved") else "clarify"
