# Lộ trình Core Stabilization của PAW

Đây là work sequence duy nhất đang hoạt động. Các phase được đánh số trong lịch
sử mô tả cách repository phình lên; chúng không quyết định việc phải xây tiếp.

Track hiện tại: **S5/S6 verification — durable CLI chat slice đã có; bằng chứng
regression/package cùng revision và hợp nhất unit loop vẫn còn.**

## Quy tắc trình tự

Hoàn thành track theo thứ tự. Có thể di chuyển trong cùng track, nhưng không bắt
đầu track sau khi item an toàn hoặc durability của track trước còn fail. Nếu đổi
ưu tiên, phải ghi rủi ro và cập nhật roadmap, không âm thầm tạo kế hoạch nhánh.

## S0 — Baseline tái lập được

**Mục tiêu:** mọi status tương lai đều tái lập được từ checkout sạch.

**Việc cần làm:**

- thay `requirements.lock.txt` snapshot host bằng lock chỉ cho PAW, hoặc đổi tên/
  xóa sau khi xác nhận owner;
- ghi một đường setup Python 3.12+ cho runtime và dev dependency;
- chạy full test và lint trên revision hiện tại;
- build wheel, cài môi trường sạch và smoke-test CLI ngoài repository;
- ghi nhận lỗi, không sửa hệ thống không liên quan;
- thêm check tự động để docs canonical không tuyên bố phase chưa kiểm chứng hoặc
  trỏ tới module không tồn tại.

**Nghiệm thu:** setup sạch dùng dependency khai báo bởi project; pytest/ruff có
kết quả hiện tại; wheel/import/CLI smoke đã chạy; không có dependency runtime bị
cấm; `IMPLEMENTATION_MAP.md` ghi evidence.

## S1 — Contract canonical và public ownership

**Mục tiêu:** mỗi khái niệm PAW-owned có một source of truth.

**Việc cần làm:** hợp nhất autonomy/stop/task status; định nghĩa proposal/
executable-task; làm `ContextCompiler` canonical; quy định normalize Evidence /
Citation; tách planner/proposer/scheduler; thu hẹp `paw.core` export; thêm test
phát hiện definition core thứ hai.

**Nghiệm thu:** một definition mỗi type; mọi runtime/policy/checkpoint/test dùng
cùng type; alias tương thích có điều kiện xóa; không giấu thay đổi behavior trong
quá trình hợp nhất.

## S2 — Toàn vẹn storage và migration

**Mục tiêu:** state cục bộ bền vững qua commit, close, restart và upgrade.

**Việc cần làm:** schema version và migration tập trung; bỏ DDL on-demand; bỏ
destructive graph initialization; giới hạn legacy mutation API; định nghĩa atomic
boundary cho task/operation/checkpoint/ledger; test đóng-mở SQLite.

**Nghiệm thu:** init không drop dữ liệu; write acknowledged sống qua restart;
migration tuần tự/idempotent; không có DDL ngoài schema owner; checkpoint và
operation thấy được sau reopen.

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
- docs không còn claim current phase/status mâu thuẫn.

Sau exit gate, đánh giá từng adapter/feature theo phép thử thay đổi sản phẩm.
Không tự động tăng phase.

## Ba task an toàn tiếp theo

1. Chạy full suite/lint, build và cài wheel sạch, smoke-test `paw chat` ngoài repo.
2. Đưa graph node qua cùng executable-unit loop với single task.
3. Chỉ định nghĩa real executor adapter hẹp sau exit gate; demo offline vẫn
   non-destructive và nói rõ là mock.
