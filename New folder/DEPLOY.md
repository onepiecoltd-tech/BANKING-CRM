# Triển khai CRM lên VPS (GDATA) — chạy trên web và cài lên iPhone

Một VPS Linux chạy toàn bộ bằng **một file `docker-compose.yml`**: giao diện + backend + CSDL + sao lưu hằng ngày. Dữ liệu nằm trên VPS tại Việt Nam, không cần Netlify/Supabase.

```
Trình duyệt / iPhone ──HTTP──► web (Caddy, CỔNG DUY NHẤT 1111) ──► /api/*  → api:8000 (qua mạng Docker crm-net) ──► SQLite (volume crm_data)
                                                              └─► còn lại → giao diện tĩnh
```

- **Chỉ một cổng ra ngoài: 1111.** Không dùng 80/443 hay cổng mặc định nào. Backend không publish cổng, chỉ giao diện gọi được qua mạng nội bộ Docker.
- File `docker-compose.yml` tự build từ mã nguồn, nên phải đặt cạnh hai thư mục `backend/` và `frontend/` (có sẵn trong `crm-deploy.zip`). CSDL là SQLite nằm trong volume Docker `crm_data`, không có container CSDL riêng.
- **Cổng 1111 là HTTP thường (chưa mã hoá).** Đọc mục 6 trước khi cho nhân viên dùng.

## 0. Chuẩn bị (làm một lần)

| Việc | Chi tiết |
|---|---|
| **VPS** | Ubuntu 22.04 hoặc 24.04, tối thiểu 2 vCPU / 2 GB RAM (khuyến nghị 4 GB nếu hay import PDF scan), ổ ≥ 20 GB, có IP công khai. |
| **Địa chỉ truy cập** | `http://103.226.250.21:1111`. Muốn dùng tên miền: tạo bản ghi **A** `crm.craftbyte.asia` trỏ về IP VPS, rồi vào `http://crm.craftbyte.asia:1111`. |
| **Tường lửa (Security Group, Inbound)** | Mở cổng **22** (SSH) và **1111**. Không cần mở 80, 443, 8000. Nên giới hạn nguồn của cổng 1111 (xem mục 6). |

Kiểm tra cổng 1111 chưa bị dịch vụ khác dùng:

```bash
ss -tlnp | grep ':1111 '     # không in ra gì là tốt
```

## 1. Cài Docker (một lần)

```bash
ssh root@IP_CUA_VPS
curl -fsSL https://get.docker.com | sh
docker compose version      # cần phiên bản 2.23 trở lên
```

## 2. Đưa mã nguồn lên VPS

Dùng `crm-deploy.zip`. Trên Windows: mở **WinSCP** (hoặc FileZilla), kết nối SFTP tới VPS, kéo `crm-deploy.zip` vào `/opt`. Sau đó:

```bash
apt-get install -y unzip
mkdir -p /opt/crm && cd /opt/crm && unzip -o ../crm-deploy.zip
ls -a     # phải thấy: docker-compose.yml  .env  backend  frontend
```

## 3. Cấu hình

```bash
cd /opt/crm
nano .env
```

Dán khóa Gemini **mới** vào dòng `GEMINI_API_KEY=` (không dấu nháy, không khoảng trắng). Lưu: `Ctrl+O`, Enter, `Ctrl+X`.

- Container `api` đọc khóa trực tiếp từ file `.env` này. Khóa cũ đã dán trong chat nên đổi. Không dùng AI đám mây thì để trống và đặt `LLM_BACKEND=ollama`.
- **Mã thiết lập** (`CRM_SETUP_CODE`) đã đặt sẵn trong `docker-compose.yml`. Ai mở trang lần đầu cũng phải nhập mã này mới tạo được Admin. Muốn đổi, sửa dòng `CRM_SETUP_CODE` trong file đó (đừng dùng lại `DOI-MA-NAY`, backend sẽ từ chối chạy).
- Không đưa file `.env` lên GitHub hay gửi qua chat.

## 4. Chạy

```bash
docker compose up -d --build     # lần đầu khoảng 5–10 phút
docker compose ps                # api: healthy, web: running
```

Mở `http://103.226.250.21:1111` → **Thiết lập lần đầu** → nhập **Mã thiết lập** → tạo tài khoản Admin. **Làm ngay sau khi chạy**: khi đã có Admin, màn hình thiết lập đóng lại và mã không còn tác dụng. Sau đó vào **Quản trị → Người dùng** tạo tài khoản cho nhân viên.

## 5. Chuyển dữ liệu đang có trên máy Windows (tuỳ chọn)

Tắt CRM trên máy Windows. Upload `E:\CRAFTBYTE\CRM\backend\banking_crm.db` lên VPS vào `/tmp/`, rồi:

```bash
cd /opt/crm
docker compose stop api
docker cp /tmp/banking_crm.db crm-api:/data/banking_crm.db
docker compose start api
```

Toàn bộ khách hàng, tài khoản Admin/nhân viên và nhật ký đi theo; đăng nhập bằng tài khoản cũ, không cần thiết lập lần đầu.

**Dọn dữ liệu mô phỏng còn trong file DB cũ:** đăng nhập Admin → tab *Doanh nghiệp* → *Quản trị & Cài đặt* → thẻ *Dọn dữ liệu mô phỏng & rác* (xem số dòng, chọn nhóm, gõ `XOA`; hệ thống tự sao lưu trước). Hoặc bằng dòng lệnh trên VPS:

```bash
docker compose exec api python -m src.corporate.cleanup                                  # chỉ xem trước
docker compose exec api python -m src.corporate.cleanup --retail --corp-demo --junk --yes   # xóa (tự sao lưu trước)
```

## 6. HTTPS và giới hạn truy cập (quan trọng)

Qua cổng 1111, **mật khẩu và dữ liệu khách hàng đi dạng chưa mã hoá**. Cổng riêng như 1111 cũng không tự xin được chứng chỉ HTTPS (Let's Encrypt cần cổng 80/443). Nên làm một hoặc cả hai:

1. **Giới hạn nguồn truy cập** (nên làm luôn): trong Security Group, rule Inbound TCP **1111** chỉ cho IP văn phòng hoặc VPN của bạn, không để `0.0.0.0/0`.
2. **Đặt HTTPS phía trước** (cần nếu dùng từ điện thoại ngoài văn phòng, và để cài lên iPhone đáng tin cậy):
   - **Cloudflare Tunnel** (`cloudflared`): không cần mở cổng nào, trỏ `crm.craftbyte.asia` về `http://localhost:1111`.
   - Hoặc nếu máy chủ đã có web server chạy HTTPS ở cổng 443: thêm một site proxy `crm.craftbyte.asia` → `http://127.0.0.1:1111`, rồi đổi dòng `"1111:1111"` trong compose thành `"127.0.0.1:1111:1111"` để cổng 1111 không còn mở ra ngoài.
   - Lưu ý: khi đi qua proxy phía trước, bộ đếm khoá đăng nhập sai (5 lần/5 phút) có thể tính theo IP của proxy, tức mọi người dùng chung một bộ đếm.

## 7. Cài lên iPhone / Android

- **iPhone:** mở bằng **Safari** (không dùng Chrome) → nút Chia sẻ → **Thêm vào Màn hình chính**. Nên làm sau khi đã có HTTPS (mục 6).
- **Android:** Chrome → menu ⋮ → **Cài đặt ứng dụng**.
- Trên điện thoại có nút ☰ góc trái trên cùng để mở menu.

## 8. Sao lưu (quan trọng)

1. **Tự động:** mỗi ngày backend sao lưu và giữ 14 bản gần nhất (trong volume `crm_data`, thư mục `/data/backups`).
2. **Tải về máy:** Admin vào **Doanh nghiệp → Cài đặt → Sao lưu dữ liệu → Tải bản sao lưu về máy**. Nên tải mỗi tuần và cất ở nơi khác; sao lưu nằm cùng VPS thì mất VPS là mất cả hai.
3. **Nên bật thêm** snapshot/backup VPS của GDATA.

Khôi phục từ một bản sao lưu:

```bash
cd /opt/crm
docker compose stop api
docker cp banking_crm-20261107-020000.db crm-api:/data/banking_crm.db
docker compose start api
```

## 9. Cập nhật phiên bản mới

Upload zip mới vào `/opt`, giải nén đè nhưng **giữ lại `.env` và `docker-compose.yml`** của bạn (dữ liệu nằm trong volume nên không bị đụng tới):

```bash
cd /opt/crm && unzip -o ../crm-deploy.zip -x .env docker-compose.yml
docker compose up -d --build
```

Nếu bản cập nhật có đổi `docker-compose.yml`, so sánh với bản mới rồi chép phần thay đổi sang.

## 10. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| Không vào được `http://IP:1111` | Security Group đã mở cổng 1111 chưa; `docker compose ps`; `docker compose logs web` |
| Trang báo 502 | Backend chưa lên: `docker compose logs api` |
| `web` không khởi động, báo cổng 1111 đã được dùng | Có dịch vụ khác giữ cổng: `ss -tlnp \| grep ':1111 '`, hoặc đổi số cổng ở 2 chỗ trong compose (dòng `ports` và `:1111 {` trong Caddyfile) |
| `api` thoát ngay, log báo "chua dat CRM_SETUP_CODE" | Dòng `CRM_SETUP_CODE` trong compose đang để trống hoặc là `DOI-MA-NAY`: đặt mã khác (bước 3) |
| Trợ lý AI báo thiếu khóa | `GEMINI_API_KEY` trong `.env` còn trống; điền rồi `docker compose up -d` |
| Lệnh compose báo không hiểu `configs.content` / `dockerfile_inline` | Docker Compose cũ; cài lại Docker bằng `curl -fsSL https://get.docker.com \| sh` |
| Quên mật khẩu Admin duy nhất | `docker compose exec -it api python data/reset_admin_password.py tên_đăng_nhập` |
| Tài khoản bị khóa vì nhập sai nhiều lần | Chờ 5 phút, hoặc `docker compose restart api` |
| Xem log | `docker compose logs -f api` |
| Dừng / chạy lại | `docker compose stop` / `docker compose start` |

## 11. Bảo mật — nhắc nhanh

- Đổi khóa Gemini cũ, dùng khóa mới (trong `.env`).
- Mỗi người một tài khoản; khóa tài khoản khi nhân viên nghỉ việc (Quản trị → Người dùng).
- Xem **Nhật ký thao tác** để biết ai đã làm gì.
- OCR đám mây (gửi nội dung file lên Google) mặc định **tắt**; chỉ bật nếu chính sách cho phép.
- Chưa có HTTPS thì chỉ cho phép IP tin cậy vào cổng 1111 (mục 6).
- Dùng SSH key và tắt đăng nhập SSH bằng mật khẩu trên VPS.
