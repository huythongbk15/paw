# Tài liệu hệ thống PAW — tiếng Việt

Audit hiện tại (2026-09-08, `ba1a583` cộng working tree): **PARTIAL**. Phép đo
E1 trên chính source PAW đã đạt ngưỡng metric, nhưng evidence mới ở trạng thái
`OBSERVED`: cây còn dirty, một fixture đã khác revision được review và gate D3
trên revision sạch chưa chạy. E2 vẫn bị chặn. Xem quyết định và execution record
trong `IMPLEMENTATION_MAP.md`.

Đây là bộ tài liệu tiếng Việt tương ứng với bộ tài liệu hệ thống PAW hiện tại.
Mỗi tài liệu trong thư mục này bám theo tài liệu tiếng Anh cùng tên ở thư mục
`docs/`. Tài liệu tiếng Anh là bản canonical về cấu trúc; mã nguồn và test hiện
tại vẫn là bằng chứng cuối cùng cho hành vi thực tế.

Hướng sau ổn định hóa đã ghi nhận chuyên PAW vào code, hệ thống và kiến trúc
phần mềm: control/context/memory ở local hỗ trợ suy luận cloud được gate có chọn
lọc, và nghiên cứu có nguồn, có giới hạn phải tạo readiness decision trước kế
hoạch triển khai. Đây là đích đã ghi trong tài liệu, chưa phải trạng thái đã
triển khai; Core Stabilization vẫn là track duy nhất đang hoạt động.

Kết quả hiện tại: Core Stabilization và baseline E0 đã `VERIFIED`; E1 là
`PARTIAL`; E2/E3/BETA và E4 tùy chọn vẫn `BLOCKED` theo thứ tự gate. Sáu case
PAW-source hiện có recall cold/warm 1,00 và median giảm context warm 0,981.
Freshness kiểm Git blob của fixture, hash input, revision và tree state; kết quả
dirty không được tự chứng nhận `PASS`.

Baseline audit gồm freeze `f3ad4ef`, HEAD `ba1a583` và working tree kiểm tra
ngày 2026-09-08. Setup tái lập dùng lock riêng của PAW:

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
