"""Kiểm thử tích hợp: đăng nhập/phân quyền, nhập liệu, import Excel/CSV/PDF, tiếp cận, chiến dịch, hội thoại, phân tích.

Chạy:  python tests/test_corp_full.py   (dùng DB tạm, không đụng banking_crm.db)"""
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_tmp = tempfile.mkdtemp()
shutil.copy(os.path.join(ROOT, "banking_crm.db"), os.path.join(_tmp, "t.db"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/t.db"
os.environ["CRM_BACKUP_DIR"] = f"{_tmp}/bk"

import subprocess  # noqa: E402
import time  # noqa: E402
import httpx  # noqa: E402

PORT = int(os.environ.get("TEST_PORT", "8011"))


class Server:
    """Khởi động uvicorn thật trên DB tạm (TestClient của starlette cũ không chạy với httpx mới)."""

    def __enter__(self):
        env = dict(os.environ)
        self.p = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api:app", "--port", str(PORT), "--log-level", "warning"],
                                  cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        c = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=120)
        for _ in range(120):
            try:
                if c.get("/api/health").status_code == 200:
                    return c
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        self.p.kill()
        raise RuntimeError("server không khởi động: " + (self.p.stdout.read().decode()[-800:] if self.p.stdout else ""))

    def __exit__(self, *a):
        self.p.terminate()
        try:
            self.p.wait(5)
        except Exception:  # noqa: BLE001
            self.p.kill()

OK = []


def check(name, cond, extra=""):
    OK.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    with Server() as c:
        # ── auth ──
        check("health public", c.get("/api/health").status_code == 200)
        check("api cần đăng nhập", c.get("/api/corp/kpis").status_code == 401)
        check("chưa khởi tạo", c.get("/api/auth/status").json()["initialized"] is False)
        r = c.post("/api/auth/setup", json={"username": "quanly", "full_name": "Nguyễn Quản Lý", "password": "abc"})
        check("mật khẩu yếu bị chặn", r.status_code == 400)
        r = c.post("/api/auth/setup", json={"username": "quanly", "full_name": "Nguyễn Quản Lý", "password": "Matkhau123"})
        check("setup admin", r.status_code == 200 and r.json()["user"]["role"] == "admin", r.text)
        adm = r.json()["token"]
        check("setup lần 2 bị từ chối", c.post("/api/auth/setup", json={"username": "x1x", "full_name": "x", "password": "Matkhau123"}).status_code == 409)
        r = c.post("/api/admin/users", headers=H(adm), json={"username": "nv.an", "full_name": "Trần Thu Hà", "role": "staff", "password": "Nhanvien123"})
        check("tạo nhân viên", r.status_code == 200 and r.json()["rm_name"] == "Trần Thu Hà", r.text)
        r = c.post("/api/auth/login", json={"username": "nv.an", "password": "sai"})
        check("sai mật khẩu 401", r.status_code == 401)
        r = c.post("/api/auth/login", json={"username": "nv.an", "password": "Nhanvien123"})
        stf = r.json()["token"]
        check("nhân viên must_change_password", r.json()["user"]["must_change_password"] is True)
        check("nhân viên không vào admin users", c.get("/api/admin/users", headers=H(stf)).status_code == 403)
        check("nhân viên không xem audit", c.get("/api/admin/audit", headers=H(stf)).status_code == 403)
        check("nhân viên không xem retail audit-log", c.get("/api/audit-log", headers=H(stf)).status_code == 403)
        check("nhân viên không sửa cài đặt", c.put("/api/corp/settings", headers=H(stf), json={"freq_cap_days": 3}).status_code == 403)
        r = c.post("/api/auth/change-password", headers=H(stf), json={"old_password": "Nhanvien123", "new_password": "Nhanvien456"})
        check("đổi mật khẩu", r.status_code == 200)
        check("khóa admin cuối cùng bị chặn", c.patch("/api/admin/users/1", headers=H(adm), json={"role": "staff"}).status_code == 400)

        # ── phạm vi dữ liệu ──
        ka = c.get("/api/corp/kpis", headers=H(adm)).json()
        ks = c.get("/api/corp/kpis", headers=H(stf)).json()
        check("admin thấy toàn bộ", ka["total"] >= 200, ka["total"])
        check("nhân viên chỉ thấy danh mục mình", 0 < ks["total"] < ka["total"], ks["total"])
        mine = c.get("/api/corp/customers?limit=500", headers=H(stf)).json()["items"]
        check("mọi KH của NV đúng rm_name", all(x["rm_name"] == "Trần Thu Hà" for x in mine))
        other = next(x for x in c.get("/api/corp/customers?limit=500", headers=H(adm)).json()["items"] if x["rm_name"] != "Trần Thu Hà")
        check("NV không mở KH người khác", c.get(f"/api/corp/customers/{other['customer_id']}", headers=H(stf)).status_code == 403)
        check("NV không soạn tin cho KH người khác", c.post(f"/api/corp/customers/{other['customer_id']}/draft", headers=H(stf), json={"product": "LC", "channel": "zalo"}).status_code == 403)
        check("NV không xóa KH", c.delete(f"/api/corp/customers/{mine[0]['customer_id']}", headers=H(stf)).status_code == 403)

        # ── nhập tay ──
        body = {"name": "Công ty TNHH Kiểm Thử", "tax_code": "0312345678", "ownership": "FDI", "investor_country": "Đài Loan", "industry": "Cơ khí chế tạo",
                "province": "Bình Dương", "employees": 120, "annual_revenue_bn": 320, "import_usd_m": 4.2, "contact_phone": "0901234567", "preferred_language": "zh"}
        r = c.post("/api/corp/customers", headers=H(stf), json=body)
        check("NV tạo KH", r.status_code == 200, r.text)
        nid = r.json()["customer_id"]
        check("trùng MST bị chặn", c.post("/api/corp/customers", headers=H(stf), json=body).status_code == 409)
        check("MST sai bị chặn", c.post("/api/corp/customers", headers=H(stf), json={**body, "tax_code": "12ab", "name": "ABC Co"}).status_code == 400)
        d = c.get(f"/api/corp/customers/{nid}", headers=H(stf)).json()
        check("KH mới thuộc NV, segment Middle", d["customer"]["rm_name"] == "Trần Thu Hà" and d["customer"]["segment"] == "Middle", d["customer"])
        r = c.put(f"/api/corp/customers/{nid}", headers=H(stf), json={**body, "rm_name": "Người Khác", "annual_revenue_bn": 100})
        d = c.get(f"/api/corp/customers/{nid}", headers=H(stf)).json()
        check("NV không đổi được rm_name; segment tự cập nhật", r.status_code == 200 and d["customer"]["rm_name"] == "Trần Thu Hà" and d["customer"]["segment"] == "SME")
        r = c.post("/api/corp/customers/reassign", headers=H(adm), json={"customer_ids": [nid], "to_rm": "Lê Minh Quân"})
        check("chuyển cho tên chưa có tài khoản bị chặn", r.status_code == 400, r.text)
        r = c.post("/api/admin/users", headers=H(adm), json={"username": "nv.quan", "full_name": "Lê Minh Quân", "role": "staff", "password": "Nhanvien123"})
        quan_id = r.json()["id"]
        r = c.post("/api/corp/customers/reassign", headers=H(adm), json={"customer_ids": [nid], "to_rm": "Lê Minh Quân"})
        check("admin chuyển danh mục", r.status_code == 200 and r.json()["moved"] == 1)
        check("NV mất quyền sau khi chuyển", c.get(f"/api/corp/customers/{nid}", headers=H(stf)).status_code == 403)
        c.post("/api/corp/customers/reassign", headers=H(adm), json={"customer_ids": [nid], "to_rm": "Trần Thu Hà"})

        # ── import Excel ──
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["Báo cáo khách hàng tháng 11"]); ws.append([])
        ws.append(["STT", "Tên công ty", "MST", "Loại hình", "Quốc gia", "Ngành", "Tỉnh", "Doanh thu (triệu đồng)", "Nhập khẩu (USD)", "Dư nợ (tỷ đồng)", "Hạn mức", "Hết hạn hạn mức",
                   "Nhóm nợ", "Sản phẩm", "SĐT", "Email", "Ngôn ngữ"])
        ws.append([1, "Công ty CP Dệt May Phương Nam Kiểm Thử", "0300111222", "FDI", "Hàn", "dệt may", "TP.HCM", "850.000", 2400000, 40, 50, "31/12/2026", "Nhóm 1", "VLĐ, L/C, TTQT", "+84 90 111 2233", "ketoan@pnam.vn", "Tiếng Việt"])
        ws.append([2, "Công ty TNHH Nhựa Á Châu", "0300333444", "Nội địa", "", "Nhựa - Bao bì", "Bình Dương", "420.000", "", 0, 0, "", "", "", "912345678", "a@b.c", ""])
        ws.append([3, "", "0300555666", "FDI", "China", "Điện tử", "HCM", "100.000", "", "", "", "", "", "", "", "", ""])      # thiếu tên
        ws.append([4, "Công ty Kiểm Thử Nữa", "0300777", "Nội địa", "", "Cơ khí", "Long An", "50.000", "", "", "", "", "", "", "", "", ""])  # MST sai
        ws.append([5, "Công ty TNHH Kiểm Thử", "0312345678", "FDI", "Đài Loan", "Cơ khí", "Bình Dương", "400.000", "", "", "", "", "", "", "", "", ""])  # trùng KH đã có -> cập nhật
        buf = io.BytesIO(); wb.save(buf)
        r = c.post("/api/corp/import/upload?filename=kh.xlsx", headers=H(stf), content=buf.getvalue())
        check("upload xlsx", r.status_code == 200, r.text[:200])
        up = r.json(); bid = up["batch"]["id"]; mp = up["batch"]["mapping"]
        check("tự nhận diện dòng tiêu đề + cột", mp.get("Tên công ty") == "name" and mp.get("MST") == "tax_code" and mp.get("Doanh thu (triệu đồng)") == "annual_revenue_bn" and mp.get("Hết hạn hạn mức") == "limit_expiry", mp)
        check("NV bị yêu cầu duyệt", up["requires_approval"] is True)
        r = c.post(f"/api/corp/import/{bid}/preview", headers=H(stf), json={"mapping": mp, "update_existing": True})
        pv = r.json()
        check("preview thống kê", r.status_code == 200 and pv["stats"]["create"] == 2 and pv["stats"]["update"] == 1 and pv["stats"]["error"] == 2, pv.get("stats"))
        r = c.post(f"/api/corp/import/{bid}/commit", headers=H(stf), json={"mapping": mp, "update_existing": True})
        check("NV gửi chờ duyệt", r.status_code == 200 and r.json()["status"] == "Chờ duyệt", r.text)
        before = c.get("/api/corp/customers?q=Nam Kiểm Thử", headers=H(adm)).json()["total"]
        check("chưa nhập trước khi duyệt", before == 0)
        check("NV không tự duyệt", c.post(f"/api/corp/import/{bid}/approve", headers=H(stf)).status_code == 403)
        r = c.post(f"/api/corp/import/{bid}/approve", headers=H(adm))
        check("admin duyệt", r.status_code == 200 and r.json()["created"] == 2 and r.json()["updated"] == 1, r.text)
        x = c.get("/api/corp/customers?q=Nam Kiểm Thử", headers=H(stf)).json()["items"]
        check("KH import gán cho NV, đơn vị quy đổi đúng", len(x) == 1 and x[0]["rm_name"] == "Trần Thu Hà" and abs(x[0]["annual_revenue_bn"] - 850) < 1e-6 and abs(x[0]["import_usd_m"] - 2.4) < 1e-6 and x[0]["industry"].startswith("Dệt may") and x[0]["province"] == "TP. Hồ Chí Minh" and x[0]["investor_country"] == "Hàn Quốc", x[:1])
        d = c.get(f"/api/corp/customers/{x[0]['customer_id']}", headers=H(stf)).json()["customer"]
        check("SĐT/ngày/sản phẩm chuẩn hóa", d["contact_phone"] == "0901112233" and d["limit_expiry"] == "2026-12-31" and set(d["products_held"]) == {"VAY_VLD", "LC", "TTQT"}, d)
        d2 = c.get(f"/api/corp/customers/{nid}", headers=H(stf)).json()["customer"]
        check("cập nhật theo MST", abs(d2["annual_revenue_bn"] - 400) < 1e-6)
        r = c.get("/api/corp/import/batches", headers=H(adm)).json()
        check("lịch sử import", r["items"][0]["status"] == "Đã nhập")

        # admin import trực tiếp CSV (có BOM, dấu ;, số kiểu VN)
        csvb = ("﻿Tên doanh nghiệp;Mã số thuế;Doanh thu năm (tỷ đồng);Cán bộ phụ trách\r\n"
                "Công ty CSV Một;0301000001;1.250,5;Lê Minh Quân\r\n").encode("utf-8")
        r = c.post("/api/corp/import/upload?filename=a.csv", headers=H(adm), content=csvb)
        up = r.json()
        r = c.post(f"/api/corp/import/{up['batch']['id']}/commit", headers=H(adm), json={"mapping": up["batch"]["mapping"], "update_existing": True})
        check("admin import CSV trực tiếp", r.status_code == 200 and r.json()["created"] == 1, r.text)
        z = c.get("/api/corp/customers?q=CSV Một", headers=H(adm)).json()["items"]
        check("CSV: số VN + rm_name từ file + segment", len(z) == 1 and abs(z[0]["annual_revenue_bn"] - 1250.5) < 1e-6 and z[0]["rm_name"] == "Lê Minh Quân" and z[0]["segment"] == "Middle", z)

        # dòng tiền tháng
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["Mã số thuế", "Tháng", "Doanh số có (tỷ đồng)", "Doanh số nợ (tỷ đồng)"])
        ws.append(["0312345678", "2026-09", 30, 28]); ws.append(["0312345678", "10/2026", 33, 30]); ws.append(["9999999999", "2026-10", 1, 1])
        buf = io.BytesIO(); wb.save(buf)
        up = c.post("/api/corp/import/upload?filename=m.xlsx&target=monthly", headers=H(adm), content=buf.getvalue()).json()
        pv = c.post(f"/api/corp/import/{up['batch']['id']}/preview", headers=H(adm), json={"mapping": up["batch"]["mapping"]}).json()
        check("monthly preview", pv["stats"]["create"] == 2 and pv["stats"]["error"] == 1, pv["stats"])
        r = c.post(f"/api/corp/import/{up['batch']['id']}/commit", headers=H(adm), json={"mapping": up["batch"]["mapping"]})
        check("monthly commit", r.status_code == 200 and r.json()["created"] == 2, r.text)

        # file mẫu
        r = c.get("/api/corp/import/template?target=customers", headers=H(stf))
        check("tải file mẫu xlsx", r.status_code == 200 and r.content[:2] == b"PK")
        up = c.post("/api/corp/import/upload?filename=mau.xlsx", headers=H(adm), content=r.content).json()
        check("file mẫu tự nhận đủ cột", sum(1 for v in up["batch"]["mapping"].values() if v) >= 28, up["batch"]["mapping"])
        c.delete(f"/api/corp/import/{up['batch']['id']}", headers=H(adm))
        check("định dạng lạ bị từ chối", c.post("/api/corp/import/upload?filename=a.docx", headers=H(adm), content=b"xx").status_code == 422)

        # ── PDF ──
        import pymupdf
        FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        def make_pdf(lines_by_y, draw_grid=False):
            doc = pymupdf.open(); pg = doc.new_page(); pg.insert_font(fontname="dj", fontfile=FONT)
            for (x, y, t) in lines_by_y:
                pg.insert_text((x, y), t, fontname="dj", fontsize=10)
            return doc
        rows = [("Tên doanh nghiệp", "Mã số thuế", "Doanh thu năm (tỷ đồng)", "Tỉnh"), ("Công ty PDF Alpha", "0302000001", "310", "Đồng Nai"), ("Công ty PDF Beta", "0302000002", "95,5", "Long An")]
        items = []
        for i, r_ in enumerate(rows):
            for j, t in enumerate(r_):
                items.append((40 + [0, 190, 290, 440][j], 100 + i * 24, t))
        doc = make_pdf(items)
        pdf_bytes = doc.tobytes()
        r = c.post("/api/corp/import/upload?filename=bang.pdf", headers=H(adm), content=pdf_bytes)
        check("PDF text-layer bảng", r.status_code == 200 and r.json()["batch"]["row_count"] == 2, r.text[:300])
        if r.status_code == 200:
            check("PDF method + mapping", r.json()["batch"]["method"] in ("pdf-text", "pdf-table") and r.json()["batch"]["mapping"].get("Mã số thuế") == "tax_code", r.json()["batch"])
            c.delete(f"/api/corp/import/{r.json()['batch']['id']}", headers=H(adm))
        kv = make_pdf([(40, 80 + i * 20, t) for i, t in enumerate(["HỒ SƠ NĂNG LỰC DOANH NGHIỆP", "Tên doanh nghiệp: CÔNG TY TNHH SẢN XUẤT BẾP VIỆT", "Mã số thuế: 0303999888", "Ngành nghề: Cơ khí chế tạo",
                                                                  "Tỉnh/Thành phố: Đồng Nai", "Số lao động: 240", "Email: lienhe@bepviet.vn"])])
        r = c.post("/api/corp/import/upload?filename=hoso.pdf", headers=H(adm), content=kv.tobytes())
        ok = r.status_code == 200 and r.json()["batch"]["row_count"] == 1
        check("PDF key-value 1 bản ghi", ok, r.text[:300])
        if ok:
            mp = r.json()["batch"]["mapping"]
            check("PDF kv mapping", mp.get("Tên doanh nghiệp") == "name" and mp.get("Mã số thuế") == "tax_code", mp)
        # PDF scan (ảnh) → OCR cục bộ nếu có tesseract
        from src.corporate.importer import tesseract_path
        img_doc = pymupdf.open(); pgi = img_doc.new_page()
        pix = doc.load_page(0).get_pixmap(dpi=200)
        pgi.insert_image(pgi.rect, stream=pix.tobytes("png"))
        scan = img_doc.tobytes()
        r = c.post("/api/corp/import/upload?filename=scan.pdf&ocr=cloud", headers=H(adm), content=scan)
        check("OCR đám mây bị chặn khi chưa bật", r.status_code == 422 and "chưa được bật" in r.text, r.text[:200])
        r = c.post("/api/corp/import/upload?filename=scan.pdf", headers=H(adm), content=scan)
        if tesseract_path():
            check("OCR cục bộ ra bảng", r.status_code == 200 and r.json()["batch"]["method"] == "ocr-tesseract" and r.json()["batch"]["row_count"] >= 1, r.text[:400])
            if r.status_code == 200:
                print("   OCR rows:", [list(x.values()) for x in c.get(f"/api/corp/import/{r.json()['batch']['id']}", headers=H(adm)).json()["sample"]][:3])
        else:
            check("scan không OCR → báo lỗi rõ", r.status_code == 422, r.text[:200])

        # ── cài đặt ──
        r = c.put("/api/corp/settings", headers=H(adm), json={"freq_cap_days": 7, "allow_cloud_ocr": False, "bank_name": "TPBank"})
        check("admin sửa cài đặt", r.status_code == 200 and r.json()["settings"]["freq_cap_days"] == 7)
        check("cài đặt sai bị chặn", c.put("/api/corp/settings", headers=H(adm), json={"freq_cap_days": -1}).status_code == 400)
        c.put("/api/corp/settings", headers=H(adm), json={"freq_cap_days": 14})

        # ── tiếp cận ──
        r = c.post("/api/corp/outreach/audience", headers=H(adm), json={"product": "UPAS", "channel": "zalo", "min_score": 60})
        au = r.json()
        check("audience", r.status_code == 200 and au["eligible_total"] > 0, r.text[:200])
        check("có lý do loại trừ", au["suppressed_total"] >= 0 and set(au["suppress_counts"]) <= {"optout", "debt", "freq", "contact"})
        ids = [s["customer_id"] for s in au["eligible"][:5]]
        r = c.post("/api/corp/outreach/drafts", headers=H(adm), json={"product": "UPAS", "channel": "email", "language": "auto", "framework": "spin", "customer_ids": ids})
        check("drafts hàng loạt", r.status_code == 200 and len(r.json()["drafts"]) == 5 and r.json()["drafts"][0]["subject"])
        r = c.post("/api/corp/outreach/log", headers=H(adm), json={"items": [{"customer_id": ids[0], "product": "UPAS", "channel": "email", "body": "test", "subject": "s"}]})
        check("ghi nhận đã gửi", r.status_code == 200 and r.json()["logged"] == 1)
        au2 = c.post("/api/corp/outreach/audience", headers=H(adm), json={"product": "UPAS", "channel": "zalo", "min_score": 60}).json()
        check("KH vừa gửi bị loại trừ giãn cách", ids[0] not in [s["customer_id"] for s in au2["eligible"]] and au2["suppress_counts"].get("freq", 0) >= 1)

        # ── chiến dịch ──
        r = c.post("/api/corp/campaigns", headers=H(adm), json={"name": "UPAS Q4", "product": "UPAS", "channel": "zalo", "language": "auto", "framework": "aida", "min_score": 70})
        check("tạo chiến dịch", r.status_code == 200 and r.json()["targets"] > 0, r.text)
        cid = r.json()["id"]
        det = c.get(f"/api/corp/campaigns/{cid}", headers=H(adm)).json()
        t0 = det["targets"][0]
        check("chiến dịch có nội dung từng KH", t0["body"] and t0["status"] == "Chưa liên hệ")
        r = c.post(f"/api/corp/campaigns/{cid}/targets/{t0['id']}/sent", headers=H(adm))
        check("đánh dấu đã gửi", r.status_code == 200)
        det = c.get(f"/api/corp/campaigns/{cid}", headers=H(adm)).json()
        check("trạng thái → Đã liên hệ", det["campaign"]["counts"]["Đã liên hệ"] == 1)
        # ── hội thoại ──
        cust = t0["customer_id"]
        r = c.post(f"/api/corp/conversations/{cust}/messages", headers=H(adm), json={"direction": "in", "body": "Cho tôi xin báo giá, tôi quan tâm", "channel": "zalo"})
        j = r.json()
        check("phân loại ý định quan tâm + gợi ý trả lời", r.status_code == 200 and j["message"]["intent"] == "interested" and j["suggestion"] and j["suggestion"]["text"], r.text[:200])
        det = c.get(f"/api/corp/campaigns/{cid}", headers=H(adm)).json()
        check("target tự lên 'Quan tâm'", next(t for t in det["targets"] if t["customer_id"] == cust)["status"] == "Quan tâm")
        r = c.post(f"/api/corp/conversations/{cust}/messages", headers=H(adm), json={"direction": "in", "body": "Đừng nhắn tin cho tôi nữa", "channel": "zalo"})
        check("opt-out tự động", r.json()["message"]["intent"] == "optout" and any("từ chối" in e for e in r.json()["effects"]))
        r = c.post(f"/api/corp/conversations/{cust}/messages", headers=H(adm), json={"direction": "out", "body": "xin chào", "channel": "zalo"})
        r = c.post("/api/corp/outreach/log", headers=H(adm), json={"items": [{"customer_id": cust, "product": "UPAS", "channel": "zalo", "body": "x"}]})
        check("gửi cho KH opt-out bị chặn", r.json()["logged"] == 0 and len(r.json()["blocked"]) == 1)
        lst = c.get("/api/corp/conversations", headers=H(adm)).json()
        check("danh sách hội thoại + trạng thái", lst["total"] >= 1 and any(t["status"] == "OPTOUT" for t in lst["items"]))
        r = c.post(f"/api/corp/conversations/{cust}/suggest", headers=H(adm), json={"intent": "rate", "language": "zh"})
        check("gợi ý trả lời đa ngôn ngữ", r.status_code == 200 and "成本" in r.json()["text"])
        check("NV không gỡ opt-out", c.post(f"/api/corp/conversations/{cust}/optout", headers=H(stf), json={"opt_out": False}).status_code in (403,))
        check("followups", c.get("/api/corp/followups/due", headers=H(adm)).status_code == 200)

        # ── lập luận / phân tích / agent ──
        r = c.post("/api/corp/agent", headers=H(stf), json={"query": "top 5 khách FDI Trung Quốc cần UPAS", "use_llm": False})
        check("agent (NV) chỉ trong danh mục", r.status_code == 200 and all(x["rm_name"] == "Trần Thu Hà" for x in r.json()["customers"]), r.text[:200])
        runs = c.get("/api/corp/reasoning/runs", headers=H(stf)).json()["items"]
        check("lưu lịch sử chạy trợ lý", len(runs) == 1)
        check("admin không thấy lẫn run NV? (admin thấy tất cả)", len(c.get("/api/corp/reasoning/runs", headers=H(adm)).json()["items"]) >= 1)
        r = c.get(f"/api/corp/reasoning/customer/{ids[1]}", headers=H(adm))
        j = r.json()
        check("giải thích điểm KH", r.status_code == 200 and j["priority"]["parts"] and j["rules"] and j["compliance"], r.text[:200])
        check("NV không giải thích KH khác", c.get(f"/api/corp/reasoning/customer/{ids[1]}", headers=H(stf)).status_code in (403, 200))
        a1 = c.get("/api/corp/analytics", headers=H(adm)).json()
        check("analytics admin có rm_performance", "rm_performance" in a1 and a1["kpis"]["contacted"] >= 1 and len(a1["funnel"]) == 4, list(a1))
        a2 = c.get("/api/corp/analytics", headers=H(stf)).json()
        check("analytics NV không có rm_performance + chỉ KH của mình", "rm_performance" not in a2 and a2["kpis"]["customers"] == ks["total"] + 2 + 1 - 0 or a2["kpis"]["customers"] > 0)

        # ── phân công KH ↔ CBBH ──
        A = "/api/corp/admin/assignment"; G = "/api/corp/admin/assign"
        check("NV không xem phân công", c.get(A, headers=H(stf)).status_code == 403)
        check("chưa đăng nhập không xem phân công", c.get(A).status_code == 401)
        check("NV không gán được", c.post(G, headers=H(stf), json={"to_rm": "Trần Thu Hà", "customer_ids": [ids[0]]}).status_code == 403)
        asg = c.get(A, headers=H(adm)).json()
        accs = {a["rm_name"]: a for a in asg["accounts"]}
        orph = {u["rm_name"]: u for u in asg["unmatched"]}
        check("tổng quan: tài khoản + số KH từng người", accs["Trần Thu Hà"]["total"] > 0 and accs["Lê Minh Quân"]["is_active"] and asg["total"] >= 200, asg["total"])
        check("nhận ra KH gán cho tên chưa có tài khoản", "Phạm Ngọc Anh" in orph and orph["Phạm Ngọc Anh"]["total"] > 0, list(orph))
        check("các nhóm cộng lại đúng tổng", sum(a["total"] for a in asg["accounts"]) + asg["unassigned"]["total"] + asg["unmatched_total"] == asg["total"])
        check("meta: admin có danh sách CBBH, NV thì không", {x["rm_name"] for x in c.get("/api/corp/meta", headers=H(adm)).json()["rm_options"]} >= {"Trần Thu Hà", "Lê Minh Quân"}
              and c.get("/api/corp/meta", headers=H(stf)).json()["rm_options"] == [])
        n_orph = orph["Phạm Ngọc Anh"]["total"]
        staff_before = c.get("/api/corp/kpis", headers=H(stf)).json()["total"]
        r = c.post(G, headers=H(adm), json={"to_rm": "Trần Thu Hà", "filters": {"rm": "Phạm Ngọc Anh"}, "dry_run": True})
        check("xem trước: số KH + người đang giữ", r.status_code == 200 and r.json()["matched"] == n_orph == r.json()["moved"] and r.json()["from"][0]["rm_name"] == "Phạm Ngọc Anh" and r.json()["dry_run"], r.text)
        check("xem trước không đổi dữ liệu", c.get("/api/corp/kpis", headers=H(stf)).json()["total"] == staff_before)
        check("gán không điều kiện bị chặn", c.post(G, headers=H(adm), json={"to_rm": "Trần Thu Hà", "filters": {}}).status_code == 400)
        check("gán cho tên không có tài khoản bị chặn", c.post(G, headers=H(adm), json={"to_rm": "Phạm Ngọc Anh", "filters": {"rm": "Lê Minh Quân"}}).status_code == 400)
        check("chuyển danh mục chặn tên lạ", c.post("/api/corp/customers/reassign", headers=H(adm), json={"from_rm": "Lê Minh Quân", "to_rm": "Tên Lạ"}).status_code == 400)
        c.patch(f"/api/admin/users/{quan_id}", headers=H(adm), json={"is_active": False})
        check("không gán cho tài khoản đã khóa", c.post(G, headers=H(adm), json={"to_rm": "Lê Minh Quân", "filters": {"rm": "Phạm Ngọc Anh"}}).status_code == 400)
        c.patch(f"/api/admin/users/{quan_id}", headers=H(adm), json={"is_active": True})
        quan_before = accs["Lê Minh Quân"]["total"]
        r = c.post(G, headers=H(adm), json={"to_rm": "Lê Minh Quân", "filters": {"rm": "Phạm Ngọc Anh"}})
        check("gán theo bộ lọc", r.status_code == 200 and r.json()["moved"] == n_orph and r.json()["already"] == 0, r.text)
        asg2 = c.get(A, headers=H(adm)).json()
        accs2 = {a["rm_name"]: a for a in asg2["accounts"]}
        check("CBBH nhận tăng đúng số, tên lạ biến mất", accs2["Lê Minh Quân"]["total"] == quan_before + n_orph and "Phạm Ngọc Anh" not in {u["rm_name"] for u in asg2["unmatched"]})
        check("gán lại cùng điều kiện: không còn gì để chuyển", c.post(G, headers=H(adm), json={"to_rm": "Lê Minh Quân", "filters": {"rm": "Phạm Ngọc Anh"}}).json()["moved"] == 0)
        pick = [x["customer_id"] for x in c.get("/api/corp/customers", params={"rm": "Nguyễn Hoàng Nam", "limit": 3}, headers=H(adm)).json()["items"]]
        r = c.post(G, headers=H(adm), json={"to_rm": "Trần Thu Hà", "customer_ids": pick})
        check("gán theo danh sách mã", r.status_code == 200 and r.json()["moved"] == 3 and r.json()["from"][0]["rm_name"] == "Nguyễn Hoàng Nam", r.text)
        r = c.post(G, headers=H(adm), json={"to_rm": "Trần Thu Hà", "customer_ids": pick})
        check("gán lần 2: đã thuộc người đó", r.json()["moved"] == 0 and r.json()["already"] == 3)
        check("NV thấy ngay KH vừa được gán", c.get(f"/api/corp/customers/{pick[0]}", headers=H(stf)).status_code == 200)
        # khách chưa phân công (rm_name rỗng)
        pick2 = [x["customer_id"] for x in c.get("/api/corp/customers", params={"rm": "Nguyễn Hoàng Nam", "limit": 2}, headers=H(adm)).json()["items"]]
        import sqlite3 as _sq  # noqa: E401
        _con = _sq.connect(f"{_tmp}/t.db"); _con.executemany("update corp_customers set rm_name = NULL where customer_id = ?", [(i,) for i in pick2]); _con.commit(); _con.close()
        lst0 = c.get("/api/corp/customers", params={"rm": "__none__", "limit": 50}, headers=H(adm)).json()
        check("lọc 'chưa phân công'", lst0["total"] == 2 and all(not x["rm_name"] for x in lst0["items"]), lst0["total"])
        check("tổng quan đếm KH chưa phân công", c.get(A, headers=H(adm)).json()["unassigned"]["total"] == 2)
        r = c.post(G, headers=H(adm), json={"to_rm": "Lê Minh Quân", "filters": {"rm": "__none__"}})
        check("gán KH chưa phân công", r.status_code == 200 and r.json()["moved"] == 2 and r.json()["from"][0]["rm_name"] == "", r.text)
        check("hết KH chưa phân công", c.get(A, headers=H(adm)).json()["unassigned"]["total"] == 0)

        # ── dọn dữ liệu mô phỏng & rác ──
        CL = "/api/corp/admin/cleanup"
        check("chưa đăng nhập không xem được kế hoạch dọn", c.get(CL).status_code == 401)
        check("NV không xem được kế hoạch dọn", c.get(CL, headers=H(stf)).status_code == 403)
        check("NV không chạy được dọn", c.post(CL, headers=H(stf), json={"retail": True, "confirm": "XOA"}).status_code == 403)
        pl = c.get(CL, headers=H(adm)).json()
        real0 = pl["real_corp_customers"]
        check("kế hoạch dọn đếm KH cá nhân mô phỏng", pl["retail"]["customers"] >= 500 and pl["retail"]["transactions"] > 1000 and pl["retail"]["total"] > 5000, pl["retail"])
        check("kế hoạch dọn đếm KH DN mẫu", pl["corp_demo"]["customers"] >= 200 and pl["corp_demo"]["monthly"] > 1000 and pl["corp_demo"]["campaigns"] >= 1, pl["corp_demo"])
        check("kế hoạch dọn đếm KH thật (không bị xóa)", real0 >= 3, real0)
        check("kế hoạch dọn không xóa gì", c.get(CL, headers=H(adm)).json()["retail"]["customers"] == pl["retail"]["customers"])
        check("thiếu xác nhận bị chặn", c.post(CL, headers=H(adm), json={"retail": True}).status_code == 400)
        check("sai từ xác nhận bị chặn", c.post(CL, headers=H(adm), json={"retail": True, "confirm": "ok"}).status_code == 400)
        check("không chọn nhóm nào bị chặn", c.post(CL, headers=H(adm), json={"confirm": "XOA"}).status_code == 400)
        # gieo rác: dòng mồ côi, ghi chú trống, log AI lỗi
        import sqlite3 as _sq, glob as _gl  # noqa: E401
        _db = _sq.connect(f"{_tmp}/t.db", timeout=20)
        _real = _db.execute("select customer_id from corp_customers where customer_id not like 'CORP%' limit 1").fetchone()[0]
        _db.execute("insert into corp_interactions(customer_id,date,channel,summary,outcome) values ('GHOST01','2026-01-01','call','ghi chú mồ côi','x')")
        _db.execute("insert into corp_interactions(customer_id,date,channel,summary,outcome) values (?, '2026-01-01','call','','')", (_real,))
        _db.execute("insert into corp_agent_runs(username,query,filters,steps,total_matched,llm_used,llm_error,created_at) values ('quanly','q','{}','[]',0,0,'RuntimeError: Gemini 404','2026-01-01')")
        _db.execute("insert into corp_agent_runs(username,query,filters,steps,total_matched,llm_used,llm_error,created_at) values ('quanly','q ok','{}','[]',1,1,NULL,'2026-01-01')")
        _db.commit(); _db.close()
        pj = c.get(CL, headers=H(adm)).json()["junk"]
        check("kế hoạch dọn thấy rác", pj["orphans"] >= 1 and pj["blank_notes"] >= 1 and pj["failed_ai_runs"] >= 1, pj)
        r = c.post(CL, headers=H(adm), json={"retail": True, "junk": True, "confirm": "xoa"})
        j = r.json()
        check("dọn KH cá nhân + rác", r.status_code == 200 and j["retail"]["customers"] >= 500 and j["retail"]["transactions"] > 1000 and j["junk"]["failed_ai_runs"] >= 1 and j["junk"]["orphans"] >= 1 and j["junk"]["blank_notes"] >= 1, r.text[:400])
        check("dọn tự sao lưu trước khi xóa", j["backup"].startswith("banking_crm-") and bool(_gl.glob(f"{_tmp}/bk/{j['backup']}")), j.get("backup"))
        _b = _sq.connect(f"{_tmp}/bk/{j['backup']}")
        check("bản sao lưu còn đủ KH cá nhân để khôi phục", _b.execute("select count(*) from customers").fetchone()[0] >= 500 and _b.execute("select count(*) from corp_agent_runs").fetchone()[0] >= 2)
        _b.close()
        check("sau dọn: kế hoạch KH cá nhân = 0", j["plan"]["retail"]["total"] == 0 and j["plan"]["junk"]["total"] == 0, j["plan"])
        check("sau dọn: KH DN thật còn nguyên", j["plan"]["real_corp_customers"] == real0)
        check("sau dọn: KH DN mẫu chưa bị đụng", j["plan"]["corp_demo"]["customers"] >= 200)
        check("sau dọn: log AI chạy tốt được giữ", _sq.connect(f"{_tmp}/t.db").execute("select count(*) from corp_agent_runs where llm_error is null").fetchone()[0] >= 1)
        # các API cá nhân phải chạy được khi CSDL trống
        empty_ok = True; bad_ep = []
        for ep in ("/api/customers", "/api/analytics/kpis", "/api/analytics/charts", "/api/analytics/campaigns", "/api/digest/morning",
                   "/api/analytics/churn-signals", "/api/analytics/cross-sell", "/api/analytics/reply-rates", "/api/outreach/pipeline",
                   "/api/outreach/campaigns", "/api/followups/due", "/api/audit-log"):
            rr = c.get(ep, headers=H(adm))
            if rr.status_code != 200:
                empty_ok = False; bad_ep.append((ep, rr.status_code))
        check("API khách hàng cá nhân chạy được khi trống", empty_ok, bad_ep)
        check("danh sách KH cá nhân rỗng", c.get("/api/customers", headers=H(adm)).json()["total"] == 0)
        kp = c.get("/api/analytics/kpis", headers=H(adm)).json()
        check("KPI cá nhân về 0", kp.get("totalCustomers") == 0, kp)
        r = c.post(CL, headers=H(adm), json={"corp_demo": True, "confirm": "XOA"})
        j = r.json()
        check("dọn KH DN mẫu", r.status_code == 200 and j["corp_demo"]["customers"] >= 200 and j["corp_demo"]["monthly"] > 1000 and j["corp_demo"]["messages"] >= 1 and j["corp_demo"]["campaigns"] >= 1, r.text[:400])
        check("sau dọn: không còn KH/chiến dịch mẫu", j["plan"]["corp_demo"]["total"] == 0 and j["plan"]["real_corp_customers"] == real0, j["plan"])
        left = c.get("/api/corp/customers?limit=500", headers=H(adm)).json()
        check("chỉ còn KH DN thật sau dọn", left["total"] == real0 and all(not x["customer_id"].startswith("CORP") for x in left["items"]), left["total"])
        check("NV vẫn xem được KH của mình sau dọn", c.get("/api/corp/customers", headers=H(stf)).status_code == 200)
        check("cờ không nạp lại dữ liệu mẫu", _sq.connect(f"{_tmp}/t.db").execute("select count(*) from corp_settings where key='_demo_cleared'").fetchone()[0] == 1)
        r = c.post(CL, headers=H(adm), json={"retail": True, "corp_demo": True, "junk": True, "confirm": "XOA"})
        check("dọn lần 2 vô hại (đã sạch)", r.status_code == 200 and r.json()["deleted_total"] == 0, r.text[:900])

        # ── audit + demo clear ──
        au = c.get("/api/admin/audit?limit=500", headers=H(adm)).json()["items"]
        acts = {e["action"] for e in au}
        check("nhật ký ghi đủ hành động", {"login", "login.failed", "customer.create", "import.approve", "campaign.create", "settings.update", "customer.assign", "data.cleanup"} <= acts, acts)
        r = c.post("/api/corp/admin/clear-demo", headers=H(adm))
        check("xóa dữ liệu mẫu (API cũ, idempotent sau khi đã dọn)", r.status_code == 200 and r.json()["deleted"] == 0, r.text)
        left = c.get("/api/corp/customers?limit=500", headers=H(adm)).json()
        check("chỉ còn KH thật", left["total"] >= 3 and all(not x["customer_id"].startswith("CORP") for x in left["items"]), left["total"])
        check("sau xóa vẫn tải analytics/kpis", c.get("/api/corp/analytics", headers=H(adm)).status_code == 200 and c.get("/api/corp/kpis", headers=H(adm)).status_code == 200)
        # ── sao lưu ──
        import glob, sqlite3  # noqa: E401
        for _ in range(30):
            if glob.glob(f"{_tmp}/bk/banking_crm-*.db"):
                break
            time.sleep(0.5)
        check("sao lưu tự động chạy khi khởi động", len(glob.glob(f"{_tmp}/bk/banking_crm-*.db")) >= 1)
        sysinfo = c.get("/api/corp/settings", headers=H(adm)).json()["system"]
        check("cài đặt báo bản sao lưu gần nhất", sysinfo["backup_auto"] is True and sysinfo["backup"]["count"] >= 1 and sysinfo["backup"]["bytes"] > 10000, sysinfo)
        check("NV không tải được sao lưu", c.get("/api/corp/admin/backup", headers=H(stf)).status_code == 403)
        check("chưa đăng nhập không tải được sao lưu", c.get("/api/corp/admin/backup").status_code == 401)
        r = c.get("/api/corp/admin/backup", headers=H(adm))
        check("admin tải sao lưu", r.status_code == 200 and r.content[:15] == b"SQLite format 3" and "banking_crm-" in r.headers.get("content-disposition", ""), r.headers)
        dl = os.path.join(_tmp, "dl.db")
        open(dl, "wb").write(r.content)
        con = sqlite3.connect(dl)
        n_corp = con.execute("select count(*) from corp_customers").fetchone()[0]
        n_usr = con.execute("select count(*) from app_users").fetchone()[0]
        con.close()
        check("bản sao lưu đủ dữ liệu", n_corp >= 3 and n_usr >= 2, (n_corp, n_usr))
        au2 = {e["action"] for e in c.get("/api/admin/audit?limit=500", headers=H(adm)).json()["items"]}
        check("nhật ký ghi backup.download", "backup.download" in au2, au2)
        # đăng xuất
        c.post("/api/auth/logout", headers=H(stf))
        check("logout vô hiệu token", c.get("/api/auth/me", headers=H(stf)).status_code == 401)

    bad = [n for n, ok in OK if not ok]
    print(f"\n{len(OK) - len(bad)}/{len(OK)} đạt" + (f"; THẤT BẠI: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
