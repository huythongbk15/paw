# Quy tắc kỹ thuật PAW

Các quy tắc này áp dụng cho cả con người và coding agent. Mục tiêu là giữ
runtime hội tụ trong giai đoạn ổn định hóa.

## Kiểm tra owner trước mỗi thay đổi

Trước khi sửa:

1. Nêu outcome người dùng và bất biến kiến trúc bị tác động.
2. Tìm owner canonical trong `IMPLEMENTATION_MAP.md` và mã nguồn.
3. Tìm mọi definition, import, caller, đường persistence và test liên quan.
4. Phân loại thay đổi: repair, contract migration, quyết định kiến trúc hay
   feature trì hoãn.
5. Liệt kê file tối thiểu cần sửa và lệnh nghiệm thu.

Nếu chưa có owner rõ ràng, cập nhật map để làm rõ ownership trước khi viết code.
Thiếu owner không phải lý do để tạo thêm manager.

## Kiểm soát phạm vi

- Một thay đổi nên giải quyết một vấn đề hệ thống.
- Không trộn baseline repair, contract refactor và product behavior mới nếu
  không cần để kiểm thử.
- Không tạo runtime, planner, context builder, router, store hoặc status enum thứ hai.
- Compatibility layer phải nêu canonical target và điều kiện xóa.
- Mọi core abstraction, production dependency, schema, adapter type hoặc runtime
  entry point mới phải có architecture decision và cập nhật tài liệu canonical.
- Nhãn phase lịch sử chỉ dùng trong history, không dùng cho docstring, contract
  API hoặc tuyên bố hoàn thành.

## Trigger cần review tăng trưởng

Đây là tín hiệu cần review, không tự động là lỗi style:

- sửa production file đã quá 500 dòng;
- thêm hơn 150 dòng vào một production module hiện có;
- export thêm public symbol từ bề mặt `paw.core` rộng;
- chạm hơn ba core subsystem cho một behavior;
- thêm mutable global state hoặc singleton;
- thêm DDL, provider call hoặc `except Exception` rộng trong core execution.

Khi trigger xảy ra, giải thích vì sao owner vẫn cohesive, phần nào có thể tách/xóa
và thay đổi tránh tạo nhánh song song như thế nào.

## Quy tắc runtime

- `PawRuntime` là authority điều phối application. Service khác chỉ trả decision/data,
  không âm thầm khởi chạy loop.
- Single task và graph node dùng chung proposal, gate, execution và observation pipeline.
- Provider/model call là operation có capability, privacy và resource requirement;
  không phải helper planning vô hại.
- Policy tạo một verdict. Autonomy nhận verdict đó và quyết định có tiếp tục.
- ASK ghi request rồi dừng. Approval phải trỏ đúng proposal; interactive mode không
  tự được coi là quyền.
- Capability Router chọn executor; Model Router chọn model.
- No-op, echo hoặc chỉ nạp instruction phải gắn nhãn rõ, không được báo là external
  action đã hoàn thành.
- Mọi retry/resume dùng idempotency key ổn định.

## Quy tắc domain và API

- Mỗi khái niệm PAW-owned có một enum/model canonical.
- Dùng boundary có kiểu cho proposal, observation, result, error và stop reason.
- Normalize dictionary của adapter tại port boundary.
- Domain contract độc lập với SQLite, Typer và package provider.
- Không re-export helper nội bộ; public symbol mới phải có use case và contract test.
- Không âm thầm đổi enum đã persist hoặc serialized field; phải có migration.

## Quy tắc persistence

- Schema và migration có một owner.
- Feature code không chạy `CREATE`, `ALTER` hoặc `DROP` trong request path bình thường.
- Mọi write có transaction tường minh và commit trước khi trả success.
- Kiểm tra durability bằng cách đóng rồi mở lại database.
- Initialization không phá dữ liệu và có thể chạy lặp.
- Checkpoint phải chứa hoặc trỏ tới đủ state để resume; counter trong memory không đủ.
- Ledger, task state và operation record phải có semantics atomic/recovery được mô tả.

## Quy tắc test

Debug có hệ thống:

```text
REPRODUCE -> LOCALIZE -> ROOT CAUSE -> INVARIANT -> MINIMAL FIX -> REGRESSION PROOF
```

Repair quan trọng phải chứng minh regression fail trước fix và pass sau fix.
Negative control bắt buộc gồm:

- thiếu source/input bắt buộc làm test fail;
- DENY và ASK không chạm side-effect mock;
- process restart không lộ write chưa commit;
- cùng idempotency key không lặp operation đã hoàn tất;
- graph node bắt buộc lỗi sẽ block dependent;
- payload context cuối không vượt budget sau khi nạp skill body;
- source scan chạy trên tập file runtime không rỗng;
- package contents và CLI được test ngoài repository.

Lệnh nghiệm thu tối thiểu:

```bash
python -m pytest -q <focused tests>
python -m pytest -q
python -m ruff check .
python -m build
```

Sau đó cài wheel vào môi trường sạch và smoke-test CLI/import bị ảnh hưởng. Khi
chưa có project-only lock và setup command, báo lỗi setup là `BLOCKED`; không dùng
`requirements.lock.txt` snapshot của host để thay thế.

## Quy tắc tài liệu

- Source reality đổi thì cập nhật `IMPLEMENTATION_MAP.md`.
- Contract đổi thì cập nhật `ARCHITECTURE.md`.
- Scope hoặc priority đổi thì cập nhật charter/roadmap.
- API example là documentation test; snippet chưa được CI chạy thì chưa gọi là runnable.
- Không thêm overview hoặc roadmap khác; mở rộng bộ canonical hiện tại.
- Không tuyên bố `PASS` dựa trên code inspection, log cũ hoặc subset test.
- Cập nhật bản tiếng Việt tương ứng trong cùng thay đổi.

## Mẫu bàn giao bắt buộc

Mỗi handoff phải gồm:

- **Outcome:** behavior nào hiện đã có;
- **Invariant:** quy tắc kiến trúc nào được bảo vệ/sửa;
- **Scope:** file và contract đã thay đổi;
- **Verification:** lệnh và kết quả trên revision hiện tại;
- **Status:** `PASS`, `PARTIAL`, `FAIL` hoặc `BLOCKED`;
- **Known gaps:** rủi ro còn lại và task an toàn tiếp theo.

Nếu còn critical safety/durability gate fail, status tổng thể không được trình bày
là thành công của dự án.
