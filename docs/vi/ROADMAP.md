# Lộ trình Core Stabilization của PAW

Đây là work sequence duy nhất đang hoạt động. Các phase được đánh số trong lịch
sử mô tả cách repository phình lên; chúng không quyết định việc phải xây tiếp.

Track hiện tại: **đưa một candidate Core Stabilization sạch qua SX**. Behavior
sửa S0–S6 là `OBSERVED` trong source hiện tại và lượt full verification gần
nhất trên working tree đã pass trước delta tài liệu/contract-test mới nhất.
Evidence đó không phải proof exit trên revision sạch. SX phải review combined
tree, sửa finding, đóng băng một candidate sạch rồi chạy gate D3 đã lên lịch
trên đúng revision đó.

| Phạm vi | Kết quả hiện tại | Ý nghĩa |
|---|---|---|
| Implementation sửa S0–S6 | `OBSERVED`; đã ghi verification working-tree trước đó | Behavior tồn tại nhưng chưa có evidence cho clean candidate hiện hành. |
| Exit gate Core Stabilization | `PARTIAL` | SX còn 14 item qualification; tiếp theo là `SX-01`. |
| E0–E3 và BETA | `BLOCKED` | Gate SX/track trước bắt buộc chưa pass. |
| E4 controlled adaptation | `BLOCKED`, tùy chọn | Cần E0–E3 và dataset verified; không bắt buộc cho BETA. |

Hướng engineering intelligence ngày 2026-09-01 đã được ghi trong Product
Charter và Architecture. Đây là ràng buộc thiết kế, chưa phải track triển khai
đang hoạt động khi exit gate còn `PARTIAL`.

## Quy tắc trình tự

Hoàn thành track theo thứ tự. Có thể di chuyển trong cùng track, nhưng không bắt
đầu track sau khi item an toàn hoặc durability của track trước còn fail. Nếu đổi
ưu tiên, phải ghi rủi ro và cập nhật roadmap, không âm thầm tạo kế hoạch nhánh.

Đầu việc nguyên tử được theo dõi trong `EXECUTION_CHECKLIST.md`. Mỗi item dùng
mức kiểm chứng theo rủi ro nhỏ nhất có thể bác bỏ invariant của nó. Full suite
và release check chỉ dành cho trigger trong `ENGINEERING_RULES.md`, gồm exit
gate ổn định hóa này và các milestone tích hợp sau gate.

## S0 — Baseline tái lập được

**Mục tiêu:** mọi status tương lai đều tái lập được từ checkout sạch.

**Việc cần làm:**

- duy trì `uv.lock` chỉ dành cho PAW, sinh từ `pyproject.toml`, và chặn freeze
  môi trường host quay lại;
- ghi một đường setup Python 3.12+ cho runtime và dev dependency;
- chạy full test và lint trên revision hiện tại;
- build wheel, cài môi trường sạch và smoke-test CLI ngoài repository;
- ghi nhận lỗi, không sửa hệ thống không liên quan;
- thêm check tự động để docs canonical không tuyên bố phase chưa kiểm chứng hoặc
  trỏ tới module không tồn tại.

**Nghiệm thu:** setup sạch dùng dependency khai báo bởi project; pytest/ruff có
kết quả hiện tại; wheel/import/CLI smoke đã chạy; không có dependency runtime bị
cấm; `IMPLEMENTATION_MAP.md` ghi evidence.

**Kết quả hiện tại:** `uv.lock` là project lock duy nhất, freeze của host đã bị
xóa, test tự động kiểm tra lock bao phủ manifest và chặn snapshot host quay lại.

## S1 — Contract canonical và public ownership

**Mục tiêu:** mỗi khái niệm PAW-owned có một source of truth.

**Việc cần làm:** hợp nhất autonomy/stop/task status; định nghĩa proposal/
executable-task; làm `ContextCompiler` canonical; quy định normalize Evidence /
Citation; tách planner/proposer/scheduler; thu hẹp `paw.core` export; thêm test
phát hiện definition core thứ hai.

**Nghiệm thu:** một definition mỗi type; mọi runtime/policy/checkpoint/test dùng
cùng type; alias tương thích có điều kiện xóa; mỗi Plan đã persist tham chiếu
Task identity canonical hiện hữu, tách với Plan identity; không giấu thay đổi
behavior trong quá trình hợp nhất.

