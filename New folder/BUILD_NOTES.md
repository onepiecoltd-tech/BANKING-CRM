# Bản build thử (2026-11-07)

Đã build/kiểm tra: frontend `npm run build` OK (có sẵn `frontend/dist`), backend chạy với Python 3.11, DB đã seed sẵn (`backend/banking_crm.db`, 500 khách hàng).

## Chạy backend (Python 3.11 hoặc 3.12, KHÔNG dùng 3.13)
```
cd backend
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # điền GEMINI_API_KEY, đặt LLM_BACKEND=gemini
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```
Nếu cần seed lại DB: `python data/seed_db.py` (README gốc ghi sai lệnh).

## Chạy frontend
```
cd frontend
npm ci
npm run dev        # hoặc npm run build
```

## Đã sửa so với repo gốc
- requirements.txt: thay `google-generativeai==0.3.0` bằng `google-genai` (gemini.py dùng SDK mới).
- README: lệnh seed DB và yêu cầu phiên bản Python.

## Chưa kiểm chứng
- Gọi Gemini thật (sandbox chặn host Google) — cần test trên máy bạn.
- Gửi WhatsApp thật (Twilio / wwebjs).
- Xác suất chuyển đổi các khách top đều ~2%, nên xem lại công thức/dữ liệu seed.

---

# Cập nhật: Doanh nghiệp đầy đủ + phân quyền + import (2026-11-07)

## Mới
- **Bản Doanh nghiệp đủ trang như Cá nhân**: Tổng quan, Khách hàng, Pipeline, Trợ lý AI cho RM, Trung tâm tiếp cận, Chiến dịch, Hội thoại, Lập luận & truy vết, Phân tích số liệu, Import dữ liệu, Quản trị & Cài đặt.
- **Đăng nhập & phân quyền**: lần đầu mở sẽ hiện màn hình tạo tài khoản **Admin** (không có mật khẩu mặc định). Admin tạo nhân viên ở *Người dùng & phân quyền*.
  - Admin (quản lý): xem tất cả, sửa/xóa/chuyển cán bộ phụ trách, duyệt import, cài đặt, nhật ký thao tác, xóa dữ liệu mẫu.
  - Nhân viên (CBQH): chỉ thấy khách hàng có "Cán bộ phụ trách" trùng *Tên CBQH* của tài khoản; thêm/sửa hồ sơ, tiếp cận, ghi hội thoại, import (chờ Admin duyệt — bật/tắt trong Cài đặt).
  - Mật khẩu ≥ 8 ký tự có chữ và số; khóa 5 phút sau 5 lần sai; phiên 12 giờ; tài khoản do Admin tạo/đặt lại phải đổi mật khẩu lần đầu đăng nhập.
- **Import dữ liệu**: Excel (.xlsx), CSV, PDF có chữ, PDF scan/ảnh (OCR). Tự nhận cột (tiếng Việt/Anh/Trung), tự quy đổi đơn vị (triệu/đồng/USD), xem trước → xác nhận; trùng MST/mã KH/tên → cập nhật. Có file Excel mẫu (nút "Tải file Excel mẫu").
  - OCR trên máy cần **Tesseract** (Windows: bản UB-Mannheim, chọn thêm ngôn ngữ Vietnamese + Chinese Simplified). Hoặc Admin bật "OCR đám mây" trong Cài đặt (gửi nội dung file lên Google Gemini, cần `GEMINI_API_KEY` trong `backend\.env`). Mặc định tắt.
- Dữ liệu mẫu (CORPxxxx) kèm 2 chiến dịch/hội thoại mô phỏng; xóa bằng *Cài đặt → Xóa dữ liệu mẫu* trước khi dùng dữ liệu thật.

## Lần chạy đầu sau khi cập nhật
Mở `CRM.exe` — launcher thấy `requirements.txt` đổi (thêm `openpyxl`, `pymupdf`) nên tự cài lại thư viện backend (vài phút). Không cần `npm ci` lại. `banking_crm.db` và `.env` của bạn được giữ nguyên; bảng mới tự tạo khi backend khởi động.

## Kiểm tra đã làm
- `backend/tests/test_corp_full.py`: 84 kiểm tra (đăng nhập, phân quyền, phạm vi dữ liệu, CRUD, import Excel/CSV/PDF/OCR, duyệt import, tiếp cận + loại trừ, chiến dịch, hội thoại, lập luận, phân tích, cài đặt). Chạy: `cd backend && .venv\Scripts\python tests\test_corp_full.py`.
- Frontend: `tsc --noEmit` sạch, `npm run build` OK, đã mở từng trang bằng trình duyệt thật (Admin và nhân viên).

## Chưa kiểm chứng được trong sandbox
- OCR đám mây Gemini và AI viết lại câu trả lời (sandbox chặn Google).
- Chạy `CRM.exe` trên Windows (đã biên dịch chéo, chưa chạy).
- Gửi Zalo/Email thật: hệ thống soạn tin và ghi nhận; cán bộ sao chép gửi tay.
- Bảo mật: Cá nhân (retail) chưa phân quyền theo từng nhân viên (mọi người dùng đăng nhập đều thấy). Đổi khóa Gemini nếu đã dán ở nơi công khai.

## Cập nhật: gói triển khai VPS + iPhone (2026-11-07)

