# Tài liệu hệ thống PAW — tiếng Việt

## Hiện trạng — nguồn sự thật duy nhất (2026-10-20)

Phần này là **nơi duy nhất** trong bộ tài liệu canonical nêu trạng thái hiện tại.
Tài liệu khác phải trỏ tới đây thay vì nhắc lại một phán quyết; các mục lịch sử
bên dưới là bằng chứng có ngày, không phải trạng thái hiện tại.

Trước đây có **hai thứ khác nhau** cùng được gọi là "E1/E2 VERIFIED". Dưới đây
tách riêng, vì nhập nhằng đó là nguồn mâu thuẫn chính giữa bản tiếng Anh và
tiếng Việt.

**Kết quả ở mức gate** — một gate đo được, trong đúng phạm vi khai báo:

| Gate | Kết quả | Phạm vi và bằng chứng |
|---|---|---|
| Core Stabilization | **`VERIFIED`** trên `f3ad4ef` | S0–S6 qua D3 trên revision sạch; commit freeze là bằng chứng canonical được track. |
| E0 fixture-validation baseline | **`VERIFIED`** cho offline tất định | 13 case (8 minimum + 5 research-decision), runner tất định, integration-pack record. 13/13 SUCCESS là **fixture-validation**, không phải gate chất lượng agent. Tầng agent-quality do runtime dẫn là việc sau gate (E0-40). |
| E1-27 production measurement | **`VERIFIED`** | Revision sạch `8d01d90`; `min_recall=1.00`, 12/12 mẫu (6 case x cold/warm), embedding Ollama thật. **Caveat bằng chứng:** báo cáo đo `benchmarks/e1/e1_production_report.md` bị *gitignore*, nên phán quyết này dựa trên tài liệu ghi nhận chứ không dựa trên artifact được track. Track lại file đó là tiền đề phát hành. |
| E2 prerequisite contract | **`RATIFIED`** trên `8d01d90` | E2-25..28 và E2-45..47 đã triển khai và pass (119 test contract E2). Ranh giới cloud-baseline được giải quyết bằng `InferenceClassification` / `evaluate_local_eligibility`. |

**Kết quả ở mức track (phát hành)** — track có được ship hay không:

| Track | Kết quả | Lý do |
|---|---|---|
| E1 (Local project intelligence) | **`PARTIAL`** | Gate *đo* E1-27 đã verify; *qualification* track E1 thì chưa. Chấp nhận chất lượng, privacy và release của track chưa từng được gắn vào revision qualification. Gate đo đã verify không phải track đã qualify. |
| E2, E3, BETA | **`BLOCKED`** | Hợp đồng ở mức gate đã có, nhưng nghiệm thu phát hành ở mức track phụ thuộc qualification của track E1. Source wiring đi trước điều kiện nghiệm thu là implementation `OBSERVED`, không phải quyền mở rộng. |
| E4 (controlled adaptation) | **`BLOCKED`**, tùy chọn | Cần E0–E3 và dataset đã verify; không bắt buộc cho BETA. |

**Product release: `PARTIAL`.** Rà soát đóng gói có ngày **2026-10-05** (source
`9fb893e` và sửa index của user được giữ nguyên), có cập nhật 2026-10-07.
B-18 shared-unit admission/recovery và CLI hai approval có bằng chứng D3 trên
working tree (2026-10-07, 2262 passed, 3 skipped). Bằng chứng đó là **working tree**, không phải certification clean
revision, và không tuyên bố release clean revision hiện tại. B-19
discovery/payload vẫn còn thiếu. Đọc [rà soát và web](BETA_LIMITATIONS.md)
sau bảy tài liệu core: F01..F12, parity, security, case và acceptance.
[Roadmap](ROADMAP.md) vẫn là authority thứ tự; B-15..B-36 là work packet bổ
sung cho BETA. Web theo yêu cầu user là presentation adapter local, không phải
agent core mới. Training vẫn ngoài phạm vi.

### Lịch sử (bằng chứng có ngày — không phải trạng thái hiện tại)

Rà soát ngày 2026-09-09, HEAD source `fd8a8c8` và thay đổi router chưa
commit có sẵn. Báo cáo tracked `benchmarks/e1/real_measurement_local.json` ghi
**chỉ phép đo** PASS/VERIFIED trên revision sạch `649ded9`: 71 file source,
839.006 byte, recall 1,0, giảm context warm ước tính 0,9847.
Báo cáo tự loại trừ qualification toàn E1. Đây là bằng chứng đo lịch sử,
không phải D3 revision hiện tại, chất lượng engineering hay token provider.
Source E2-06..11 đã tồn tại, gồm wiring routing/reconnaissance trong runtime:
ghi nhận OBSERVED, chưa đồng nghĩa đã đạt điều kiện nghiệm thu.
Giữ code để rà soát, không tự mở rộng. Xem quyết định 2026-09-09 trong
`IMPLEMENTATION_MAP.md`.

Bản Roadmap tiếng Anh và tiếng Việt mô tả **cùng** rà soát 2026-09-09. Trước
đây hai bên nêu phán quyết *ngược nhau* cho cùng một rà soát. Nay cả hai nói
cùng một điều: bằng chứng chỉ phép đo tại các revision nêu trên, qualification
track E1 chưa được thiết lập.

Đây là bộ tài liệu tiếng Việt tương ứng với bộ tài liệu hệ thống PAW hiện tại.
Mỗi tài liệu trong thư mục này bám theo tài liệu tiếng Anh cùng tên ở thư mục
`docs/`. Tài liệu tiếng Anh là bản canonical về cấu trúc; mã nguồn và test hiện
tại vẫn là bằng chứng cuối cùng cho hành vi thực tế.