**Kết quả hiện tại:** chỉ `Planner` tạo/lưu `Plan`; decomposition là strategy
thuần, runtime sở hữu action proposal, `TaskScheduler` sở hữu DAG readiness/node
state. `paw.core` cố định ở 11 runtime-contract export.
`normalize_knowledge_result()` là boundary stored-knowledge/result duy nhất và
từ chối provenance hỏng. Phần hợp nhất sole owner đạt `PASS`, nhưng
`Planner.plan()` hiện thay `Task.id` bằng Plan ID và không giữ project identity.
Linkage này là `PARTIAL`, là finding SX-03/SX-10 phải sửa trước khi evidence exit
S1 có thể pass.

## S2 — Toàn vẹn storage và migration

**Mục tiêu:** state cục bộ bền vững qua commit, close, restart và upgrade.

**Việc cần làm:** schema version và migration tập trung; bỏ DDL on-demand; bỏ
destructive graph initialization; giới hạn legacy mutation API; định nghĩa atomic
boundary cho task/operation/checkpoint/ledger; test đóng-mở SQLite.

**Nghiệm thu:** init không drop dữ liệu; write acknowledged sống qua restart;
migration tuần tự/idempotent; không có DDL ngoài schema owner; checkpoint và
operation thấy được sau reopen.

**Kết quả hiện tại:** `RuntimePersistence` có hai SQLite boundary đã test:
observation/artifact/execution event/record của operation và checkpoint/task-
status/terminal event. Failure injection sau operation, checkpoint, task-status
và terminal-ledger chứng minh rollback toàn bộ sau đóng-mở database.

## S3 — Authorization và autonomy

**Mục tiêu:** không side effect hoặc provider cost nào xảy ra trước authorization,
mọi counter có đúng một ý nghĩa.

**Việc cần làm:** model/provider planning call thành operation có gate; Policy
đánh giá một lần; approval ASK bền vững và resume exact-operation; thống nhất
DENY/ASK/SANDBOX/ALLOW; sửa accounting decision/token/model/tool/time/iteration;
restore detector state và chứng minh hard bound.

**Nghiệm thu:** negative control chứng minh DENY/ASK không chạm executor/tool/
network/model; một policy event và autonomy event mỗi proposal; counter khớp
observation; stop/wait typed; ASK approve chạy operation gốc đúng một lần.

## S4 — Execution thật và routing độc lập

**Mục tiêu:** runtime canonical thực hiện approved work qua port thay thế được.

**Việc cần làm:** wire `CapabilityRouter`/`ExecutorRegistry`; normalize output;
model selection độc lập; thay skill echo bằng instruction-only executor hoặc
executor thật; định nghĩa availability/fallback/error không nuốt exception rộng.

**Nghiệm thu:** capability chọn executor tương thích hoặc trả unavailable typed;
model routing không giả capability executor; mock/local integration chứng minh
side effect sau Policy; executor failure tới task/graph/ledger; adapter chỉ dùng
domain contract PAW.

## S5 — Graph, checkpoint và resume dùng một loop

**Mục tiêu:** single task và DAG node dùng chung state machine, khôi phục an toàn.

**Việc cần làm:** factor graph qua canonical unit loop; optional dependency rõ;
persist node status/ready set cùng observation; bỏ proposal-counter skip; restore
task/graph/context/autonomy/detector; test crash trước execution, sau side effect
và trước/sau commit.

**Nghiệm thu:** DAG order, cycle/missing dependency và failure propagation đúng;
node bắt buộc lỗi chặn dependent và task success; restart không lặp side effect;
checkpoint đủ để resume; mọi mode phát cùng chuỗi proposal/gate/execution/
observation event.

**Kết quả hiện tại:** mọi mode dùng `_execute_unit`; operation ID đã hoàn tất ổn
định khi resume. Với filesystem write built-in, PAW commit `EffectIntent`
`prepared` trước invocation. Test close/reopen thật chứng minh final content khớp
được reconcile không gọi executor lần hai; target đã đổi bị chặn ambiguous và
giữ nguyên.

## S6 — Một product slice mạch lạc

**Mục tiêu:** expose core ổn định thành workflow cục bộ có thể dùng.

**Việc cần làm:** CLI/API nhỏ cho create/run/inspect/approve/resume; task result và
ledger dễ hiểu không cần đọc SQLite; một ví dụ offline end-to-end; hiển thị context
explanation, artifact và stop reason.

**Nghiệm thu:** clean install hoàn thành core scenario trong charter; CLI và
library dùng cùng application service/runtime; smoke path không cần provider;
examples/API được test và không để quarantine.

