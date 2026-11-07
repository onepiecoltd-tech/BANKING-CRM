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

- **`deploy/`**: Docker (backend + giao diện tĩnh + Caddy HTTPS tự động) cho 1 VPS (GDATA). Hướng dẫn từng bước: `deploy/DEPLOY.md`.
- **PWA**: `frontend/public/manifest.webmanifest` + icon → iPhone "Thêm vào Màn hình chính". Giao diện có nút ☰ menu trên điện thoại.
- **Sao lưu**: tự động mỗi ngày (`CRM_BACKUP_DIR`, giữ `CRM_BACKUP_KEEP_DAYS` ngày) + Admin tải bản sao lưu ở Cài đặt (`GET /api/corp/admin/backup`).
- **Quên mật khẩu Admin**: `python data/reset_admin_password.py <tên_đăng_nhập>` (chạy trên máy chủ).
- Build giao diện tĩnh: `STATIC_SPA=1 npm run build` → `frontend/dist/client` (có `_shell.html`).
- Kiểm thử: `python tests/test_corp_full.py` → 91/91 đạt. Chưa chạy thử Docker/Caddy trong môi trường build; đã chạy thử bản build tĩnh + backend thật ở khung iPhone (390px) và máy tính bảng.
