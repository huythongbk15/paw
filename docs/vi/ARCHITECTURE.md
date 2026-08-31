# Kiến trúc lõi PAW

Tài liệu này định nghĩa contract đích của PAW Core. Nó ổn định và độc lập với
cách sắp xếp file hiện tại; xem [bản đồ triển khai](IMPLEMENTATION_MAP.md) để
biết mã nguồn thực tế đang làm được gì.

## Ranh giới hệ thống

PAW Core nhận mục tiêu người dùng và sở hữu mọi chuyển trạng thái dẫn đến kết
quả cuối của task. PAW có thể gọi provider/executor thay thế được qua port,
nhưng adapter không quyết định policy, task state hoặc resume.

```text
CLI / library caller
        |
        v
ChatService / application runtime -----------------------------+
        |                                                      |
        +--> Task + Task Graph                                 |
        +--> Context Compiler <--> Memory / Knowledge / Skills |
        +--> Operation Proposal                                |
        +--> Policy Gate --> Autonomy Gate                     |
        +--> Capability Router --> Executor port               |
        +--> Model Router ------> Model provider port           |
        +--> Observation --> Progress evaluation -------------+
        |
        +--> Ledger + checkpoint + operation records
```

SQLite là adapter lưu bền vững mặc định. Ollama là một model-provider adapter
tùy chọn. Không adapter nào thuộc domain model.

## Hướng phụ thuộc

Các lớp khái niệm gồm:

1. **Domain contracts** — identifier, task/graph state, capability,
   policy/autonomy decision, proposal, observation và result; không chứa DB,
   CLI, provider hay executor.
2. **Core services** — planning, skill selection, context compilation, policy,
   autonomy, routing và progress evaluation; phụ thuộc contract và port.
3. **Application runtime** — owner duy nhất của execution state machine và thứ
   tự transaction; ghép các core service, không tạo loop cạnh tranh.
4. **Ports và adapters** — store, SQLite, model provider, executor và CLI; phụ
   thuộc vào contract PAW, không kéo type riêng vào Core.

Điều quan trọng là hướng import và quyền sở hữu, không phải chỉ vị trí thư mục.

## Contract runtime canonical

Single task và graph node dùng cùng một logical loop. Graph chỉ thay đổi cách
chọn unit sẵn sàng tiếp theo; không tạo pipeline an toàn/execution khác.

```text
1. Nạp hoặc tạo Task state bền vững
2. Chọn TaskNode sẵn sàng (hoặc chính task)
3. Tìm skill và biên dịch context theo budget
4. Đề xuất operation kế tiếp
5. Ủy quyền proposal qua Policy
6. Autonomy quyết định có được tiếp tục không
7. CapabilityRouter chọn executor
8. ModelRouter chọn model khi operation thực sự cần
9. Thực thi một lần với idempotency key
10. Ghi observation và operation completion một cách nguyên tử
11. Đánh giá progress, dependency và trạng thái cuối
12. Ghi checkpoint và ledger event
13. CONTINUE, REPLAN, WAIT, ESCALATE hoặc STOP
```

Nếu bước 4 cần model/provider, đó cũng là operation phải qua policy, privacy và
budget trước network hoặc chi phí. “Planning” không phải ngoại lệ của side-effect
gate.

## Operation envelope

Mọi executable unit, kể cả model call, có một proposal có kiểu với:

- task/node/operation identifier ổn định;
- operation kind và intent tường minh;
- capability cần thiết;
- input/context reference, không dùng global state ẩn;
- resource ước tính và yêu cầu privacy;
- skill, model role và executor constraint nếu có;
- idempotency key ổn định qua retry/resume.

Execution trả về observation có kiểu gồm success/failure, result, artifact,
resource usage, retryability, progress signal và typed error. Dictionary tùy ý
chỉ được phép ở biên adapter và phải normalize trước khi vào runtime state.

## Quyền quyết định

| Quyết định | Owner duy nhất | Ghi chú |
|---|---|---|
| Action có được phép không? | Policy Engine | `ASK` là wait state, không phải permission ngầm. |
| Loop có tiếp tục không? | Autonomy Controller | Dựa trên budget, progress, repetition, stall và terminal state. |
| Executor nào làm được? | Capability Router | Ghép capability, risk, privacy, cost và availability. |
| Model nào suy luận? | Model Router | Ghép cognitive role/provider; không chọn executor. |
| Context nào được gửi? | Context Compiler | Áp budget, lý do chọn và provenance. |
| DAG chạy gì tiếp? | Task Scheduler | Tôn trọng dependency và failure propagation. |
| Điều gì đã xảy ra? | Task Ledger | Audit append-oriented, không phải long-term memory. |
| Resume từ đâu? | Checkpoint/operation store | Runtime state bền vững và key đã hoàn thành. |

