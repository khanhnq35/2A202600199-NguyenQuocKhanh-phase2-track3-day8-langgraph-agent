import uuid
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer

def demo():
    # 1. Khởi tạo đồ thị với SQLite Checkpointer
    print("Khởi tạo SQLite Checkpointer...")
    checkpointer = build_checkpointer("sqlite")
    graph = build_graph(checkpointer)
    
    # Tạo một Thread ID ngẫu nhiên để giả lập một session của user
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n=======================================================")
    print(f"🚀 PHẦN 1: CHẠY GRAPH & GIẢ LẬP CRASH (CRASH SIMULATION)")
    print(f"=======================================================")
    print(f"Thread ID: {thread_id}")
    
    # Gửi một câu lệnh nhạy cảm để ép graph dừng lại ở node 'approval'
    initial_state = {"query": "Refund this customer and send confirmation email"}
    
    print("\nĐang xử lý yêu cầu...")
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, state in event.items():
            print(f"  -> Đã chạy qua node: [{node_name}]")
            
    print("\n🛑 HỆ THỐNG ĐÃ DỪNG LẠI (INTERRUPT) TẠI NODE 'approval'.")
    print("Giả sử lúc này máy chủ bị mất điện (Crash) hoặc process bị kill hoàn toàn.")
    
    print(f"\n=======================================================")
    print(f"🔄 PHẦN 2: PHỤC HỒI SAU CRASH (CRASH RECOVERY)")
    print(f"=======================================================")
    print("Máy chủ vừa khởi động lại. Cấu hình lại checkpointer với cùng Thread ID...")
    
    # Khởi tạo lại graph hoàn toàn mới để chứng minh nó không lưu trong RAM
    graph_recovered = build_graph(build_checkpointer("sqlite"))
    
    current_state = graph_recovered.get_state(config)
    print(f"Trạng thái hiện tại đang chờ chạy tiếp node: {current_state.next}")
    
    print("\nTiếp tục chạy Graph từ SQLite DB bằng cách truyền input = None...")
    for event in graph_recovered.stream(None, config, stream_mode="updates"):
        for node_name, state in event.items():
            print(f"  -> Đã chạy qua node: [{node_name}]")
            
    print("✅ Graph đã chạy thành công đến đích (END).")
    
    
    print(f"\n=======================================================")
    print(f"⏳ PHẦN 3: DU HÀNH THỜI GIAN (TIME TRAVEL)")
    print(f"=======================================================")
    # Lấy toàn bộ lịch sử các checkpoint của thread này (sắp xếp từ mới nhất -> cũ nhất)
    history = list(graph_recovered.get_state_history(config))
    print(f"Tổng số checkpoint (bản ghi trạng thái) đã lưu trong SQLite: {len(history)}")
    
    # Tìm về quá khứ: Trạng thái lúc graph CHƯA chạy node 'risky_action'
    target_config = None
    for state_snapshot in history:
        # Nếu next node của snapshot này là 'risky_action' thì đây là mốc thời gian ta cần
        if state_snapshot.next == ('risky_action',):
            target_config = state_snapshot.config
            break
            
    if target_config:
        checkpoint_id = target_config['configurable']['checkpoint_id']
        print(f"\nĐã tìm thấy mốc thời gian trong quá khứ! Checkpoint ID: {checkpoint_id}")
        print("Lúc này Graph vừa phân loại xong (classify) và chuẩn bị chạy 'risky_action'.")
        
        print("\nTiến hành Time Travel: Chạy lại luồng bắt đầu từ quá khứ này...")
        # Khi truyền target_config vào, LangGraph sẽ Fork (rẽ nhánh) quá khứ để tạo một tương lai mới
        for event in graph_recovered.stream(None, target_config, stream_mode="updates"):
            for node_name, state in event.items():
                print(f"  -> [TIME TRAVEL] Đã chạy qua node: [{node_name}]")
                
if __name__ == "__main__":
    demo()