## Exit gate Core Stabilization

Chỉ đề xuất mở rộng khi:

- mọi acceptance S0–S6 đều `VERIFIED` trên cùng revision;
- map không còn safety/durability `FAIL`;
- full test, lint, build và isolated install pass;
- public contract và migration có compatibility test;
- runtime có một orchestration path cho executable unit;
- docs không còn claim giai đoạn/trạng thái hiện tại mâu thuẫn.

Sau exit gate, đánh giá từng adapter/feature theo phép thử thay đổi sản phẩm.
Không tự động tăng phase.

## Trình tự sau gate đã được duyệt — chưa hoạt động

Trình tự này thu hẹp PAW vào giải quyết vấn đề kỹ thuật. Chỉ được bắt đầu sau
khi exit gate Core Stabilization pass trên một revision sạch. Các track có thứ
tự: đo lường và cắt bỏ đi trước behavior model mới; readiness nghiên cứu có
nguồn đi trước kế hoạch triển khai; thích nghi memory/context và personal skill
có quản trị đi trước training.
Đường sản phẩm bắt buộc là E0 → E1 → E2 → E3 → BETA. E4 chỉ có thể bắt đầu sau
E3, nhưng là tùy chọn và không bao giờ là prerequisite của BETA.

Boundary kiến trúc đã được phê duyệt dù implementation còn defer: một Task với
Plan purpose có kiểu; readiness decision có version; tách observation,
engineering verification và benchmark evaluation; escalation non-terminal với
ownership tách runtime/Autonomy/Model Router/Policy; SkillFabric là registry có
quản trị duy nhất; single-user authority tới BETA.

### E0 — Benchmark kỹ thuật và cắt bỏ tính năng

**Mục tiêu:** định nghĩa "giỏi hơn về code, hệ thống và kiến trúc" trước khi đổi
bề mặt sản phẩm.

**Công việc:**

- tạo case có version cho hiểu repository, khoanh vùng lỗi, thay đổi xuyên
  module, refactor, thiết kế kiến trúc và phục hồi task bị ngắt;
- đóng băng phân biệt operation observation, engineering verification và
  benchmark/gate evaluation, gồm field tối thiểu của
  `VerificationSpec`/`VerificationRecord`;
- định nghĩa điều kiện đủ của successful verified trace độc lập model output;
- chứng minh benchmark runner chấm runtime hiện có từ fixture do người review
  mà không cần capability E1–E3;