- **`docker-compose.yml`** (thư mục gốc, MỘT file duy nhất): giao diện tĩnh + Caddy (một cổng duy nhất 1111, HTTP) + backend (chỉ trong mạng Docker) + CSDL SQLite (volume) cho 1 VPS (GDATA). Dockerfile và Caddyfile nhúng ngay trong file; khóa Gemini nằm trong `.env` cạnh file. Hướng dẫn từng bước: `DEPLOY.md`.
- **PWA**: `frontend/public/manifest.webmanifest` + icon → iPhone "Thêm vào Màn hình chính". Giao diện có nút ☰ menu trên điện thoại.
- **Sao lưu**: tự động mỗi ngày (`CRM_BACKUP_DIR`, giữ `CRM_BACKUP_KEEP_DAYS` ngày) + Admin tải bản sao lưu ở Cài đặt (`GET /api/corp/admin/backup`).
- **Quên mật khẩu Admin**: `python data/reset_admin_password.py <tên_đăng_nhập>` (chạy trên máy chủ).
- Build giao diện tĩnh: `STATIC_SPA=1 npm run build` → `frontend/dist/client` (có `_shell.html`).
- Kiểm thử: `python tests/test_corp_full.py` → 115/115 đạt. Chưa chạy thử Docker/Caddy trong môi trường build; đã chạy thử bản build tĩnh + backend thật ở khung iPhone (390px) và máy tính bảng.

## Cập nhật: phân công khách hàng ↔ CBBH (2026-11-09)

- **Trang mới** `Quản trị hệ thống → Phân công KH ↔ CBBH` (`/admin/assign`, chỉ Admin): khối lượng từng CBBH (tổng / KH mới / hiện hữu), mục "Cần xử lý" (khách chưa phân công, hoặc gán cho tên chưa có tài khoản nên không ai ngoài Admin thấy), nút "Chuyển toàn bộ…", và công cụ "Gán theo điều kiện" (vd. toàn bộ KH mới ở Bình Dương → một CBBH) có xem trước số lượng.
- **Danh sách khách hàng** (Admin): thêm lọc "Loại KH", "CBBH phụ trách", cột CBBH, ô tick chọn nhiều + "Chọn cả N khách hàng khớp bộ lọc" + nút "Gán cho CBBH…".
- Hồ sơ khách hàng: nút chuyển CBBH giờ chọn từ danh sách tài khoản (trước đây gõ tay, dễ sai tên).
- Quy tắc: chỉ gán được cho tài khoản **đang hoạt động** (khớp `Tên CBQH` của tài khoản); có hiệu lực ngay, CBBH cũ không còn thấy; ghi nhật ký `customer.assign`.
- API: `GET /api/corp/admin/assignment`, `POST /api/corp/admin/assign` (`customer_ids` hoặc `filters`, `dry_run` để xem trước). `customers/reassign` cũng kiểm tra CBBH hợp lệ.

## Cập nhật: dọn dữ liệu mô phỏng & rác (2026-11-09)

- **Thẻ mới** `Doanh nghiệp → Quản trị & Cài đặt → Dọn dữ liệu mô phỏng & rác` (chỉ Admin) thay thẻ "Xóa dữ liệu mẫu". Ba nhóm chọn độc lập, có xem trước số dòng:
  1. *Khách hàng cá nhân mô phỏng* — toàn bộ `customers` + giao dịch, tương tác, định danh, đồng ý, danh sách chặn, phiên, lịch chăm sóc, nhật ký gửi (giữ bảng danh mục `products`).
  2. *KH DN mẫu (CORPxxxx) & ghi chú mô phỏng* — khách hàng mẫu + dòng tiền, cơ hội, ghi chú tương tác, hội thoại, chiến dịch mẫu (kể cả chiến dịch chỉ nhắm KH mẫu). KH thật (mã khác CORPxxxx) không bị đụng.
  3. *Dữ liệu rác* — dòng mồ côi (khách hàng đã xóa), ghi chú trống, nhật ký chạy AI bị lỗi (`llm_error`), chiến dịch rỗng.
- Quy trình an toàn: gõ `XOA` → **tự sao lưu SQLite** (lỗi sao lưu thì dừng, chưa xóa gì) → xóa trong một giao dịch → đặt cờ `_demo_cleared` (lần khởi động sau không nạp lại KH DN mẫu) → `VACUUM` thu nhỏ file → ghi nhật ký `data.cleanup`.
- API: `GET/POST /api/corp/admin/cleanup`; dòng lệnh: `python -m src.corporate.cleanup [--retail] [--corp-demo] [--junk] [--yes]` (không `--yes` = chỉ xem trước).
- Giao diện mục **Cá nhân** bỏ số liệu giả cứng: Dashboard (không còn dữ liệu dự phòng `mockData`, "+4,2%", gợi ý AI/hoạt động giả), Trung tâm tiếp cận (chiến dịch "Mumbai HNI…"), Lập luận & truy vết (trace #47281, số liệu giả), Audit Log trong Cài đặt (nay đọc nhật ký thật). Đã xóa `lib/mockData.ts`, `lib/agentSim.ts`. Nhãn "(Dữ liệu mô phỏng)" ở Tổng quan DN đã bỏ.
- Thử trên bản sao DB thật của anh (snapshot 2026-11-07): xóa 13.495 dòng cá nhân + 3.420 dòng DN mẫu + 2 log AI lỗi; 934 KH thật giữ nguyên; file 10,4 → 3,9 MB; `integrity_check` ok.
- Kiểm thử: `tests/test_corp_full.py` 142/142 đạt (thêm 27 kiểm tra: phân quyền, xác nhận, rác gieo sẵn, sao lưu còn đủ để khôi phục, API cá nhân chạy được khi trống, dọn lần 2 vô hại). Duyệt 19 trang bằng trình duyệt thật sau dọn: không lỗi, không còn chữ "Mumbai/Trace #/mô phỏng" ở trang dữ liệu.