Hướng sau ổn định hóa đã ghi nhận chuyên PAW vào code, hệ thống và kiến trúc
phần mềm: control/context/memory ở local hỗ trợ suy luận cloud được gate có chọn
lọc, và nghiên cứu có nguồn, có giới hạn phải tạo readiness decision trước kế
hoạch triển khai. Đây là đích đã ghi trong tài liệu, chưa phải trạng thái đã
triển khai; kết quả gate và track hiện tại nằm ở hai bảng phía trên.

Kết quả và số đo hiện tại nằm trong phần hiện trạng đầu tài liệu; không suy ra
trạng thái gate từ checkbox hay lịch sử test. Setup dùng lock riêng của PAW:

```bash
uv lock --check
uv sync --locked --extra dev
```

## Thứ tự đọc

1. [Tuyên ngôn sản phẩm](PRODUCT_CHARTER.md) — PAW giải quyết vấn đề gì,
   PAW sở hữu gì và cố ý chưa làm gì.
2. [Kiến trúc lõi](ARCHITECTURE.md) — hợp đồng runtime, hướng phụ thuộc và
   các bất biến an toàn.
3. [Bản đồ triển khai](IMPLEMENTATION_MAP.md) — mã nguồn hiện tại nằm ở đâu,
   đường chạy nào đã được kiểm chứng và khoảng trống nào còn lại.
4. [Lộ trình ổn định](ROADMAP.md) — thứ tự sửa chữa và cổng nghiệm thu.
5. [Quy tắc kỹ thuật](ENGINEERING_RULES.md) — cách con người và coding agent
   thay đổi hệ thống mà không tạo thêm nhánh triển khai cạnh tranh.
6. [Checklist thực thi](EXECUTION_CHECKLIST.md) — đầu việc nguyên tử và ước
   lượng được dẫn xuất từ Roadmap; file này không được đổi scope, thứ tự hoặc gate.
7. [Tham chiếu API](api.md) và [ví dụ](examples.md) — cách dùng thực tế của
   runtime và CLI chat.
8. [Contract role/task-signal E2](benchmarks/e2/e2_02_implementation_readiness.md)
   — bản dịch của contract pre-gate E2-02..05; chưa phải runtime đã kích hoạt.

## Thứ tự ưu tiên khi tài liệu không khớp

Khi hai nguồn mâu thuẫn, dùng thứ tự sau:

1. Hành vi tái lập được từ test trên revision hiện tại.
2. Mã nguồn hiện tại dưới `src/paw/`.
3. `docs/IMPLEMENTATION_MAP.md` tiếng Anh để giải thích trạng thái hiện tại.
4. `docs/ARCHITECTURE.md` tiếng Anh cho hợp đồng đích.
5. Bộ tài liệu tiếng Việt này để đọc và trao đổi thuận tiện.
6. Ghi chú phase lịch sử, memory workspace và commit message.

Nếu bản dịch lệch mã nguồn, cập nhật bản dịch trong cùng thay đổi. Không dùng
bản dịch để biến một hành vi chưa được kiểm chứng thành `VERIFIED`.

## Từ vựng trạng thái

Status có hai chiều riêng; không dùng chiều này thay chiều kia.

Trạng thái evidence:

| Nhãn | Ý nghĩa |
|---|---|
| `OBSERVED` | Có trong source qua inspection; chưa chắc đã được chạy. |
| `VERIFIED` | Lệnh hoặc test có tên đã pass trên đúng revision/tree được nêu. |

Kết quả gate hoặc handoff:

| Nhãn | Ý nghĩa |
|---|---|
| `PASS` | Mọi acceptance condition của gate/change có tên đã pass bằng evidence hiện hành. |
| `PARTIAL` | Đã có một phần behavior/evidence nhưng còn ít nhất một acceptance item. |
| `FAIL` | Evidence hiện tại mâu thuẫn acceptance condition hoặc invariant an toàn/durability. |
| `BLOCKED` | Công việc hoặc verification không thể tiếp tục vì thiếu prerequisite. |

`DONE` và từ `implemented` đứng một mình không phải status. Feature có thể đã
được quan sát trong dirty working tree trong khi release gate vẫn `PARTIAL`.
Không biến test count cũ, phase label hoặc workspace note thành `VERIFIED`/`PASS`.

## Cập nhật tài liệu

Khi thay đổi hệ thống, cập nhật tài liệu tiếng Anh canonical và bản tiếng Việt
tương ứng trong cùng pull request/chặng thay đổi:

- thay đổi hợp đồng hoặc hướng phụ thuộc: `ARCHITECTURE.md`;
- thay đổi owner, public class hoặc known gap: `IMPLEMENTATION_MAP.md`;
- thay đổi ưu tiên hoặc acceptance gate: `ROADMAP.md`;
- chia nhỏ task hoặc ghi evidence hoàn thành: `EXECUTION_CHECKLIST.md`, sau khi
  cập nhật Roadmap nếu cần;
- thay đổi phạm vi sản phẩm: `PRODUCT_CHARTER.md` và ghi lại quyết định;
- thay đổi quy trình phát triển: `ENGINEERING_RULES.md` và khi cần `AGENTS.md`;
- thay đổi cách gọi: `api.md` và `examples.md`.

Không tạo thêm overview, roadmap hoặc architecture document song song.
