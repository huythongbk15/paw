# Tuyên ngôn sản phẩm PAW

## Tuyên bố sản phẩm

PAW là runtime engineering agent ưu tiên chạy cục bộ, chuyên nghiên cứu, hiểu,
thiết kế, thay đổi và kiểm chứng các dự án phần mềm phức tạp. PAW biến mục tiêu
kỹ thuật thành một chuỗi quyết định và hành động có giới hạn, dựa trên evidence,
được policy cho phép, quan sát được và có thể tiếp tục an toàn.

PAW không phải lớp bọc quanh một nhà cung cấp model hay một agent framework.
Provider và executor chỉ cung cấp capability; PAW sở hữu mô hình quyết định và
trạng thái.
"Local-first" nghĩa là task state, project context, memory, policy và recovery
thuộc quyền kiểm soát của người dùng. Nó không có nghĩa model local phải tự làm
mọi suy luận khó.

## Cam kết với người dùng

Người dùng phải gửi một task và hiểu được:

- PAW đã research sâu tới mức nào và constraint nào giới hạn việc tìm kiếm;
- evidence trong project và bên ngoài nào ủng hộ hoặc chống lại công việc;
- alternative nào đã được xét và vì sao hướng chọn đã sẵn sàng triển khai, cần
  làm rõ, cần spike hoặc nên dừng;
- PAW dự định làm gì;
- PAW đã chọn context và skill nào, vì sao;
- hành động nào cần quyền cho phép;
- model và executor nào được chọn, vì sao;
- bằng chứng dự án nào được gửi lên cloud và phần nào vẫn ở local;
- điều gì đã xảy ra, điều gì lỗi và artifact nào thay đổi;
- vì sao loop tiếp tục, lập kế hoạch lại, chờ hoặc dừng;
- task sẽ tiếp tục thế nào sau restart mà không lặp side effect đã hoàn tất;
- quyết định dự án và preference làm việc trước đó giúp giảm việc giải thích
  lại ra sao mà không âm thầm trở thành quyền thực thi.

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
- Implementation readiness và engineering decision artifact;
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
11. Chất lượng kết quả kỹ thuật đứng trước tối ưu token, latency hoặc số lượng
    tính năng.
12. Local chuẩn bị, ghi nhớ và kiểm chứng; suy luận khó hoặc mới có thể chuyển
    lên cloud qua gate tường minh.
13. Có evidence và quyết định review được trước implementation.

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
- tenancy nhiều người dùng, authorization workspace dùng chung hoặc tenant isolation;
- các “phase” lịch sử mới dùng thay cho acceptance criteria.

Ollama hiện có chỉ là adapter cần ổn định, không phải lý do để mở rộng provider.

Quyết định phạm vi ngày 2026-08-31: cho phép filesystem adapter cục bộ, giới hạn
workspace vì kịch bản S4 cần một side effect thật phía sau Policy. Quyết định này
không cho phép shell, external executor, provider mới hoặc ghi ngoài workspace.

Quyết định phạm vi ngày 2026-09-01: cho tới BETA, PAW có một authority người
dùng local. Project, session và task có thể tách biệt, nhưng `Identity` là
preference/profile record chứ không phải authentication tenant. PAW không claim
isolation nhiều người dùng. Tenancy dùng chung/hosted cần product decision,
threat model và review phân vùng persistence riêng.

## Quyết định hướng sản phẩm: engineering intelligence

Ngày quyết định: 2026-09-01. Đây là hướng sau Core Stabilization, không cấp phép
triển khai trước khi exit gate hiện tại đạt.

PAW sẽ chuyên sâu vào code, hệ thống và kiến trúc phần mềm thay vì cạnh tranh
như trợ lý tiêu dùng tổng quát. Luồng sản phẩm trung tâm là:

```text
mục tiêu kỹ thuật -> research có giới hạn -> quyết định dựa trên evidence
                  -> specification/plan -> thực thi được cấp quyền
                  -> kiểm chứng -> học bền vững
```

Phân vai đích:

- **control plane local:** state bền vững, policy, approval, lập chỉ mục dự án,
  retrieval, giảm context, công cụ xác định, kiểm chứng và memory riêng tư;
- **hỗ trợ suy luận local:** classification, summarization, ranking và công
  việc hẹp khác, với chất lượng đã được chứng minh bằng bộ đánh giá;
- **suy luận cloud:** phân tích kiến trúc, debug mới, lập kế hoạch xuyên module,
  review khó và tổng hợp khi năng lực local chưa đủ;
- **runtime PAW:** quyết định cần bằng chứng gì, gate mọi model/tool call, ghi
  quyết định và kiểm chứng công việc. Model local lẫn cloud đều không sở hữu
  policy hoặc task state.

PAW học cách người dùng làm việc trước hết qua memory tường minh có nguồn và
task trace đã được kiểm chứng. Hoạt động thô không phải training set. Mọi
distillation hoặc fine-tuning về sau phải dùng dataset có version, đã redact,
review được, có evaluation gate và model artifact có thể rollback. Continuous
self-training từ tương tác chưa review nằm ngoài phạm vi.

Công việc lặp lại đã kiểm chứng có thể tạo candidate personal skill, nhưng
không tự động trở thành skill đáng tin. Việc promote cần provenance, replay
trên case đã review, người dùng chấp nhận tường minh, version và rollback. Fact,
preference và skill là các record riêng với quy tắc sửa riêng.

