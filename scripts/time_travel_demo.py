"""
Demo script for LangGraph Time Travel (Extension 3).
Usage: python scripts/time_travel_demo.py
"""
import sqlite3
from langgraph_agent_lab.graph import build_graph
from langgraph.checkpoint.sqlite import SqliteSaver

def demo_time_travel():
    # 1. Setup checkpointer
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    
    # 2. Build graph
    graph = build_graph(checkpointer=checkpointer)
    
    # 3. Simulate a thread id
    thread_id = "demo_thread_001"
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"--- Auditing Thread: {thread_id} ---")
    
    # 4. List state history
    # This retrieves all previous checkpoints for the thread
    history = list(graph.get_state_history(config))
    
    if not history:
        print("No history found. Run scenarios first to populate checkpoints.db")
        return

    print(f"Found {len(history)} checkpoints.\n")
    
    for i, state in enumerate(reversed(history)):
        node = state.metadata.get("source", "START")
        print(f"Step {i}: Node = {node}")
        print(f"   Route: {state.values.get('route')}")
        print(f"   Events: {len(state.values.get('events', []))}")
        print("-" * 30)

    # 5. Time Travel: How to resume from a past checkpoint
    # last_state = history[1] # Pick the second most recent state
    # graph.invoke(None, last_state.config) 

if __name__ == "__main__":
    try:
        demo_time_travel()
    except Exception as e:
        print(f"Note: This demo requires checkpoints.db to be present.\nError: {e}")
