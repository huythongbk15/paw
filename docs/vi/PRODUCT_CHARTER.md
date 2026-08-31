# Tuyên ngôn sản phẩm PAW

## Tuyên bố sản phẩm

PAW là runtime agent cá nhân, ưu tiên chạy cục bộ. PAW biến mục tiêu của người
dùng thành một chuỗi hành động có giới hạn, được policy cho phép, quan sát
được và có thể tiếp tục an toàn.

PAW không phải lớp bọc quanh một nhà cung cấp model hay một agent framework.
Provider và executor chỉ cung cấp capability; PAW sở hữu mô hình quyết định và
trạng thái.

## Cam kết với người dùng

Người dùng phải gửi một task và hiểu được:

- PAW dự định làm gì;
- PAW đã chọn context và skill nào, vì sao;
- hành động nào cần quyền cho phép;
- model và executor nào được chọn, vì sao;
- điều gì đã xảy ra, điều gì lỗi và artifact nào thay đổi;
- vì sao loop tiếp tục, lập kế hoạch lại, chờ hoặc dừng;
- task sẽ tiếp tục thế nào sau restart mà không lặp side effect đã hoàn tất.

Đường chạy mặc định phải hoạt động cục bộ với SQLite và fallback xác định. Cloud
provider có thể nâng chất lượng nhưng không được sở hữu task state, policy hoặc
resume semantics.

## Quyền sở hữu lõi

PAW độc quyền sở hữu các khái niệm sau:

- Identity và preference;
- Session và Task;
- Plan và Task Graph;
- Skill Fabric;
- Context Compiler;
- primitive Memory và Knowledge;
- Policy Engine và approval state;
- autonomy budget, progress và stop decision;
- Capability Router và Model Router;
- Executor và provider port;
- Observation, Task Ledger và artifact;
- Checkpoint, operation record và resume semantics.

Hệ thống bên ngoài có thể triển khai một port, nhưng không được đưa vào Core một
task model, policy model, memory model, context model hoặc checkpoint model song
song.

## Nguyên tắc sản phẩm

1. An toàn trước side effect.
2. Mỗi khái niệm chỉ có một contract canonical.
3. State tường minh và boundary có kiểu.
4. Hành vi xác định trước, model chỉ hỗ trợ khi cần bất định.
5. Context tối thiểu nhưng đủ và giải thích được.
6. Autonomy có giới hạn, stop reason hiển thị được.
7. Ghi state bền vững trước khi báo đã tiến triển.
8. Provider và executor có thể thay thế.
9. Ưu tiên CLI và library; không yêu cầu daemon.
10. Tin bằng chứng, không tin nhãn phase hoặc số lượng tính năng.

## Các kịch bản hoàn thành lõi

Core chưa ổn định cho đến khi tất cả kịch bản sau được kiểm chứng trong môi
trường cô lập:

1. Task cục bộ đi từ tạo đến kết quả cuối qua entry point runtime canonical.
2. DENY và ASK đều chặn side effect; ASK đã approve tiếp tục đúng operation đó
   đúng một lần.
3. Chọn context tôn trọng budget token/fragment và giải thích include/exclude.
4. Capability routing chọn executor độc lập với model routing.
5. Restart process khôi phục checkpoint mà không lặp external operation đã xong.
6. DAG hợp lệ chạy đúng dependency; cycle bị từ chối; node lỗi bắt buộc chặn
   dependent và ngăn task báo thành công giả.
7. Ledger tái dựng được proposal, gate, execution, observation và quyết định cuối.
8. Wheel cài trong môi trường sạch và CLI chạy ngoài repository.

## Khóa phạm vi trong Core Stabilization

Cho đến khi exit gate trong `ROADMAP.md` đạt, PAW không mở rộng sang:

- thêm cloud/model provider hoặc coding-agent executor;
- triển khai MCP, browser/GUI automation hoặc multi-agent orchestration;
- worker phân tán, queue, Redis, PostgreSQL, Kafka hoặc Kubernetes;
- vector database hoặc routing adaptive/learned;
- daemon nền hoặc control plane được host;
- các “phase” lịch sử mới dùng thay cho acceptance criteria.

Ollama hiện có chỉ là adapter cần ổn định, không phải lý do để mở rộng provider.

## Phép thử thay đổi

Một feature chỉ thuộc Core nếu thiếu nó thì ít nhất một kịch bản hoàn thành lõi
không thể đạt. Nếu không, trì hoãn đến sau exit gate. Quy tắc nghiêm này giúp
PAW hội tụ thay vì tiếp tục phình bề mặt.
