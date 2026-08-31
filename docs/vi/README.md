# Tài liệu hệ thống PAW — tiếng Việt

Đây là bộ tài liệu tiếng Việt tương ứng với bộ tài liệu hệ thống PAW hiện tại.
Mỗi tài liệu trong thư mục này bám theo tài liệu tiếng Anh cùng tên ở thư mục
`docs/`. Tài liệu tiếng Anh là bản canonical về cấu trúc; mã nguồn và test hiện
tại vẫn là bằng chứng cuối cùng cho hành vi thực tế.

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
6. [Tham chiếu API](api.md) và [ví dụ](examples.md) — cách dùng thực tế của
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

| Trạng thái | Ý nghĩa |
|---|---|
| `OBSERVED` | Có trong mã nguồn qua kiểm tra; chưa chắc đã được chạy. |
| `VERIFIED` | Một lệnh hoặc test có tên đã chạy thành công trên revision hiện tại. |
| `PARTIAL` | Có một phần hợp đồng, nhưng còn đường chạy thiếu hoặc không nhất quán. |
| `FAIL` | Hành vi mâu thuẫn với bất biến an toàn hoặc durability. |
| `BLOCKED` | Không thể kiểm chứng vì thiếu điều kiện tiên quyết. |

## Cập nhật tài liệu

Khi thay đổi hệ thống, cập nhật tài liệu tiếng Anh canonical và bản tiếng Việt
tương ứng trong cùng pull request/chặng thay đổi:

- thay đổi hợp đồng hoặc hướng phụ thuộc: `ARCHITECTURE.md`;
- thay đổi owner, public class hoặc known gap: `IMPLEMENTATION_MAP.md`;
- thay đổi ưu tiên hoặc acceptance gate: `ROADMAP.md`;
- thay đổi phạm vi sản phẩm: `PRODUCT_CHARTER.md` và ghi lại quyết định;
- thay đổi quy trình phát triển: `ENGINEERING_RULES.md` và khi cần `AGENTS.md`;
- thay đổi cách gọi: `api.md` và `examples.md`.

Không tạo thêm overview, roadmap hoặc architecture document song song.