Service có thể yêu cầu quyết định từ owner khác nhưng không được sao chép logic.

## Task và runtime state

PAW dùng một task status canonical:

```text
PENDING -> RUNNING -> COMPLETED
                  \-> FAILED
                  \-> PARTIAL
                  \-> BLOCKED
                  \-> WAITING_APPROVAL
                  \-> PAUSED / CHECKPOINTED -> RESUMING -> RUNNING
                  \-> CANCELLED
```

Autonomy decision không phải task status. `WAIT`, `REPLAN` hay `STOP` phải tạo
chuyển trạng thái tường minh và stop reason có kiểu.

Đối với graph:

- node chỉ ready khi mọi predecessor bắt buộc đã completed;
- predecessor bắt buộc lỗi sẽ block dependent;
- optional dependency phải khai báo rõ;
- cycle và dependency thiếu bị từ chối trước persistence/execution;
- graph không thể thành công nếu node bắt buộc lỗi hoặc chưa chạy;
- resume khôi phục node state và operation key, không chỉ thứ tự graph.

## Bất biến an toàn

Đây là các nguyên tắc hiến định. Vi phạm một nguyên tắc làm gate liên quan
`FAIL`, dù test khác vẫn xanh:

1. **Một contract:** mỗi khái niệm có một type/implementation canonical.
2. **Policy trước effect:** write, process, network/model call và thao tác hủy
   không chạy trước Policy.
3. **ASK phải chờ:** ASK ghi approval request bền vững; chỉ approval khớp
   proposal chính xác mới được resume.
4. **Autonomy có giới hạn:** mọi đường runtime có hard bound và stop reason có kiểu.
5. **Routing độc lập:** capability và model routing không thay thế nhau.
6. **Acknowledge sau durability:** chỉ báo thành công sau khi observation và
   operation record commit.
7. **Resume idempotent:** retry/resume dùng lại operation key, không lặp effect.
8. **Failure propagation:** node bắt buộc lỗi phải block dependent và ngăn false success.
9. **Context giải thích được:** fragment có provenance, score, reason; payload
   cuối không vượt budget.
10. **Adapter isolation:** type provider không rò vào domain và không sở hữu state PAW.
11. **Decision quan sát được:** ledger dựng lại được proposal, gate, chọn, chạy và stop.
12. **Khởi tạo không phá dữ liệu:** migration/initialization không drop bảng user.
13. **Input approval bất biến:** runtime resume không mutate `ProposedAction` đã approve.

## Contract persistence

Schema có một owner tập trung. Module tính năng chỉ định nghĩa repository/store
interface, không tự tạo hoặc drop bảng trong request path.

Yêu cầu chính:

- schema version rõ ràng và migration tuần tự, idempotent;
- mọi write có transaction boundary tường minh;
- store không báo durable trước commit;
- checkpoint chứa task/node state, autonomy usage, detector state, context
  reference và operation key đã hoàn thành;
- ledger, operation completion và state transition commit cùng nhau hoặc có
  recovery rule rõ;
- test durability phải đóng rồi mở lại SQLite.

## Context, memory và knowledge

- **Context** là payload giới hạn cho quyết định hiện tại.
- **Memory** lưu fact về user/project và kinh nghiệm đáng nhớ.
- **Knowledge** lưu source, chunk, evidence và citation.
- **Ledger** lưu những gì PAW đã làm.
- **Skill** lưu cách áp dụng capability.

Các store chỉ cung cấp candidate cho `ContextCompiler`; không đổ toàn bộ nội
dung vào prompt. Retrieval và budget payload cuối là hai bước riêng; nạp skill
body cuối cùng phải re-budget.

## Port mở rộng

Boundary ổn định gồm:

- `ModelProvider`: discover/health/complete/embed/stream nếu hỗ trợ;
- `Executor`: khai báo capability và thực thi proposal đã approve;
- `SkillProvider`: discover/import skill manifest đã normalize;
- memory/knowledge repository: retrieve/persist record do PAW sở hữu.

Thêm adapter không được yêu cầu thêm task, policy, context hay checkpoint type.

## Bề mặt application công khai

Bề mặt dự kiến nhỏ:

- tạo/nạp session và task;
- run hoặc resume qua runtime canonical;
- xem task state, ledger, checkpoint và approval request;
- cấu hình policy, skill, provider và execution profile bằng contract có kiểu.

Bề mặt source-backed đầu tiên là `paw.application.chat.ChatService`, được expose
qua `paw chat`. Service này lưu transcript như application projection; Session,
Task, Policy, Approval, Ledger và Checkpoint vẫn do Core sở hữu.

Không coi helper module hoặc wildcard export rộng là public API. Chỉ ổn định API
sau khi track hợp nhất contract trong `ROADMAP.md` hoàn tất.
