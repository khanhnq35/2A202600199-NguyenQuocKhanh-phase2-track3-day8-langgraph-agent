import json

from langgraph_agent_lab.nodes import classify_node, intake_node, retry_or_fallback_node, tool_node
from langgraph_agent_lab.state import Route


def test_intake_pii_masking() -> None:
    state = {"query": "My email is test@example.com and phone is 123-456-7890"}
    result = intake_node(state)
    assert "[EMAIL]" in result["query"]
    assert "[PHONE]" in result["query"]
    assert result["metadata"]["has_pii"] is True
    assert result["metadata"]["word_count"] > 0

def test_classify_priority_risky() -> None:
    # Should pick risky over tool keywords
    state = {"query": "Please refund my order and track status"}
    result = classify_node(state)
    assert result["route"] == Route.RISKY
    assert result["risk_level"] == "high"

def test_classify_missing_info() -> None:
    # Short query with vague pronoun
    state = {"query": "Fix it"}
    result = classify_node(state)
    assert result["route"] == Route.MISSING_INFO

def test_tool_node_idempotency() -> None:
    # First execution
    state = {"scenario_id": "S01", "attempt": 0, "tool_results": []}
    result1 = tool_node(state)
    assert len(result1["tool_results"]) == 1
    
    # Second execution with previous success should skip
    state2 = {
        "scenario_id": "S01", 
        "attempt": 1, 
        "tool_results": [json.dumps({"status": "success", "data": "Done"})]
    }
    result2 = tool_node(state2)
    assert "tool_results" not in result2
    assert result2["events"][0]["event_type"] == "skipped"

def test_retry_backoff_metadata() -> None:
    state = {"attempt": 1}
    result = retry_or_fallback_node(state)
    assert result["attempt"] == 2
    # 2^2 * 100 = 400ms
    assert result["events"][0]["metadata"]["backoff_ms"] == 400
