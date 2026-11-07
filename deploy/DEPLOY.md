# Triển khai CRM lên VPS (GDATA) — dùng trên web và cài lên iPhone

Một VPS Linux chạy toàn bộ: giao diện + backend + HTTPS tự động + sao lưu hằng ngày. Dữ liệu nằm trên VPS tại Việt Nam, không cần Netlify/Supabase.

```
Trình duyệt / iPhone ──HTTPS──► Caddy (cổng 80/443) ──► /api/*  → Backend FastAPI (SQLite trong /data)
                                                    └─► còn lại → giao diện tĩnh
```

## 0. Chuẩn bị (làm một lần)

| Việc | Chi tiết |
|---|---|
| **VPS** | Ubuntu 22.04 hoặc 24.04, tối thiểu 2 vCPU / 2 GB RAM (khuyến nghị 4 GB nếu hay import PDF scan), ổ ≥ 20 GB, có IP công khai. Đặt ở trang quản lý của GDATA. |
| **Tên miền** | Ví dụ `crm.tenmiencuaban.vn`. Ở nơi quản lý tên miền, tạo bản ghi **A** trỏ về IP của VPS. Chờ vài phút. *Bắt buộc có HTTPS thì iPhone mới cài được app lên màn hình chính.* |
| **Tường lửa** | Mở cổng **22** (SSH), **80** và **443**. **Không** mở 8000. |

## 1. Cài Docker (một lần)

```bash
ssh root@IP_CUA_VPS
curl -fsSL https://get.docker.com | sh
docker compose version      # phải in ra số phiên bản
```

## 2. Đưa mã nguồn lên VPS

Dùng file `crm-deploy.zip` đã gửi kèm. Cách dễ nhất trên Windows: mở **WinSCP** (hoặc FileZilla), kết nối SFTP tới VPS, kéo `crm-deploy.zip` vào thư mục `/opt`. Sau đó:

```bash
apt-get install -y unzip
mkdir -p /opt/crm && cd /opt/crm && unzip -o ../crm-deploy.zip
cd /opt/crm/deploy
```

## 3. Cấu hình

```bash
cp .env.example .env
nano .env
```

Điền tối thiểu:

- `DOMAIN=crm.tenmiencuaban.vn`
- `CRM_SETUP_CODE=` một chuỗi dài khó đoán, tạo bằng `openssl rand -hex 16`. Ai mở trang lần đầu cũng phải nhập mã này mới tạo được Admin, nên người lạ không thể vào trước bạn.
- `GEMINI_API_KEY=` nếu dùng trợ lý AI (dùng **khóa mới**, khóa đã dán trong chat nên đổi). Không dùng AI đám mây thì để trống.
- Giữ `CRM_SEED_DEMO=0` để không nạp khách hàng mô phỏng.

Lưu: `Ctrl+O`, Enter, `Ctrl+X`.

## 4. Chạy

```bash
docker compose up -d --build     # lần đầu khoảng 5–10 phút
docker compose ps                # cả hai dịch vụ ở trạng thái running/healthy
```

Mở `https://crm.tenmiencuaban.vn` → màn hình **Thiết lập lần đầu** → nhập **Mã thiết lập** → tạo tài khoản Admin của bạn. Sau đó vào **Quản trị → Người dùng** để tạo tài khoản cho cán bộ nhân viên.

> Chưa có tên miền? Đặt `DOMAIN=:80` rồi vào `http://IP_VPS` để chạy thử. Chế độ này không có HTTPS, nên chỉ nên thử nội bộ và không cài được lên iPhone.

## 5. Chuyển dữ liệu đang có trên máy Windows (tuỳ chọn)

Tắt CRM trên máy Windows. Upload file `E:\CRAFTBYTE\CRM\backend\banking_crm.db` lên VPS vào `/tmp/`, rồi:

```bash
cd /opt/crm/deploy
docker compose stop api
docker cp /tmp/banking_crm.db crm-api:/data/banking_crm.db
docker compose start api
```

Toàn bộ khách hàng, tài khoản Admin/nhân viên và nhật ký sẽ đi theo. Khi đó bạn đăng nhập bằng tài khoản cũ, không cần thiết lập lần đầu.

## 6. Cài lên iPhone / Android

- **iPhone:** mở bằng **Safari** (không dùng Chrome) → nút Chia sẻ → **Thêm vào Màn hình chính**. Icon "CRM" xuất hiện và mở toàn màn hình như app.
- **Android:** Chrome → menu ⋮ → **Cài đặt ứng dụng**.
- Trên điện thoại có nút ☰ ở góc trái trên cùng để mở menu.

## 7. Sao lưu (quan trọng)

1. **Tự động:** mỗi ngày backend tự sao lưu và giữ 14 bản gần nhất (trong `/data/backups` của VPS).
2. **Tải về máy:** Admin vào **Doanh nghiệp → Cài đặt → Sao lưu dữ liệu → Tải bản sao lưu về máy**. Hãy tải định kỳ (ví dụ mỗi tuần) và cất ở ổ ngoài hoặc nơi khác. Sao lưu nằm cùng VPS thì mất VPS là mất cả hai.
3. **Nên bật thêm** dịch vụ snapshot/backup VPS của GDATA.

Khôi phục từ một bản sao lưu:

```bash
docker compose stop api
docker cp banking_crm-20261107-020000.db crm-api:/data/banking_crm.db
docker compose start api
```

## 8. Cập nhật phiên bản mới

Upload zip mới, giải nén đè vào `/opt/crm` (file `deploy/.env` và dữ liệu không bị đụng tới), rồi:

```bash
cd /opt/crm/deploy && docker compose up -d --build
```

## 9. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| Không vào được `https://…` | Kiểm tra bản ghi A đã đúng IP; cổng 80 và 443 đã mở; `docker compose logs web` |
| Trang báo 502 | Backend chưa lên: `docker compose logs api` |
| Quên mật khẩu Admin duy nhất | `docker compose exec -it api python data/reset_admin_password.py tên_đăng_nhập` |
| Tài khoản bị khóa vì nhập sai nhiều lần | Chờ 5 phút, hoặc `docker compose restart api` |
| Xem log theo thời gian thực | `docker compose logs -f api` |
| Dừng / chạy lại | `docker compose stop` / `docker compose start` |

## 10. Bảo mật — nhắc nhanh

- Đổi khóa Gemini cũ, dùng khóa mới trong `.env`.
- Chỉ dùng tài khoản riêng cho từng người; khóa tài khoản khi nhân viên nghỉ việc (Quản trị → Người dùng).
- Xem **Nhật ký thao tác** để biết ai đã làm gì (đăng nhập, import, sửa, xóa, tải sao lưu).
- OCR đám mây (gửi nội dung file lên Google) mặc định **tắt**; chỉ bật nếu chính sách của bạn cho phép.
- Chỉ nhập thông tin kinh doanh của khách hàng mới; không nhập dữ liệu nhạy cảm của ngân hàng.
- Nên dùng SSH key và tắt đăng nhập SSH bằng mật khẩu trên VPS.
