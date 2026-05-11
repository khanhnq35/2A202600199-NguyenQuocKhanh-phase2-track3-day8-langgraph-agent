import uuid
import os

# Kích hoạt chế độ ngắt (Interrupt) để mô phỏng Human-in-the-loop
os.environ["LANGGRAPH_INTERRUPT"] = "true"

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer

def demo():
    print("Khởi tạo SQLite Checkpointer...")
    checkpointer = build_checkpointer("sqlite")
    graph = build_graph(checkpointer)
    
    # Tạo Thread ID cho phiên làm việc
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n=======================================================")
    print(f"🚀 PHẦN 1: USER INTERRUPT & CRASH SIMULATION")
    print(f"=======================================================")
    print(f"Thread ID: {thread_id}")
    
    # Người dùng vô tình yêu cầu một hành động nguy hiểm
    initial_state = {"query": "Refund this customer and delete their account"}
    print(f"\nUser Request: '{initial_state['query']}'")
    print("Đang xử lý yêu cầu...")
    
    # Graph sẽ chạy và BỊ DỪNG LẠI tại node 'approval' do có lệnh interrupt()
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, state in event.items():
            print(f"  -> Đã chạy qua node: [{node_name}]")
            
    print("\n🛑 HỆ THỐNG ĐÃ DỪNG LẠI (USER INTERRUPT) ĐỂ CHỜ PHÊ DUYỆT.")
    print("Giả sử đúng lúc này máy chủ bị mất điện (Crash) hoặc quá trình bị ngắt đột ngột.")
    
    print(f"\n=======================================================")
    print(f"🔄 PHẦN 2: CRASH RECOVERY (KHÔI PHỤC SAU SỰ CỐ)")
    print(f"=======================================================")
    print("Máy chủ vừa khởi động lại. Hệ thống tự động kết nối lại SQLite với cùng Thread ID...")
    
    # Khởi tạo lại một object đồ thị hoàn toàn mới để chứng minh RAM đã bị xóa
    graph_recovered = build_graph(build_checkpointer("sqlite"))
    current_state = graph_recovered.get_state(config)
    
    print(f"Hệ thống nhận diện được luồng vẫn đang mắc kẹt ở node: {current_state.next}")
    print("Nhưng thay vì phê duyệt hoàn tiền, User hốt hoảng và quyết định THAY ĐỔI YÊU CẦU!")
    
    print(f"\n=======================================================")
    print(f"⏳ PHẦN 3: TIME TRAVEL & THAY ĐỔI YÊU CẦU (FORKING)")
    print(f"=======================================================")
    
    # Kéo lịch sử các bước ra
    history = list(graph_recovered.get_state_history(config))
    
    # Tìm về quá khứ: Lấy mốc thời gian NGAY TRƯỚC KHI đồ thị chạy node 'classify'
    # Để chúng ta có thể tiêm một câu lệnh mới vào và bắt nó phân loại lại từ đầu.
    target_config = None
    for state_snapshot in history:
        if state_snapshot.next == ('classify',):
            target_config = state_snapshot.config
            break
            
    if target_config:
        checkpoint_id = target_config['configurable']['checkpoint_id']
        print(f"\nĐã lùi thời gian về mốc chuẩn bị phân loại. Checkpoint ID: {checkpoint_id}")
        
        new_query = "Actually, please just check the order status instead."
        print(f"User can thiệp thay đổi yêu cầu thành: '{new_query}'")
        
        # Cập nhật State tại mốc thời gian trong quá khứ
        # Hành động này sẽ tạo ra một nhánh thời gian mới (Fork)
        graph_recovered.update_state(
            target_config, 
            {"query": new_query}, 
            as_node="intake" # Giả lập như thể câu hỏi này vừa đi ra từ intake_node
        )
        
        print("\nTiến hành chạy lại luồng bắt đầu từ nhánh thời gian mới này...")
        # Lần này Graph sẽ rẽ sang nhánh 'tool' thay vì nhánh 'risky_action' như lúc nãy
        for event in graph_recovered.stream(None, config, stream_mode="updates"):
            for node_name, state in event.items():
                print(f"  -> [TIME TRAVEL] Đã chạy qua node: [{node_name}]")
                
    print("\n✅ Hệ thống đã thay đổi yêu cầu thành công và đi đến đích an toàn (END).")

if __name__ == "__main__":
    demo()