- thêm decision case có outcome đã review là `READY`, `REJECTED`,
  `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, cùng case mà chỉ nghiên cứu thêm mới
  là kết quả đúng;
- đo success, vi phạm invariant, recall bằng chứng bắt buộc, kết quả verification,
  độ đúng vấn đề/root cause, độ phủ phương án, readiness, tỷ lệ triển khai không
  an toàn, token model, chi phí và latency của runtime hiện tại;
- map mọi capability được giữ lại vào luồng kỹ thuật trung tâm và ít nhất một
  benchmark case;
- đánh dấu capability không liên quan hoặc trùng lặp là core, chỉ tương thích,
  quarantine hoặc ứng viên loại bỏ trước khi thêm thay thế.

**Nghiệm thu:**

- cả đường deterministic offline và cloud baseline đã chọn đều tái lập bằng
  lệnh và fixture có tên;
- expected evidence và success condition được review, không do chính model đang
  được đánh giá sinh ra;
- decision evidence, phương án, bằng chứng ngược và readiness kỳ vọng được người
  review cho mọi research-gate case;
- success executor/model không thể tự chứng nhận engineering correctness hoặc
  positive verified trace;
- mọi public capability có owner, engineering scenario và disposition;
- không gộp mở rộng provider, swarm, marketplace hoặc integration vào việc đo.

### E1 — Project intelligence local và hiệu quả context

**Mục tiêu:** giảm context cloud lặp lại mà không làm yếu khả năng hiểu dự án.

**Công việc:**

- dẫn xuất repository, dependency, symbol, test và change view có nguồn qua
  ownership Memory, Knowledge và Context Compiler hiện có;
- đưa revision dự án, hành vi hiện tại, constraint, quyết định liên quan và lịch
  sử verification thành input có nguồn cho research decision;
- tạo context manifest gồm identity/hash của source, privacy class, lý do chọn
  và token budget cuối;
- biểu diễn claim status, confidence và freshness mà không nâng model summary
  hoặc nội dung ngoài thành fact;
- ưu tiên xử lý xác định, chỉ dùng summarization, classification hoặc ranking
  local đã đánh giá cho vai trò hẹp có tên;
- giữ lý do inspect được cho mỗi item include, exclude và compress.

**Mục tiêu nghiệm thu ban đầu:**

- recall ít nhất 95% bằng chứng bắt buộc trên benchmark có version;
- giảm ít nhất 30% median cloud input token so với full-context baseline đã
  review sau khi dự án warm-up;
- không giảm verified task success, tính đúng của invariant quan trọng hoặc số
  hành động chưa cấp quyền;
- mọi byte project context gửi remote truy nguyên được về context manifest đã approve;
- decision chỉ ra được bằng chứng dự án ủng hộ hoặc phản bác nó và phát hiện khi
  revision thay đổi làm decision cũ.

### E2 — Research gate có bằng chứng và suy luận local/cloud có chọn lọc

**Mục tiêu:** chọn phương án triển khai tốt nhất có đủ bằng chứng trước khi đổi
production; chỉ dùng độ sâu cloud khi quyết định cần và PAW vẫn giữ quyền điều khiển.

**Công việc:**

- phân loại goal thành `FAST`, `STANDARD` hoặc `DEEP` theo độ mới, tác động, bất
  định, khả năng đảo ngược và constraint bên ngoài;
- mở rộng Plan hiện có bằng `PlanPurpose`; yêu cầu `Task.id` hiện hữu, giữ Plan
  identity riêng và project revision;
- tạo một decision artifact có nguồn và outcome `ImplementationReadiness` có
  kiểu mà không thêm planner hay store thứ hai;
- làm version decision final bất biến với state
  `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED` và invalidation constraint/revision;
- bắt đầu bằng reconnaissance dự án local, rồi so sánh phương án, giả định và
  bằng chứng ngược; `STANDARD`/`DEEP` có ít nhất phương án khả thi nhỏ nhất và
  không làm/hoãn;
- định nghĩa cognitive role đã đánh giá và eligibility local/cloud tường minh;
- route theo độ mới, bất định, tác động, privacy, budget và context sufficiency
  sau reconnaissance mà không tạo router thứ hai;
- hiển thị escalation và fallback trong ledger cùng kết quả cho người dùng;
- bắt buộc reasoning trả evidence, uncertainty và proposed action có kiểu, vẫn
  phải qua Policy và verification;
- chặn Plan nhằm triển khai và mọi proposal gây thay đổi cho tới khi đúng
  task/revision có quyết định `READY` bền vững;
- để `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `REJECTED` và `SPIKE_REQUIRED`
  dừng, hỏi hoặc chỉ lên lịch đúng phần việc có giới hạn tương ứng;
- giữ spike cô lập, có thể bỏ, rồi trả evidence về cùng readiness gate thay vì
  âm thầm promote code spike;
- chạy engineering verification đã khai báo qua operation có gate và derive
  `VerificationRecord` bền vững từ observation chính xác;
- làm protocol escalation assessment có kiểu → threshold runtime → Model Router
  chọn cached → proposal chính xác → Policy verdict → budget Autonomy → invoke provider.

**Nghiệm thu:**

- verified engineering success không thấp hơn cloud-only baseline đã review
  trên benchmark tác động cao;
- 100% mutating implementation proposal tham chiếu artifact `READY` còn hiệu
  lực; negative control chứng minh mọi readiness value khác không thể chạy;
- mọi decision `STANDARD`/`DEEP` so sánh ít nhất hai phương án khả thi, ghi bằng
  chứng ngược quan trọng và có budget dừng nghiên cứu tường minh;
- mọi Plan tham chiếu Task hiện hữu; chỉ `IMPLEMENTATION` có decision `READY`
  hiện hành khớp mới tới mutation dự án;
- riêng `ExecutionObservation.success` không thể thỏa verification hoặc trace eligibility;
- `ESCALATE` hoặc lên lịch inference mạnh hơn có gate theo cách non-terminal,
  hoặc dừng với typed reason khi không có route đủ điều kiện;
- 100% model call local/remote có proposal đã gate, context manifest, role đã
  chọn, usage quan sát được và lý do routing;
- local result low-confidence hoặc ngoài distribution phải escalation hoặc
  dừng tường minh, không âm thầm chạy;
- output local lẫn cloud không đi vòng canonical execution loop.

