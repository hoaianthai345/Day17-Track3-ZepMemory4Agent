# Lab 17 — Submission

## Bài toán

Agent chỉ nhìn thấy context hiện tại sẽ dễ quên preference, open loop, sự kiện ở session cũ và kiến thức domain. Lab xây dựng multi-memory agent để truy hồi đúng loại thông tin trước khi đưa vào model.

## Solution

- Short-term: local sliding window và compaction cho hội thoại hiện tại.
- Long-term: Zep user graph, Context Block, facts và open loops.
- Episodic: Zep episodes để truy lại trajectory/incident.
- Semantic: standalone Zep graph cho policy/domain knowledge dùng chung.
- ContextBudgetManager ghép theo thứ tự short-term → long-term → episodic → semantic và giới hạn 10%/4%/3%/3%.

## Kết quả

Practice student benchmark đạt 11/11 PASS, evidence hit rate 100%. No-memory baseline đạt 2/11; memory-enabled tăng 81.8 điểm phần trăm. Unit test đạt 11 passed, 1 skipped. Golden set v3 chạy được 19/20; G18 thiếu literal marker `BUDGET-10-4-3-3`, nên chưa đạt bonus 20/20.

## Nhận xét

Zep giảm công sức tự xây graph memory và Context Block, nhưng có latency/network cost. Thiết kế hybrid hợp lý: local short-term cho tốc độ, Zep cho durable memory, Redis/Qdrant làm baseline hoặc fallback. Benchmark chấm evidence deterministic, vì vậy tách retrieval khỏi generation giúp xác định lỗi rõ hơn.

## Demo

- UI: `http://localhost:8501`
- Slides: `http://localhost:8502/presentation.html`
- Demo cases: E02 → E04 → E06 → E07.
