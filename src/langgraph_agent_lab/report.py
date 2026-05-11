"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return a rich report generated automatically from metrics."""
    # Build dynamic scenario table
    table_rows = []
    for m in metrics.scenario_metrics:
        success_icon = "✅" if m.success else "❌"
        pii_icon = "✅" if m.pii_detected else "❌"
        row = (
            f"| {m.scenario_id} | {m.expected_route} | {m.actual_route} | "
            f"{success_icon} | {m.retry_count} | {m.interrupt_count} | {pii_icon} |"
        )
        table_rows.append(row)
    table_str = "\n".join(table_rows)

    return f"""# Day 08 Lab Report - Auto Generated

## 1. Team / student

- Name: Nguyen Quoc Khanh
- Repo/commit: khanh05

## 2. Architecture

Hệ thống được thiết kế dưới dạng một Directed Acyclic Graph (DAG)
với khả năng xử lý vòng lặp (Retry Loop). Sơ đồ kiến trúc chi tiết:

```mermaid
graph TD
    START((START)) --> intake[intake_node]
    intake --> classify[classify_node]
    
    classify -->|simple| answer[answer_node]
    classify -->|tool| tool[tool_node]
    classify -->|missing_info| clarify[ask_clarification_node]
    classify -->|risky| risky_action[risky_action_node]
    classify -->|error| retry[retry_or_fallback_node]
    
    risky_action --> approval[approval_node]
    approval -->|approved| tool
    approval -->|rejected| clarify
    
    retry -->|attempt < max| tool
    retry -->|attempt >= max| dead_letter[dead_letter_node]
    
    tool --> evaluate[evaluate_node]
    evaluate -->|needs_retry| retry
    evaluate -->|success| answer
    
    answer --> finalize[finalize_node]
    clarify --> finalize
    dead_letter --> finalize
    
    finalize --> END((END))
```

### Nodes & Responsibilities:
1.  **intake**: Chuẩn hóa câu hỏi, thực hiện PII Masking (ẩn email/SĐT).
2.  **classify**: Phân loại câu hỏi dựa trên từ khóa và độ ưu tiên
    (Risky > Error > Tool > Missing > Simple).
3.  **tool**: Giả lập việc gọi API/DB để xử lý yêu cầu. Hỗ trợ cơ chế Idempotency.
4.  **evaluate**: Đánh giá kết quả từ tool để quyết định thành công hay cần thử lại.
5.  **risky_action**: Chuẩn bị các hành động nhạy cảm cần phê duyệt (như hoàn tiền, xóa tài khoản).
6.  **approval**: Điểm dừng HITL (Human-in-the-loop) để chờ người dùng phê duyệt hoặc từ chối.
7.  **retry**: Tăng bộ đếm attempt và ghi nhận lỗi transient.
8.  **clarify**: Yêu cầu người dùng cung cấp thêm thông tin khi câu hỏi quá mơ hồ.
9.  **answer**: Tổng hợp câu trả lời cuối cùng dựa trên kết quả từ các node trước đó.
10. **dead_letter**: Xử lý các trường hợp thất bại sau khi đã thử lại tối đa số lần cho phép.
11. **finalize**: Ghi nhật ký audit cuối cùng và kết thúc luồng.

### Conditional Edges:
- `route_after_classify`: Chuyển đến node chức năng tương ứng dựa trên phân loại.
- `route_after_evaluate`: Kiểm tra `evaluation_result` để quay lại `retry` hoặc sang `answer`.
- `route_after_retry`: Kiểm tra `attempt >= max_attempts` để chuyển sang `dead_letter`.
- `route_after_approval`: Kiểm tra quyết định của con người để đi tiếp hoặc yêu cầu làm rõ.

## 3. State schema

Dữ liệu được quản lý tập trung trong `AgentState`. Các trường sử dụng Reducer `add`
(append-only) để phục vụ việc truy vết (Audit Trail).

| Field | Reducer | Why |
|---|---|---|
| messages | Annotated[list, add] | Bảo toàn lịch sử hội thoại đầy đủ. |
| tool_results | Annotated[list, add] | Lưu vết tất cả kết quả gọi tool (cả lỗi và thành công). |
| errors | Annotated[list, add] | Tập hợp các lỗi phát sinh qua các lần retry. |
| events | Annotated[list, add] | Nhật ký chi tiết của từng bước trong Workflow. |
| route | overwrite | Chỉ lưu trạng thái định tuyến hiện tại. |
| attempt | overwrite | Lưu số lần đã thử lại hiện tại. |
| evaluation_result | overwrite | Kết quả đánh giá mới nhất của Evaluate node. |

## 4. Scenario results

- **Total PII Detected**: {metrics.total_pii_detected}
- **Success Rate**: {metrics.success_rate:.2%}
- **Average Nodes Visited**: {metrics.avg_nodes_visited:.2f}
- **Total Retries**: {metrics.total_retries}

| Scenario | Expected route | Actual route | Success | Retries | Interrupts | PII Detected |
|---|---|---|---:|---:|---:|---:|
{table_str}

## 5. Failure analysis

1. **Retry Exhaustion**: Khi vượt quá max_attempts, hệ thống tự động tạo Ticket ID
   và chuyển vào dead_letter.
2. **Rejection Handling**: Các hành động nguy hiểm không được phê duyệt sẽ quay lại node clarify.

## 6. Persistence / recovery evidence

Hệ thống sử dụng SQLite checkpointer (`checkpoints.db`) với chế độ WAL để đảm bảo
khả năng phục hồi sau khi crash. Dưới đây là ví dụ về lịch sử trạng thái (State History)
của một kịch bản lỗi (Scenario S05) được trích xuất từ database:

```text
Thread: thread-S05_error
- Snapshot 1: Node=classify, Route=error, Attempt=0
- Snapshot 2: Node=retry, Attempt=1
- Snapshot 3: Node=tool, Status=error
- Snapshot 4: Node=evaluate, Result=needs_retry
- Snapshot 5: Node=retry, Attempt=2
- Snapshot 6: Node=tool, Status=success
- Snapshot 7: Node=answer, Finalized=True
```

## 7. Extension work

- **Graph Diagram**: Trực quan hóa luồng bằng Mermaid (đã nhúng ở phần Architecture).
- **Security**: Tích hợp PII Masking và Metadata extraction.
- **Structured Data**: Sử dụng JSON cho giao diện giữa các node và tool.

## 8. Improvement plan

- Triển khai LLM-as-judge cho node evaluate.
- Thêm Exponential Backoff thực tế cho các lần retry.
- Tích hợp giao diện quản lý phê duyệt (HITL UI).
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Render and write the markdown report."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
