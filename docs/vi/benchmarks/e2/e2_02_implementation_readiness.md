# E2-02..04 — Contract cognitive role và task signal

**Ngày review:** 2026-09-08  
**Baseline:** `2c4a81f` cộng working tree  
**Điều kiện:** E0 + E1 phải `VERIFIED` trước khi kích hoạt  
**Kết quả hiện tại:** `PARTIAL` — value contract đã có test, nhưng E1 chưa
verified và chưa có wiring runtime E2.

Tên file lịch sử được giữ để không làm hỏng liên kết. File này **không** định
nghĩa `ImplementationReadiness`; lifecycle đó thuộc E2-25..E2-28 và E2-47. Nó
cũng không cho phép routing, escalation, persistence hoặc provider call.

## Quyền sở hữu

| Khái niệm | Owner canonical | Boundary hiện tại |
|---|---|---|
| Từ vựng model routing lịch sử | `paw.core.models.ModelRole` | Tương thích manifest hiện có; không tạo enum mới. |
| Contract cognitive role E2 | `paw.core.reasoning_contracts.RoleContract` | Một registry bất biến, import tường minh từ module owner. |
| Taxonomy privacy | `paw.core.privacy.PrivacyClass` | Task signal tái dùng; không có `PrivacyLevel`. |
| Task signal E2 | `paw.core.reasoning_contracts.TaskSignals` | Chỉ là value input bất biến, không có decision method. |
| Phân loại research depth | Owner E2-29 tương lai | E2-04 chưa triển khai. |
| Quyết định escalation | Runtime/Autonomy/Model Router theo Architecture | E2-04 chưa triển khai. |

`paw.core.__all__` giữ đúng 11 symbol runtime đã ratify. Contract E2 phải import
từ module chuyên trách, không mở rộng package root.

## E2-02: cognitive role tối thiểu

PAW tái dùng bốn giá trị `ModelRole` cho vòng lặp kỹ thuật tối thiểu:

- `FAST`: classification có giới hạn và tổng hợp ngắn cho việc rủi ro thấp;
- `REASONING`: nghiên cứu, chẩn đoán và đánh giá phương án kiến trúc;
- `CODING`: proposal triển khai/review có nguồn;
- `TOOLS`: proposal operation có cấu trúc, không bao giờ là quyền thực thi.

`VISION` và `EMBEDDING` là modality/capability; `FALLBACK` là hành vi routing.
Chúng vẫn là giá trị manifest lịch sử để giữ tương thích, nhưng không thành
cognitive role riêng trong tập tối thiểu E2.

## E2-03: output, evidence và uncertainty

Mỗi role có một `RoleContract` frozen gồm description, scenario tag, output
schema, yêu cầu evidence/citation, loại evidence cho phép, confidence threshold
và disposition khi confidence thấp (`STOP`, `ASK`, `ESCALATE`). Reasoning trả
`reasoning_assessment`, không yêu cầu hidden chain-of-thought. Assessment phải
cho thấy evidence reference, kết luận phương án, uncertainty quan trọng và next
action đề xuất; nó không authorize tool hoặc mutation. Coding trả
`implementation_proposal` và cần evidence source/test/decision cùng citation.

Registry dùng `MappingProxyType`; constructor từ chối threshold ngoài `[0,1]`,
citation không có evidence hoặc role yêu cầu evidence nhưng không khai báo loại
evidence.

## E2-04: task signal

`TaskSignals` ghi:

- novelty: `UNKNOWN`, `ROUTINE`, `FAMILIAR`, `NOVEL`, `UNPRECEDENTED`;
- impact: `UNKNOWN`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`;
- privacy: `PrivacyClass` canonical;
- context: `UNKNOWN`, `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`;
- budget còn lại: `UNKNOWN`, `WITHIN_LIMIT`, `NEAR_LIMIT`, `EXHAUSTED`;
- uncertainty tùy chọn trong `[0,1]` và token estimate không âm.

Default unknown là chủ ý fail-closed: thiếu reconnaissance không được hiểu thành
task routine/public/low-impact. `TaskSignals.complete` chỉ báo input đã đủ; nó
không phân loại `FAST`/`STANDARD`/`DEEP`, yêu cầu escalation hoặc chọn model.
Các hành vi đó lần lượt thuộc E2-29, E2-11 và E2-06.

Focused contract test có thể pass cho repair value contract, nhưng E2-02..04 vẫn
để unchecked cho tới khi E1 `VERIFIED` và contract được review lại trên revision
đó.
