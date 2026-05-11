"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from typing import Any

from .state import AgentState, ApprovalDecision, Route, make_event


def intake_node(state: AgentState) -> dict[str, Any]:
    """Normalize raw query (strip/lower), check for PII, and extract metadata."""
    import re
    query = state.get("query", "").strip().lower()

    # Basic PII masking (email and phone)
    masked = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b", "[EMAIL]", query)
    masked = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", masked)

    metadata = {
        "word_count": len(query.split()),
        "has_pii": masked != query,
        "char_count": len(masked),
    }

    return {
        "query": masked,
        "metadata": metadata,
        "messages": [f"intake:{masked[:40]}"],
        "events": [make_event("intake", "completed", "query normalized", **metadata)],
    }


def classify_node(state: AgentState) -> dict[str, Any]:
    """Classify the query into a route based on keywords and priority.

    Required routes: simple, tool, missing_info, risky, error.
    """
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]

    risky_keywords = {"refund", "delete", "send", "cancel", "remove", "revoke"}
    tool_keywords = {"status", "order", "lookup", "check", "track", "find", "search"}
    error_keywords = {"timeout", "fail", "error", "crash", "unavailable"}
    vague_pronouns = {"it", "this", "that", "they"}

    route = Route.SIMPLE
    risk_level = "low"

    # Priority 1: risky
    if any(kw in query for kw in risky_keywords):
        route = Route.RISKY
        risk_level = "high"
    # Priority 2: error (Đẩy lên trước tool để bắt các case "check timeout error")
    elif any(kw in query for kw in error_keywords):
        route = Route.ERROR
    # Priority 3: tool
    elif any(kw in query for kw in tool_keywords):
        route = Route.TOOL
    # Priority 4: missing_info (Bỏ giới hạn < 5 từ để bắt các câu dài nhưng thiếu context)
    elif any(w in vague_pronouns for w in clean_words):
        route = Route.MISSING_INFO

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}")],
    }


def ask_clarification_node(state: AgentState) -> dict[str, Any]:
    """Generate a specific clarification question based on query context.


    """
    query = state.get("query", "").lower()
    if "it" in query or "this" in query:
        question = "I'm sorry, but 'it' is unclear. What specifically are you referring to?"
    else:
        question = "Could you please provide more context or an order ID to help me assist you?"

    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", f"asked: {question[:30]}...")],
    }


def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute a mock tool with idempotency check and structured output.


    """
    import json
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    tool_results = state.get("tool_results", [])

    # Idempotency check: If already succeeded in this thread, skip re-execution
    for res in tool_results:
        try:
            if json.loads(res).get("status") == "success":
                return {
                    "events": [make_event("tool", "skipped", "idempotency check: already success")]
                }
        except json.JSONDecodeError:
            continue

    if state.get("route") == Route.ERROR.value and attempt < 2:
        result = {"status": "error", "code": 503, "message": "Service temporarily unavailable"}
    else:
        result = {"status": "success", "data": f"Processed action for {scenario_id}"}

    result_str = json.dumps(result)
    return {
        "tool_results": [result_str],
        "events": [make_event("tool", "completed", f"status={result['status']}")],
    }


def risky_action_node(state: AgentState) -> dict[str, Any]:
    """Prepare a risky action with a clear justification for the reviewer.


    """
    query = state.get("query", "")
    justification = "Requires manual override due to potential permanent impact on customer data."
    proposed = f"Action: {query} | Reason: {justification}"

    return {
        "proposed_action": proposed,
        "events": [make_event("risky_action", "prepared", "justification added")],
    }


def approval_node(state: AgentState) -> dict[str, Any]:
    """Human approval step with optional LangGraph interrupt().



    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.
    """
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": state.get("risk_level"),
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")
    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict[str, Any]:
    """Record a retry attempt with exponential backoff metadata.


    """
    attempt = int(state.get("attempt", 0)) + 1
    errors = [f"transient failure attempt={attempt}"]

    # Exponential backoff simulation metadata: 2^attempt * 100ms
    backoff_ms = (2**attempt) * 100
    metadata = {"backoff_ms": backoff_ms, "strategy": "exponential_backoff"}

    return {
        "attempt": attempt,
        "errors": errors,
        "events": [
            make_event("retry", "completed", f"retry {attempt} recorded", **metadata)
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response grounded in tool results.


    """
    import json
    tool_results = state.get("tool_results", [])

    if tool_results:
        try:
            latest = json.loads(tool_results[-1])
            if latest.get("status") == "success":
                answer = f"I have successfully completed your request: {latest.get('data')}"
            else:
                answer = f"I encountered an issue: {latest.get('message')}"
        except (json.JSONDecodeError, KeyError):
            answer = f"Here is what I found: {tool_results[-1]}"
    else:
        answer = "I've processed your request. Is there anything else I can help with?"

    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "grounded response generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results to decide success or retry.


    """
    import json
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {"evaluation_result": "success", "events": []}

    try:
        latest = json.loads(tool_results[-1])
        if latest.get("status") == "error":
            return {
                "evaluation_result": "needs_retry",
                "events": [
                    make_event("evaluate", "completed", "retry triggered by service error")
                ],
            }
    except json.JSONDecodeError:
        pass

    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "result validated")],
    }


def dead_letter_node(state: AgentState) -> dict[str, Any]:
    """Log unresolvable failures and simulate support ticket creation.


    """
    import uuid
    ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
    return {
        "final_answer": (
            f"Request could not be completed after maximum retry attempts. "
            f"A support ticket ({ticket_id}) has been created for manual review."
        ),
        "events": [
            make_event(
                "dead_letter",
                "completed",
                f"max retries exceeded, ticket={ticket_id}",
                ticket_id=ticket_id,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
