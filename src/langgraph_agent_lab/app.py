import os
import time

import streamlit as st

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Route, Scenario, initial_state

# Force interrupt for demo
os.environ["LANGGRAPH_INTERRUPT"] = "true"

st.set_page_config(page_title="LangGraph Interactive Demo", page_icon="🧠", layout="wide")

# Custom CSS for better look
st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; }
    .node-pill { 
        background-color: #e0e7ff; 
        color: #4338ca; 
        border-radius: 10px; 
        padding: 2px 10px; 
        font-size: 0.75rem; 
        font-weight: 500;
        border: 1px solid #c7d2fe;
        margin-right: 5px;
        display: inline-block;
    }
    </style>
""", unsafe_allow_html=True)

def render_dynamic_mermaid(visited_nodes: list[str]) -> None:
    """Render the graph as a Mermaid diagram with highlighted nodes."""
    checkpointer_dummy = build_checkpointer("memory")
    dummy_graph = build_graph(checkpointer=checkpointer_dummy)
    mermaid_code = dummy_graph.get_graph().draw_mermaid()
    
    if visited_nodes:
        skip = {"__start__", "__end__", "START", "END"}
        clean_nodes = [n for n in visited_nodes if n not in skip]
        if clean_nodes:
            active_cls = "fill:#4CAF50,stroke:#2E7D32,stroke-width:1px,color:#fff"
            styles = f"\n    classDef active {active_cls};\n"
            styles += (
                "\n    classDef current fill:#FF9800,stroke:#EF6C00,stroke-width:3px,color:#fff;\n"
            )
            current_node = clean_nodes[-1]
            past_nodes = set(clean_nodes[:-1])
            for node in past_nodes:
                styles += f"    class {node} active;\n"
            styles += f"    class {current_node} current;\n"
            mermaid_code += styles

    st.components.v1.html(
        f"""
        <div class="mermaid" style="display: flex; justify-content: center;">{mermaid_code}</div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ 
                startOnLoad: true, 
                theme: 'neutral',
                flowchart: {{ useMaxWidth: false, htmlLabels: true }} 
            }});
        </script>
        """,
        height=800,
        scrolling=True
    )

def main() -> None:
    st.title("🧠 LangGraph Interactive Support Agent")
    
    # Session State Initialization
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"demo-{int(time.time())}"
    if "visited_nodes" not in st.session_state:
        st.session_state.visited_nodes = ["START"]
    if "nodes_in_this_run" not in st.session_state:
        st.session_state.nodes_in_this_run = []
    if "waiting_for_hitl" not in st.session_state:
        st.session_state.waiting_for_hitl = False
    if "pending_proposal" not in st.session_state:
        st.session_state.pending_proposal = None

    # Sidebar
    with st.sidebar:
        st.header("🛠️ Admin Controls")
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.thread_id = f"demo-{int(time.time())}"
            st.session_state.visited_nodes = ["START"]
            st.session_state.nodes_in_this_run = []
            st.session_state.waiting_for_hitl = False
            st.rerun()
            
        st.divider()
        st.header("📂 Sample Scenarios")
        scenarios = load_scenarios("data/sample/scenarios.jsonl")
        for s in scenarios:
            if st.button(f"📌 {s.id}", help=s.query, use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": s.query})
                st.rerun()

    # Layout: Chat and Graph
    col_chat, col_graph = st.columns([1.2, 0.8])

    with col_chat:
        # Display chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "nodes" in msg:
                    pills = " ".join(
                        f"<span class='node-pill'>{n}</span>" for n in msg["nodes"]
                    )
                    st.markdown(pills, unsafe_allow_html=True)

        # HITL Interface
        if st.session_state.waiting_for_hitl:
            with st.chat_message("assistant"):
                st.warning("⚠️ **Cần phê duyệt hành động nhạy cảm**")
                st.info(f"**Hành động đề xuất:**\n{st.session_state.pending_proposal}")
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Đồng ý thực hiện", use_container_width=True, type="primary"):
                    st.session_state.hitl_decision = True
                    st.session_state.waiting_for_hitl = False
                    st.rerun()
                if c2.button("❌ Từ chối", use_container_width=True):
                    st.session_state.hitl_decision = False
                    st.session_state.waiting_for_hitl = False
                    st.rerun()
            return

        # Input
        if user_query := st.chat_input("Nhập yêu cầu của bạn..."):
            st.session_state.messages.append({"role": "user", "content": user_query})
            st.rerun()

        # Processing Logic
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            process_query(st.session_state.messages[-1]["content"])

    with col_graph:
        st.subheader("📊 Live Workflow Diagram")
        render_dynamic_mermaid(st.session_state.visited_nodes)
        
def process_query(query: str) -> None:
    checkpointer = build_checkpointer("sqlite", "checkpoints_ui.db")
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    
    # Check if we are resuming from HITL
    if hasattr(st.session_state, "hitl_decision"):
        decision = st.session_state.hitl_decision
        del st.session_state.hitl_decision
        # Update state with decision BEFORE resuming
        graph.update_state(config, {"approval": {"approved": decision}}, as_node="approval")
        # Resume stream
        stream = graph.stream(None, config, stream_mode="updates")
    else:
        # New run - Reset everything
        st.session_state.visited_nodes = ["START"]
        st.session_state.nodes_in_this_run = []
        scen = Scenario(id="ui", query=query, expected_route=Route.SIMPLE)
        state = initial_state(scen)
        stream = graph.stream(state, config, stream_mode="updates", interrupt_before=["approval"])

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        with status_placeholder.status("Agent đang xử lý...", expanded=True) as status:
            final_answer = None
            pending_question = None
            
            try:
                for output in stream:
                    for node_name, updates in output.items():
                        st.session_state.visited_nodes.append(node_name)
                        st.session_state.nodes_in_this_run.append(node_name)
                        status.write(f"⚙️ Đang chạy node: **{node_name}**")
                        
                        if "final_answer" in updates:
                            final_answer = updates["final_answer"]
                        if "pending_question" in updates:
                            pending_question = updates["pending_question"]
                        
                        time.sleep(0.4)
                
                # Check if we hit a breakpoint (approval)
                snapshot = graph.get_state(config)
                if snapshot.next and snapshot.next[0] == "approval":
                    # Highlight 'approval' node as current
                    st.session_state.visited_nodes.append("approval")
                    st.session_state.nodes_in_this_run.append("approval")
                    
                    st.session_state.waiting_for_hitl = True
                    st.session_state.pending_proposal = snapshot.values.get(
                        "proposed_action", "Manual approval required"
                    )
                    status.update(label="🛑 Tạm dừng để chờ phê duyệt!", state="running")
                    st.rerun()

                status.update(label="Xử lý hoàn tất!", state="complete")
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
                return

        # Final responses
        nodes = st.session_state.nodes_in_this_run.copy()
        if pending_question:
            st.write(f"**❓ Agent cần thêm thông tin:**\n{pending_question}")
            st.session_state.messages.append(
                {"role": "assistant", "content": pending_question, "nodes": nodes}
            )
        elif final_answer:
            st.write(final_answer)
            st.session_state.messages.append(
                {"role": "assistant", "content": final_answer, "nodes": nodes}
            )
        
        st.session_state.visited_nodes.append("END")
        st.rerun()

if __name__ == "__main__":
    main()