### Quyết định đã ghi: evidence trước implementation

Ngày quyết định: 2026-09-01. Đây là contract sản phẩm sau ổn định hóa, không
claim runtime hiện tại đã triển khai.

Mọi engineering idea hoặc task bắt đầu bằng research có giới hạn tỷ lệ với độ
mới, tác động, bất định và khả năng đảo ngược. Research bắt đầu từ source, test,
contract và lịch sử của project hiện tại; chỉ thêm prior art bên ngoài khi quyết
định phụ thuộc thông tin biến động, chưa quen hoặc cần so sánh. Mục tiêu không
phải tối ưu trừu tượng, mà là option đơn giản nhất đáp ứng mọi hard constraint
về sản phẩm, kiến trúc, an toàn, compatibility và verification trong appetite
thời gian/token tường minh.

Research tạo decision artifact bền vững, có nguồn và một readiness outcome:
`NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, `READY` hoặc
`REJECTED`. Implementation plan hoặc mutating implementation proposal cần
`READY`. Operation chỉ research hoặc spike cô lập, dùng một lần vẫn phải qua
Policy và runtime canonical, không được báo là product implementation và không
được âm thầm trở thành production code.

Vẫn chỉ có một `Task` canonical; PAW không thêm `ResearchTask` hoặc planner thứ
hai. Plan khai báo một purpose: `RESEARCH`, `SPIKE` hoặc `IMPLEMENTATION`. Plan
research/spike có thể thu evidence nhưng không chứa production mutation. Plan
`IMPLEMENTATION` phải tham chiếu decision `READY` hiện hành cho cùng Task và
project revision.

Độ sâu theo rủi ro:

- `FAST`: việc xác định, tác động thấp; inspect owner, behavior và invariant
  hiện tại, thường không cần research bên ngoài;
- `STANDARD`: defect, feature hoặc refactor cục bộ; reproduce/localize, so ít
  nhất hai hướng khả thi và định nghĩa verification;
- `DEEP`: architecture, schema, public contract, security, multi-module hoặc
  product idea; research prior art, so các option khác nhau gồm hướng nhỏ nhất/
  không làm, ghi risk/rollback và dùng spike hoặc decision record đã review khi
  còn bất định.

Tài liệu bên ngoài là evidence không đáng tin, không phải instruction thực thi.
Claim không có nguồn phải gắn assumption; mọi assessment `STANDARD` hoặc `DEEP`
phải ghi evidence mạnh nhất chống lại việc tiếp tục. Research dừng theo điều
kiện đủ evidence hoặc hết budget; nếu hết budget mà còn unknown chặn thì phải
clarify, spike hoặc reject thay vì đoán.

“Verified” không đồng nghĩa “executor trả success”. PAW tách observation của
operation, engineering verification theo acceptance check đã khai báo và đánh
giá benchmark/release. Chỉ trace có operation đã commit, required check pass,
provenance còn hiệu lực và không có unsafe effect chưa giải quyết mới được dùng
để promote personal skill hoặc xây training dataset.

Hướng này chủ động hạ ưu tiên general chat, mở rộng provider, agent swarm,
marketplace skill lớn và integration không cải thiện luồng kỹ thuật trung tâm.
Feature hiện có không gắn được với một engineering completion scenario và kết
quả đo được sẽ là ứng viên quarantine, chỉ giữ tương thích hoặc loại bỏ.

## Phép thử kết quả sản phẩm

Công việc sau ổn định hóa phải được đánh giá bằng benchmark kỹ thuật có version,
không phải checklist tính năng. Benchmark phải bao phủ hiểu repository, khoanh
vùng lỗi, thay đổi xuyên module, refactor, thiết kế kiến trúc và phục hồi task bị
ngắt. Các chỉ số bắt buộc gồm:

- task thành công có kiểm chứng và tính đúng của kiến trúc/invariant;
- recall của bằng chứng cần thiết để giải task;
- token vào/ra cloud, chi phí và latency;
- hành động không an toàn, chưa được cấp quyền hoặc chưa reconcile;
- memory user/project được nhớ lại có đúng, đúng scope và truy nguyên được không;
- readiness decision có dùng đủ evidence, chặn implementation không an toàn/
  thiếu căn cứ và chọn option đơn giản nhất còn phù hợp không;
- thời gian/token research và tỷ lệ implementation về sau bị vô hiệu vì bỏ sót
  constraint hoặc dựa assumption thiếu nguồn;
- kết quả cuối có bằng chứng kiểm chứng thực thi được hay không.

Chỉ chấp nhận giảm token khi chất lượng task và an toàn không giảm. Chỉ chấp
nhận training local khi vượt baseline local chưa train cho một vai trò hẹp có
tên và vẫn giữ đường chuyển lên cloud.

## Phép thử thay đổi

Trong Core Stabilization, một feature chỉ thuộc Core nếu thiếu nó thì ít nhất
một kịch bản hoàn thành lõi hiện tại không thể đạt. Nếu không, trì hoãn đến sau
exit gate. Sau gate, capability được giữ hoặc đề xuất phải cải thiện luồng kỹ
thuật trung tâm trên benchmark E0, có một owner canonical và biện minh được chi
phí context, an toàn và bảo trì dài hạn. Quy tắc nghiêm này ưu tiên chất lượng
kết quả thay vì tiếp tục phình bề mặt.