### E3 — Tích lũy personal skill có quản trị

**Mục tiêu:** biến công việc kỹ thuật lặp lại đã kiểm chứng thành quy trình cá
nhân tái sử dụng được, không biến hoạt động thô hoặc model output thành authority.

**Điều kiện vào:**

- E0–E2 pass và verified trace cho thấy ít nhất một workflow lặp lại;
- Skill Fabric vẫn là owner duy nhất của lifecycle và selection skill;
- fact trong memory, preference người dùng và procedural skill có record cùng
  quy tắc sửa riêng.

**Công việc:**

- chỉ tạo candidate từ yêu cầu tường minh hoặc verified trace;
- giữ chuỗi nghiên cứu → quyết định → triển khai → kiểm chứng trong mọi trace
  dùng để tạo candidate;
- mở rộng lifecycle `SkillFabric` hiện có; không thêm registry thứ hai hoặc coi
  `enabled` là activation đã review;
- ghi trigger, trường hợp không áp dụng, input, allowed tool, policy class,
  procedure, evidence bắt buộc, success/failure check, provenance và version;
- deduplicate candidate với skill active và rejected;
- replay candidate trên benchmark case đã review trước khi kích hoạt;
- yêu cầu chấp nhận tường minh khi promote và giữ version trước để rollback;
- đo selection precision, verified outcome và maintenance cost, rồi deprecate
  skill bị drift hoặc overlap.

**Nghiệm thu:**

- hội thoại thô, lần thử lỗi hoặc model output chưa review không thể thành
  active skill;
- mọi personal skill active có evidence replay đã review, source và version;
- activation, rejection, deprecation và rollback bền vững, inspect được;
- selection skill cải thiện ít nhất một case E0 có tên mà không giảm an toàn
  hoặc required-evidence recall; negative case chứng minh skill không trigger
  ngoài scope.

### BETA — Kiểm chứng engineering partner hằng ngày

**Mục tiêu:** chứng minh một clean install hỗ trợ profile analyze, ideate,
change và review qua cùng runtime, evidence và readiness contract.

**Công việc:**

- định nghĩa profile bằng configuration, không tạo runtime riêng;
- giữ analyze/ideate read-only, change có gate tường minh và review mặc định
  không gây thay đổi;
- thử research depth, decision evidence, readiness, routing, approval, restart,
  verification và inspection trên bốn profile;
- build/chạy beta wheel ngoài repository và ghi giới hạn.
- kiểm chứng boundary single-user/local-authority đã ghi và không claim tenant isolation.

**Nghiệm thu:**

- cả bốn profile dùng runtime canonical và hiển thị evidence, uncertainty,
  readiness cùng next action;
- effect đã hoàn tất không lặp sau restart và mọi remote payload qua privacy review;
- demo từ wheel đã cài pass và beta decision ghi known limit;
- không cần E4 training để pass gate này.

### E4 — Thích nghi model local có kiểm soát

**Mục tiêu:** chỉ train khi lịch sử đã kiểm chứng cho thấy một vai trò local
hẹp, ổn định và có giá trị.

**Điều kiện vào:**

- E0–E3 pass và có đủ trace thành công đã review;
- semantics sửa, lưu giữ và xóa memory đã vận hành;
- cùng role có baseline local chưa train và cloud teacher baseline.

**Công việc và nghiệm thu:**

- chỉ tạo dataset có consent, đã redact, có version từ example đã kiểm chứng;
- ghi base model, lineage dataset, cấu hình training, evaluation và artifact rollback;
- chỉ nhận artifact đã train nếu vượt baseline local chưa train cho role có tên
  mà không hạ chất lượng end-to-end hoặc an toàn;
- giữ cloud escalation và từ chối continuous online self-training từ hoạt động thô.

Các con số trên là product gate ban đầu. Chỉ được đổi qua benchmark review có
tài liệu, không được hạ để biến implementation kém thành hoàn tất.

## Ba task an toàn tiếp theo

1. Làm SX-01/SX-02: ghi và phân loại combined working tree, không đổi user work
   không liên quan.
2. Trong SX-03/SX-10, tái hiện và sửa mismatch Task/Plan identity bằng proof
   persistence/caller tập trung, rồi hoàn tất review compatibility/migration.
3. Đóng băng một clean candidate và chạy SX-12–SX-14. Chỉ exit decision pass mới
   bắt đầu E0; E1–E4/BETA và mở rộng provider vẫn bị chặn trong lúc đó.
