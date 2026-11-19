"""Đọc file Excel / CSV / PDF (có OCR) → dòng dữ liệu thô → chuẩn hóa → kiểm tra → nhập.

Thư viện nặng (openpyxl, pymupdf) chỉ nạp khi cần để backend vẫn khởi động được nếu thiếu."""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

from .catalog import PRODUCTS, TITLES, INDUSTRIES, LOCATIONS

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 5000


class ImportError_(Exception):
    """Lỗi người dùng đọc được (tiếng Việt)."""


# ── chuẩn hóa chuỗi ──────────────────────────────────────────────────────────
def fold(s) -> str:
    s = unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def key_of(s) -> str:
    """Chuỗi so khớp tiêu đề: bỏ dấu, bỏ phần trong ngoặc, chỉ giữ chữ-số (và chữ Hán)."""
    s = re.sub(r"[\(\[（].*?[\)\]）]", " ", str(s))
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", fold(s))


# ── định nghĩa trường & từ đồng nghĩa tiêu đề ────────────────────────────────
FIELDS = {
    "customer_id": ("Mã KH", ["ma kh", "ma khach hang", "customer id", "id", "cif", "ma cif", "so cif"]),
    "name": ("Tên doanh nghiệp", ["ten doanh nghiep", "ten cong ty", "ten khach hang", "cong ty", "doanh nghiep", "company name", "company", "name", "ten dn", "ten kh", "企业名称", "公司名称"]),
    "name_zh": ("Tên tiếng Trung", ["ten tieng trung", "ten zh", "chinese name", "ten trung quoc", "中文名称", "中文名"]),
    "tax_code": ("Mã số thuế", ["ma so thue", "mst", "tax code", "tax id", "tax no", "ma so dn", "税号"]),
    "ownership": ("Loại hình (Nội địa/FDI)", ["loai hinh", "loai hinh doanh nghiep", "loai hinh dn", "ownership", "hinh thuc dau tu"]),
    "investor_country": ("Quốc gia nhà đầu tư", ["quoc gia nha dau tu", "quoc gia", "nuoc dau tu", "nha dau tu", "investor country", "country", "投资国"]),
    "industry": ("Ngành nghề", ["nganh", "nganh nghe", "linh vuc", "linh vuc hoat dong", "industry", "sector"]),
    "province": ("Tỉnh/Thành phố", ["tinh", "tinh thanh", "tinh thanh pho", "thanh pho", "province", "city", "dia ban"]),
    "industrial_zone": ("KCN/KCX", ["kcn", "kcx", "kcn kcx", "khu cong nghiep", "industrial zone", "园区"]),
    "employees": ("Số lao động", ["so lao dong", "lao dong", "nhan su", "so nhan vien", "employees", "headcount"]),
    "annual_revenue_bn": ("Doanh thu năm", ["doanh thu", "doanh thu nam", "revenue", "annual revenue", "turnover"]),
    "total_assets_bn": ("Tổng tài sản", ["tong tai san", "assets", "total assets"]),
    "equity_bn": ("Vốn chủ sở hữu", ["von chu so huu", "vcsh", "equity"]),
    "export_usd_m": ("Xuất khẩu", ["xuat khau", "kim ngach xuat khau", "export", "exports"]),
    "import_usd_m": ("Nhập khẩu", ["nhap khau", "kim ngach nhap khau", "import", "imports"]),
    "fx_exposure_usd_m": ("Trạng thái ngoại tệ", ["trang thai ngoai te", "nhu cau ngoai te", "fx exposure", "fx"]),
    "casa_balance_bn": ("Số dư CASA BQ", ["casa", "so du casa", "so du khong ky han", "so du binh quan", "casa balance"]),
    "deposit_bn": ("Tiền gửi có kỳ hạn", ["tien gui co ky han", "tien gui", "deposit", "term deposit"]),
    "loan_outstanding_bn": ("Dư nợ", ["du no", "du no tin dung", "loan", "outstanding", "loan outstanding"]),
    "credit_limit_bn": ("Hạn mức tín dụng", ["han muc", "han muc tin dung", "credit limit", "limit"]),
    "limit_expiry": ("Ngày hết hạn hạn mức", ["ngay het han han muc", "han muc het han", "ngay het han", "het han han muc", "limit expiry", "expiry", "han muc den ngay"]),
    "debt_group": ("Nhóm nợ", ["nhom no", "debt group", "nhom no cic"]),
    "relationship_years": ("Số năm quan hệ", ["so nam quan he", "nam quan he", "thoi gian quan he", "relationship years"]),
    "products_held": ("Sản phẩm đang dùng", ["san pham dang dung", "san pham", "products", "products held", "dich vu dang dung"]),
    "rm_name": ("Cán bộ phụ trách", ["can bo phu trach", "rm", "rm name", "cbqhkh", "can bo quan he khach hang", "nguoi phu trach", "rm phu trach"]),
    "contact_name": ("Người liên hệ", ["nguoi lien he", "ten nguoi lien he", "lien he", "contact", "contact name"]),
    "contact_name_zh": ("Tên người LH (Trung)", ["ten nguoi lien he zh", "contact name zh", "联系人"]),
    "contact_title": ("Chức danh", ["chuc danh", "chuc vu", "title", "position"]),
    "contact_phone": ("SĐT liên hệ", ["sdt", "so dien thoai", "dien thoai", "phone", "mobile", "tel", "sdt lien he"]),
    "contact_email": ("Email liên hệ", ["email", "mail", "e mail", "email lien he"]),
    "preferred_language": ("Ngôn ngữ ưu tiên", ["ngon ngu", "ngon ngu uu tien", "language"]),
    "lifecycle": ("Loại khách (Mới/Hiện hữu)", ["loai khach", "loai kh", "phan loai khach", "phan loai kh", "tinh trang khach", "trang thai khach", "khach moi hien huu", "lifecycle"]),
}
MONTHLY_FIELDS = {
    "ref": ("Mã KH hoặc MST", ["ma kh", "ma khach hang", "mst", "ma so thue", "customer id", "tax code", "id"]),
    "month": ("Tháng (YYYY-MM)", ["thang", "ky", "month", "period", "nam thang"]),
    "inflow_bn": ("Doanh số có (tỷ)", ["doanh so co", "doanh so ve", "inflow", "dong tien ve", "tien ve"]),
    "outflow_bn": ("Doanh số nợ (tỷ)", ["doanh so no", "doanh so chi", "outflow", "dong tien ra", "tien ra"]),
    "trade_usd_m": ("Kim ngạch XNK (triệu USD)", ["kim ngach", "kim ngach xnk", "trade", "xnk"]),
    "avg_balance_bn": ("Số dư BQ (tỷ)", ["so du bq", "so du binh quan", "avg balance", "so du"]),
}
BN_FIELDS = {"annual_revenue_bn", "total_assets_bn", "equity_bn", "casa_balance_bn", "deposit_bn", "loan_outstanding_bn", "credit_limit_bn", "inflow_bn", "outflow_bn", "avg_balance_bn"}
USD_FIELDS = {"export_usd_m", "import_usd_m", "fx_exposure_usd_m", "trade_usd_m"}
NUM_FIELDS = BN_FIELDS | USD_FIELDS | {"employees", "relationship_years", "debt_group"}


def field_defs(target: str):
    return MONTHLY_FIELDS if target == "monthly" else FIELDS


def match_header(h: str, defs) -> tuple[Optional[str], int]:
    k = key_of(h)
    if not k:
        return None, 0
    best, score = None, 0
    for f, (_, syns) in defs.items():
        for s in syns:
            sk = key_of(s)
            if k == sk:
                sc = 100
            elif len(sk) >= 4 and len(k) >= 4 and (sk in k or k in sk):
                sc = 88 - min(abs(len(k) - len(sk)), 10)
            else:
                try:
                    from rapidfuzz import fuzz
                    r = fuzz.ratio(k, sk)
                    sc = int(r) if r >= 88 else 0
                except Exception:  # noqa: BLE001
                    sc = 0
            if sc > score:
                best, score = f, sc
    return (best, score) if score >= 80 else (None, 0)


def auto_mapping(columns: list[str], target: str) -> dict:
    defs = field_defs(target)
    cand = {}
    for col in columns:
        f, sc = match_header(col, defs)
        if f and (f not in cand or sc > cand[f][1]):
            cand[f] = (col, sc)
    return {col: f for f, (col, _) in cand.items()}


# ── đọc file ─────────────────────────────────────────────────────────────────
def _cell(v):
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _dedupe_cols(cols):
    seen, out = {}, []
    for i, c in enumerate(cols):
        c = (c or "").strip() or f"Cột {i + 1}"
        if c in seen:
            seen[c] += 1
            c = f"{c} ({seen[c]})"
        else:
            seen[c] = 1
        out.append(c)
    return out


def _rows_from_matrix(matrix: list[list], target: str) -> tuple[list[str], list[dict]]:
    """Tìm dòng tiêu đề (trong 15 dòng đầu) rồi chuyển thành list[dict]."""
    matrix = [r for r in matrix if any(str(c).strip() for c in r)]
    if not matrix:
        raise ImportError_("File không có dữ liệu")
    defs = field_defs(target)
    best_i, best_hits = 0, -1
    for i, r in enumerate(matrix[:15]):
        hits = sum(1 for c in r if str(c).strip() and match_header(str(c), defs)[0])
        if hits > best_hits:
            best_i, best_hits = i, hits
    if best_hits <= 0:   # không nhận ra cột nào: coi dòng đầu là tiêu đề
        best_i = 0
    cols = _dedupe_cols([str(c) for c in matrix[best_i]])
    rows = []
    for r in matrix[best_i + 1:]:
        d = {cols[j]: (str(r[j]).strip() if j < len(r) else "") for j in range(len(cols))}
        if any(d.values()):
            rows.append(d)
    if len(rows) > MAX_ROWS:
        raise ImportError_(f"File có {len(rows)} dòng, vượt giới hạn {MAX_ROWS} dòng/lần. Hãy tách file.")
    return cols, rows


def parse_excel(data: bytes, target: str, sheet: Optional[str] = None):
    try:
        import openpyxl
    except ImportError:
        raise ImportError_("Thiếu thư viện openpyxl — hãy đóng và mở lại CRM.exe để cài đặt thư viện mới")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        raise ImportError_("Không đọc được file Excel (chỉ hỗ trợ .xlsx/.xlsm; file .xls hãy Lưu thành .xlsx)")
    sheets = wb.sheetnames
    name = sheet if sheet in sheets else None
    if name is None:   # chọn sheet nhiều dữ liệu nhất
        best = (-1, sheets[0])
        for sn in sheets:
            ws = wb[sn]
            n = sum(1 for _ in zip(range(200), ws.iter_rows(values_only=True)))
            if n > best[0] and sn.lower() not in ("hướng dẫn", "huong dan", "readme"):
                best = (n, sn)
        name = best[1]
    ws = wb[name]
    matrix = [[_cell(c) for c in row] for row in ws.iter_rows(values_only=True)]
    cols, rows = _rows_from_matrix(matrix, target)
    return {"method": "excel", "sheets": sheets, "sheet": name, "columns": cols, "rows": rows, "warnings": []}


def parse_csv(data: bytes, target: str):
    text = None
    for enc in ("utf-8-sig", "utf-16", "cp1258", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except Exception:  # noqa: BLE001
            continue
    if text is None:
        raise ImportError_("Không nhận diện được mã hóa file CSV (hãy lưu dạng UTF-8)")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except Exception:  # noqa: BLE001
        dialect = csv.excel
    matrix = list(csv.reader(io.StringIO(text), dialect))
    cols, rows = _rows_from_matrix(matrix, target)
    return {"method": "csv", "sheets": [], "sheet": None, "columns": cols, "rows": rows, "warnings": []}


# ── PDF / ảnh ────────────────────────────────────────────────────────────────
def tesseract_path() -> Optional[str]:
    p = shutil.which("tesseract")
    if p:
        return p
    for cand in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(cand):
            return cand
    return None


def _tess_langs(exe: str) -> str:
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout.split()
    except Exception:  # noqa: BLE001
        return "eng"
    want = [l for l in ("vie", "eng", "chi_sim") if l in out]
    return "+".join(want) or "eng"


def _ocr_image_tsv(exe: str, png: bytes, langs: str) -> list[list[str]]:
    """Tesseract TSV → danh sách dòng, mỗi dòng tách thành các ô theo khoảng trống ngang."""
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "p.png")
        with open(ip, "wb") as f:
            f.write(png)
        res = subprocess.run([exe, ip, "stdout", "-l", langs, "--psm", "6", "tsv"], capture_output=True, timeout=180)
    if res.returncode != 0:
        raise ImportError_("Tesseract OCR lỗi: " + res.stderr.decode(errors="ignore")[:200])
    lines = {}
    for ln in res.stdout.decode("utf-8", errors="ignore").splitlines()[1:]:
        p = ln.split("\t")
        if len(p) < 12 or not p[11].strip():
            continue
        try:
            conf = float(p[10])
        except ValueError:
            continue
        if conf < 20:
            continue
        key = (p[2], p[3], p[4])
        lines.setdefault(key, []).append((int(p[6]), int(p[8]), int(p[9]), p[11].strip()))
    out = []
    ordered = sorted(lines.items(), key=lambda kv: (int(kv[0][0]), int(kv[0][1]), int(kv[0][2])))
    for _, words in ordered:
        words.sort()
        h = max(w[2] for w in words) or 20
        cells, cur, prev_right = [], [], None
        for left, width, height, txt in words:
            if prev_right is not None and left - prev_right > max(28, int(h * 1.6)):
                cells.append(" ".join(cur)); cur = []
            cur.append(txt)
            prev_right = left + width
        cells.append(" ".join(cur))
        out.append(cells)
    return out


def _pdf_page_pngs(doc, dpi=200):
    for page in doc:
        yield page.get_pixmap(dpi=dpi).tobytes("png")


def _lines_to_table(lines: list[list[str]], target: str) -> Optional[tuple[list[str], list[dict]]]:
    defs = field_defs(target)
    for i, cells in enumerate(lines):
        if len(cells) < 3:
            continue
        hits = sum(1 for c in cells if match_header(c, defs)[0])
        if hits < 2:
            continue
        cols = _dedupe_cols(cells)
        rows = []
        for r in lines[i + 1:]:
            if len(r) < max(2, len(cols) - 2):
                if rows:
                    break
                continue
            r = (r + [""] * len(cols))[: len(cols)] if len(r) <= len(cols) else r[: len(cols) - 1] + [" ".join(r[len(cols) - 1:])]
            rows.append(dict(zip(cols, r)))
        if rows:
            return cols, rows
    return None


_KV_LABEL = re.compile(r"^\s*([^:：]{2,60})[:：]\s*(.+?)\s*$")


def _text_to_record(text: str, target: str) -> Optional[tuple[list[str], list[dict]]]:
    """Văn bản dạng 'Nhãn: giá trị' (hồ sơ năng lực / GCN ĐKDN) → 1 bản ghi."""
    defs = FIELDS
    rec = {}
    for ln in text.splitlines():
        m = _KV_LABEL.match(ln)
        if not m:
            continue
        f, sc = match_header(m.group(1), defs)
        if f and f not in rec.values():
            rec[m.group(1).strip()] = m.group(2).strip()
    folded = fold(text)
    if not any(match_header(k, defs)[0] == "tax_code" for k in rec):
        mt = re.search(r"(ma so thue|mst|ma so doanh nghiep|tax code)[^0-9]{0,20}(\d{10}(?:-\d{3})?)", folded)
        if mt:
            rec["Mã số thuế"] = mt.group(2)
    if not any(match_header(k, defs)[0] == "contact_email" for k in rec):
        me = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if me:
            rec["Email"] = me.group(0)
    if not any(match_header(k, defs)[0] == "name" for k in rec):
        mn = re.search(r"((?:CÔNG TY|Công ty)\s+(?:TNHH|CỔ PHẦN|Cổ phần|TNHH MTV)[^\n]{3,90})", text)
        if mn:
            rec["Tên doanh nghiệp"] = mn.group(1).strip()
    known = sum(1 for k in rec if match_header(k, defs)[0])
    if known < 2:
        return None
    return list(rec.keys()), [rec]


def parse_pdf_or_image(data: bytes, target: str, kind: str, ocr: str, allow_cloud: bool, api_key: str):
    """ocr: auto | local | cloud | off."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError:
            raise ImportError_("Thiếu thư viện PyMuPDF — hãy đóng và mở lại CRM.exe để cài đặt thư viện mới")
    warnings = []
    if kind == "image":
        pngs = [data]
        doc = None
        text = ""
    else:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception:  # noqa: BLE001
            raise ImportError_("Không đọc được file PDF (file hỏng hoặc có mật khẩu)")
        if doc.page_count > 30:
            raise ImportError_("PDF quá dài (tối đa 30 trang/lần)")
        text = "\n".join(p.get_text() for p in doc)
        pngs = None
    sparse = len(text.strip()) < 40 * max(1, (doc.page_count if doc else 1))

    # 1) lớp văn bản có sẵn
    if doc is not None and not sparse and ocr != "cloud" and ocr != "local":
        tables = []
        for page in doc:
            try:
                for tb in page.find_tables().tables:
                    m = [[(c or "").replace("\n", " ").strip() for c in r] for r in tb.extract()]
                    if len(m) >= 2 and max(len(r) for r in m) >= 2:
                        tables.append(m)
            except Exception:  # noqa: BLE001
                pass
        if tables:
            matrix = max(tables, key=lambda m: len(m) * len(m[0]))
            try:
                cols, rows = _rows_from_matrix(matrix, target)
                if rows:
                    return {"method": "pdf-table", "sheets": [], "sheet": None, "columns": cols, "rows": rows, "warnings": warnings}
            except ImportError_:
                pass
        lines = [re.split(r"\s{2,}|\t|\|", ln.strip()) for ln in text.splitlines() if ln.strip()]
        t = _lines_to_table([[c for c in l if c] for l in lines], target)
        if t:
            return {"method": "pdf-text", "sheets": [], "sheet": None, "columns": t[0], "rows": t[1], "warnings": warnings}
        r = _text_to_record(text, target)
        if r:
            warnings.append("PDF dạng văn bản: đã trích xuất 1 bản ghi từ các dòng 'Nhãn: giá trị'. Hãy kiểm tra kỹ trước khi nhập.")
            return {"method": "pdf-text", "sheets": [], "sheet": None, "columns": r[0], "rows": r[1], "warnings": warnings}
        if ocr == "off" or ocr == "auto":
            pass  # thử OCR bên dưới (vẫn có thể là bảng không có đường kẻ)

    if ocr == "off":
        raise ImportError_("Không trích xuất được dữ liệu từ lớp văn bản của PDF và OCR đang tắt")

    if pngs is None:
        pngs = list(_pdf_page_pngs(doc))

    # 2) OCR
    exe = tesseract_path()
    use_cloud = ocr == "cloud" or (ocr == "auto" and exe is None)
    if use_cloud and not (allow_cloud and api_key):
        if ocr == "cloud":
            if not allow_cloud:
                raise ImportError_("OCR đám mây (Gemini) chưa được bật. Admin vào Cài đặt → bật 'Cho phép OCR đám mây'")
            raise ImportError_("Chưa cấu hình GEMINI_API_KEY trong backend\\.env")
        raise ImportError_("File là PDF dạng ảnh (scan). Cần một trong hai: (1) Admin bật 'OCR đám mây (Gemini)' trong Cài đặt và có GEMINI_API_KEY; "
                           "(2) cài Tesseract OCR trên máy chạy CRM (gói ngôn ngữ vie, eng, chi_sim)")
    if use_cloud:
        rows = _gemini_extract(data if kind != "image" else pngs[0], "application/pdf" if kind != "image" else "image/png", api_key, target)
        if not rows:
            raise ImportError_("Gemini không trích xuất được bản ghi nào từ file")
        cols = list(dict.fromkeys(k for r in rows for k in r))
        warnings.append("Dữ liệu được trích xuất bằng AI (Gemini) — nội dung file đã được gửi tới dịch vụ đám mây. Hãy kiểm tra kỹ trước khi nhập.")
        return {"method": "ocr-gemini", "sheets": [], "sheet": None, "columns": cols, "rows": rows, "warnings": warnings, "ai_keys": True}

    if exe is None:
        raise ImportError_("Chưa cài Tesseract OCR trên máy này")
    langs = _tess_langs(exe)
    all_lines, ocr_text = [], []
    for png in pngs:
        ls = _ocr_image_tsv(exe, png, langs)
        all_lines.extend(ls)
        ocr_text.extend(" ".join(l) for l in ls)
    t = _lines_to_table(all_lines, target)
    warnings.append(f"Đã OCR cục bộ bằng Tesseract ({langs}). Chữ nhận dạng có thể sai — hãy kiểm tra kỹ trước khi nhập.")
    if t:
        return {"method": "ocr-tesseract", "sheets": [], "sheet": None, "columns": t[0], "rows": t[1], "warnings": warnings}
    r = _text_to_record("\n".join(ocr_text), target)
    if r:
        return {"method": "ocr-tesseract", "sheets": [], "sheet": None, "columns": r[0], "rows": r[1], "warnings": warnings}
    raise ImportError_("OCR xong nhưng không nhận ra bảng dữ liệu hay các dòng 'Nhãn: giá trị'. Hãy dùng file Excel/CSV theo mẫu hoặc ảnh/scan rõ nét hơn")


def _gemini_extract(content: bytes, mime: str, api_key: str, target: str) -> list[dict]:
    from google import genai
    from google.genai import types
    defs = field_defs(target)
    spec = "\n".join(f'- "{k}": {v[0]}' for k, v in defs.items())
    prompt = (
        "Bạn là công cụ trích xuất dữ liệu khách hàng doanh nghiệp từ tài liệu ngân hàng (có thể tiếng Việt, tiếng Trung, tiếng Anh). "
        "Đọc tài liệu và trả về DUY NHẤT một mảng JSON; mỗi phần tử là một doanh nghiệp/dòng dữ liệu với các khóa sau (bỏ khóa nếu tài liệu không có thông tin, KHÔNG bịa):\n"
        f"{spec}\n"
        "Quy ước: số tiền bằng tỷ đồng, ngoại tệ bằng triệu USD, ngày dạng YYYY-MM-DD. Chỉ trả JSON, không giải thích."
    )
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model="gemini-flash-latest",
        contents=[types.Part.from_bytes(data=content, mime_type=mime), prompt],
        config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
    )
    txt = (resp.text or "").strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    data = json.loads(txt)
    if isinstance(data, dict):
        data = data.get("records") or data.get("data") or [data]
    out = []
    for r in data[:MAX_ROWS]:
        if isinstance(r, dict):
            rr = {}
            for k, v in r.items():
                if k in defs and v not in (None, "", []):
                    rr[defs[k][0]] = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
            if rr:
                out.append(rr)
    return out


def parse_any(filename: str, data: bytes, target: str, sheet=None, ocr="auto", allow_cloud=False, api_key=""):
    if len(data) > MAX_BYTES:
        raise ImportError_("File quá lớn (tối đa 20 MB)")
    if not data:
        raise ImportError_("File rỗng")
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".xlsx", ".xlsm"):
        return "xlsx", parse_excel(data, target, sheet)
    if ext == ".xls":
        raise ImportError_("File .xls (Excel cũ) chưa hỗ trợ — mở bằng Excel và Lưu thành .xlsx")
    if ext in (".csv", ".txt"):
        return "csv", parse_csv(data, target)
    if ext == ".pdf":
        return "pdf", parse_pdf_or_image(data, target, "pdf", ocr, allow_cloud, api_key)
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        if ext in (".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(data)).convert("RGB")
                buf = io.BytesIO(); im.save(buf, "PNG"); data = buf.getvalue()
            except Exception:  # noqa: BLE001
                raise ImportError_("Không đọc được file ảnh")
        return "image", parse_pdf_or_image(data, target, "image", ocr, allow_cloud, api_key)
    raise ImportError_("Định dạng chưa hỗ trợ. Dùng .xlsx, .csv, .pdf hoặc ảnh .png/.jpg")


# ── chuẩn hóa giá trị ────────────────────────────────────────────────────────
def to_num(v) -> Optional[float]:
    s = str(v).strip()
    if not s or s in ("-", "—", "N/A", "n/a"):
        return None
    s = re.sub(r"[^\d,.\-+eE]", "", s.replace("\u00a0", ""))
    if not s or s in ("-", "+"):
        return None
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif "." in s and re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def unit_factor(header: str, field: str) -> float:
    h = fold(header)
    if field in BN_FIELDS:
        if re.search(r"nghin ty|ngan ty|thousand b", h):
            return 1000.0
        if "trieu" in h and "usd" not in h:
            return 0.001
        if re.search(r"\(\s*(dong|vnd|vnđ)\s*\)|\bvnd\b", h) and "ty" not in h:
            return 1e-9
    if field in USD_FIELDS:
        if re.search(r"nghin usd|ngan usd|k usd|usd k", h):
            return 0.001
        if re.search(r"\(\s*usd\s*\)", h) and "trieu" not in h and "m" not in re.sub(r"usd", "", h):
            return 1e-6
    return 1.0


def to_date(v) -> Optional[date]:
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    n = to_num(s)
    if n and 20000 < n < 80000:   # số serial Excel
        return (datetime(1899, 12, 30) + timedelta(days=int(n))).date()
    return None


def to_month(v) -> Optional[str]:
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.fullmatch(r"(\d{1,2})[-/](\d{4})", s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    d = to_date(s)
    return d.strftime("%Y-%m") if d else None


COUNTRY_ALIASES = {
    "Trung Quốc": ["trung quoc", "tq", "china", "prc", "中国", "trung hoa"], "Đài Loan": ["dai loan", "taiwan", "台湾", "台灣"],
    "Hàn Quốc": ["han quoc", "korea", "south korea", "韩国", "han"], "Nhật Bản": ["nhat ban", "japan", "日本", "nhat"],
    "Singapore": ["singapore", "sing", "新加坡"], "Hồng Kông": ["hong kong", "hk", "香港"], "Thái Lan": ["thai lan", "thailand"],
    "Mỹ": ["my", "usa", "us", "united states", "hoa ky"], "Malaysia": ["malaysia"], "Ấn Độ": ["an do", "india"], "Đức": ["duc", "germany"],
}
PROVINCE_ALIASES = {
    "TP. Hồ Chí Minh": ["hcm", "tphcm", "tp hcm", "tp ho chi minh", "ho chi minh", "sai gon", "saigon", "hochiminh", "hcmc"],
    "Bình Dương": ["binh duong", "bd"], "Đồng Nai": ["dong nai", "dn"], "Long An": ["long an", "la"], "Bà Rịa – Vũng Tàu": ["ba ria vung tau", "brvt", "vung tau", "ba ria"],
    "Bắc Ninh": ["bac ninh", "bn"], "Hải Phòng": ["hai phong", "hp"], "Hưng Yên": ["hung yen"], "Tây Ninh": ["tay ninh"], "Hà Nội": ["ha noi", "hn", "hanoi"],
    "Đà Nẵng": ["da nang", "danang"],
}
PRODUCT_SYNS = {
    "VAY_VLD": ["vay von luu dong", "von luu dong", "vld", "working capital", "vay vld", "流动资金"], "VAY_DT": ["vay dau tu", "vay du an", "tai tro du an", "project finance", "投资贷款"],
    "LC": ["lc", "l/c", "thu tin dung", "letter of credit", "信用证"], "UPAS": ["upas"], "BAO_LANH": ["bao lanh", "guarantee", "保函"],
    "TTQT": ["ttqt", "thanh toan quoc te", "t/t", "nho thu", "international payment", "国际结算"], "NGOAI_TE": ["ngoai te", "fx", "hedging", "phong ngua ty gia", "外汇"],
    "LUONG": ["luong", "tra luong", "the luong", "payroll", "代发工资"], "DONG_TIEN": ["dong tien", "thu ho", "chi ho", "cash management", "ibanking", "ibanking dn", "现金管理"],
    "TIEN_GUI": ["tien gui", "gui co ky han", "term deposit", "定期存款"],
}


def norm_country(v: str) -> str:
    f = fold(v).strip()
    for name, al in COUNTRY_ALIASES.items():
        if f == fold(name) or f in al or any(a in v for a in al if re.search(r"[\u4e00-\u9fff]", a)):
            return name
    return v.strip().title() if v.strip().islower() else v.strip()


def norm_province(v: str) -> str:
    f = re.sub(r"\s+", " ", re.sub(r"[.\-_]", " ", fold(v))).strip()
    f = re.sub(r"^(tinh|thanh pho|tp)\s+", "", f)
    for name, al in PROVINCE_ALIASES.items():
        if f == fold(name) or f in al:
            return name
    return v.strip()


def norm_industry(v: str) -> str:
    f = fold(v).strip()
    if not f:
        return v
    for name, ip in INDUSTRIES.items():
        if f == fold(name) or f == fold(ip["short"]):
            return name
    for name, ip in INDUSTRIES.items():
        sf = fold(ip["short"])
        if sf in f or fold(name.split("–")[0].strip()) in f:
            return name
    try:
        from rapidfuzz import process, fuzz
        hit = process.extractOne(f, {n: fold(n) for n in INDUSTRIES}, scorer=fuzz.WRatio, score_cutoff=82)
        if hit:
            return hit[2]
    except Exception:  # noqa: BLE001
        pass
    return v.strip()


def norm_products(v: str) -> tuple[list[str], list[str]]:
    found, unknown = [], []
    for tok in re.split(r"[,;\n|+]| và ", str(v)):
        t = tok.strip()
        if not t:
            continue
        if t.upper() in PRODUCTS:
            found.append(t.upper()); continue
        f = fold(t)
        hit = None
        for code, syns in PRODUCT_SYNS.items():
            if any(f == s or (len(s) > 3 and s in f) for s in syns):
                hit = code; break
        (found if hit else unknown).append(hit or t)
    return sorted(set(found)), unknown


def norm_title(v: str) -> Optional[str]:
    f = fold(v)
    if "pho" in f or "副" in v:
        return "PGD"
    if "tai chinh" in f or "cfo" in f or "财务总监" in v:
        return "CFO"
    if "ke toan" in f or "财务经理" in v or "会计" in v or "accountant" in f:
        return "KTT"
    if "giam doc" in f or "director" in f or "gd" == f.strip() or "总经理" in v or "ceo" in f or "tong" in f:
        return "GD"
    return v.strip().upper() if v.strip().upper() in TITLES else None


def norm_lang(v: str) -> Optional[str]:
    f = fold(v).strip()
    if f in ("vi", "vn", "viet", "tieng viet", "vietnamese"):
        return "vi"
    if f in ("zh", "cn", "trung", "tieng trung", "chinese", "mandarin") or "中文" in v:
        return "zh"
    if f in ("en", "anh", "tieng anh", "english"):
        return "en"
    return None


def norm_lifecycle(v: str) -> Optional[str]:
    f = fold(v).strip()
    if f in ("prospect", "new", "moi", "kh moi", "khach moi", "tiem nang", "kh tiem nang", "khach hang moi") or "tiem nang" in f or f.startswith("moi") or "khach moi" in f:
        return "prospect"
    if f in ("existing", "hien huu", "kh hien huu", "khach hien huu", "cu", "kh cu", "khach cu") or "hien huu" in f or "tpbank" in f or "khach cu" in f:
        return "existing"
    return None


def norm_phone(v: str) -> str:
    s = re.sub(r"[^\d+]", "", str(v))
    if s.startswith("+84"):
        s = "0" + s[3:]
    elif s.startswith("84") and len(s) >= 11:
        s = "0" + s[2:]
    elif re.fullmatch(r"[1-9]\d{8}", s):      # Excel làm mất số 0 đầu
        s = "0" + s
    return s


def norm_ownership(v: str, country: Optional[str]) -> str:
    f = fold(v)
    if "fdi" in f or "nuoc ngoai" in f or "foreign" in f or "外资" in v or "100% von nuoc ngoai" in f:
        return "FDI"
    if v.strip() and ("noi dia" in f or "trong nuoc" in f or "domestic" in f or "tu nhan" in f or f.strip() in ("vn", "viet nam")):
        return "Nội địa"
    if country and fold(country) not in ("viet nam", "vn", ""):
        return "FDI"
    return "Nội địa"


def normalize_customer_row(raw: dict, mapping: dict) -> tuple[dict, list[str], list[str]]:
    """raw: {tiêu đề: giá trị}; mapping: {tiêu đề: trường}. Trả về (fields, lỗi, cảnh báo); fields chỉ gồm trường có giá trị."""
    f, errs, warns = {}, [], []
    country_val = None
    for col, field in mapping.items():
        if not field or col not in raw:
            continue
        v = str(raw[col]).strip()
        if v == "":
            continue
        if field in NUM_FIELDS:
            n = to_num(v)
            if n is None:
                errs.append(f"'{col}': không phải số ('{v[:20]}')")
                continue
            n = n * unit_factor(col, field)
            if field in ("employees", "relationship_years", "debt_group"):
                n = int(round(n))
            if field != "equity_bn" and n < 0:
                errs.append(f"'{col}': không được âm")
                continue
            f[field] = round(n, 4) if isinstance(n, float) else n
        elif field == "limit_expiry":
            d = to_date(v)
            if not d:
                errs.append(f"'{col}': ngày không hợp lệ ('{v[:20]}')")
            else:
                f[field] = d
        elif field == "products_held":
            codes, unknown = norm_products(v)
            f[field] = codes
            if unknown:
                warns.append("Sản phẩm không nhận ra (bỏ qua): " + ", ".join(unknown))
        elif field == "tax_code":
            digits = re.sub(r"[^\d-]", "", v.replace(" ", ""))
            f[field] = digits
        elif field == "investor_country":
            f[field] = norm_country(v); country_val = f[field]
        elif field == "province":
            f[field] = norm_province(v)
        elif field == "industry":
            f[field] = norm_industry(v)
        elif field == "contact_phone":
            f[field] = norm_phone(v)
        elif field == "contact_email":
            f[field] = v.lower().replace(" ", "")
        elif field == "contact_title":
            t = norm_title(v)
            if t:
                f[field] = t
            else:
                warns.append(f"Chức danh '{v[:30]}' không nhận ra — bỏ qua")
        elif field == "preferred_language":
            l = norm_lang(v)
            if l:
                f[field] = l
            else:
                warns.append(f"Ngôn ngữ '{v[:20]}' không nhận ra — mặc định tiếng Việt")
        elif field == "lifecycle":
            lc = norm_lifecycle(v)
            if lc:
                f[field] = lc
            else:
                warns.append(f"Loại khách '{v[:20]}' không nhận ra (dùng: Mới / Hiện hữu) — mặc định KH mới")
        elif field == "ownership":
            f[field] = v   # chuẩn hóa sau khi biết quốc gia
        else:
            f[field] = v
    if "lifecycle" not in f and any(f.get(k) for k in ("loan_outstanding_bn", "casa_balance_bn", "deposit_bn", "credit_limit_bn")):
        f["lifecycle"] = "existing"      # có số dư/dư nợ tại TPBank nhưng file không ghi loại khách
    if "ownership" in f or country_val:
        f["ownership"] = norm_ownership(f.get("ownership", ""), country_val)
    if f.get("ownership") == "FDI" and not f.get("investor_country"):
        warns.append("FDI nhưng thiếu quốc gia nhà đầu tư")
    if f.get("credit_limit_bn") and not f.get("limit_expiry"):
        warns.append("Có hạn mức nhưng thiếu ngày hết hạn — không cảnh báo được hạn mức")
    if f.get("loan_outstanding_bn") and not f.get("credit_limit_bn"):
        warns.append("Có dư nợ nhưng thiếu hạn mức tín dụng")
    return f, errs, warns


def normalize_monthly_row(raw: dict, mapping: dict) -> tuple[dict, list[str], list[str]]:
    f, errs = {}, []
    for col, field in mapping.items():
        if not field or col not in raw:
            continue
        v = str(raw[col]).strip()
        if not v:
            continue
        if field == "ref":
            f["ref"] = re.sub(r"\s", "", v)
        elif field == "month":
            m = to_month(v)
            if not m:
                errs.append(f"'{col}': tháng không hợp lệ ('{v[:20]}')")
            else:
                f["month"] = m
        else:
            n = to_num(v)
            if n is None:
                errs.append(f"'{col}': không phải số")
            else:
                f[field] = round(n * unit_factor(col, field), 4)
    if "ref" not in f:
        errs.append("Thiếu mã KH / MST")
    if "month" not in f and not any("tháng" in e for e in errs):
        errs.append("Thiếu tháng")
    return f, errs, []


# ── file mẫu ─────────────────────────────────────────────────────────────────
def build_template(target: str) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dữ liệu"
    if target == "monthly":
        heads = ["Mã KH hoặc MST", "Tháng (YYYY-MM)", "Doanh số có (tỷ đồng)", "Doanh số nợ (tỷ đồng)", "Kim ngạch XNK (triệu USD)", "Số dư BQ (tỷ đồng)"]
        sample = ["DN00001", "2026-10", 42.5, 40.1, 1.8, 6.3]
        notes = ["Mỗi dòng = 1 khách hàng × 1 tháng. Nhập lại cùng tháng sẽ cập nhật số liệu cũ.", "Dùng Mã KH trong hệ thống hoặc Mã số thuế để nhận diện khách hàng."]
    else:
        heads = ["Mã KH", "Tên doanh nghiệp *", "Tên tiếng Trung", "Mã số thuế", "Loại hình (Nội địa/FDI)", "Quốc gia nhà đầu tư", "Ngành nghề", "Tỉnh/Thành phố", "KCN/KCX",
                 "Số lao động", "Doanh thu năm (tỷ đồng)", "Tổng tài sản (tỷ đồng)", "Vốn chủ sở hữu (tỷ đồng)", "Xuất khẩu (triệu USD)", "Nhập khẩu (triệu USD)",
                 "Trạng thái ngoại tệ (triệu USD)", "Số dư CASA BQ (tỷ đồng)", "Tiền gửi có kỳ hạn (tỷ đồng)", "Dư nợ (tỷ đồng)", "Hạn mức tín dụng (tỷ đồng)",
                 "Ngày hết hạn hạn mức", "Nhóm nợ", "Số năm quan hệ", "Sản phẩm đang dùng", "Cán bộ phụ trách", "Người liên hệ", "Tên người LH (Trung)", "Chức danh",
                 "SĐT liên hệ", "Email liên hệ", "Ngôn ngữ ưu tiên", "Loại khách (Mới/Hiện hữu)"]
        sample = ["", "Công ty TNHH Điện tử Hưng Thịnh", "兴盛电子有限公司", "0312345678", "FDI", "Trung Quốc", "Điện tử – Linh kiện", "Bình Dương", "VSIP 1",
                  850, 620.5, 540, 210, 18.5, 12.3, 3.1, 14.2, 5, 120, 150, "2027-03-31", 1, 4, "Vay vốn lưu động, TTQT", "", "Trần Văn An", "陈安", "Kế toán trưởng",
                  "0901234567", "an.tran@example.com", "Tiếng Trung", "Hiện hữu"]
        notes = ["Cột có dấu * là bắt buộc. Để trống 'Mã KH' để hệ thống tự cấp. Trùng Mã số thuế → cập nhật khách hàng cũ (nếu bạn chọn).",
                 "Đơn vị ghi ngay trong tiêu đề cột (tỷ đồng / triệu USD). Có thể đổi thành 'triệu đồng' hoặc 'đồng' — hệ thống tự quy đổi.",
                 "Sản phẩm đang dùng: ngăn cách bằng dấu phẩy (VD: Vay vốn lưu động, L/C, TTQT, Bảo lãnh, Ngoại tệ, Lương, Dòng tiền, Tiền gửi, UPAS, Vay đầu tư).",
                 "Cột 'Cán bộ phụ trách': nhân viên không cần điền (hệ thống tự gán cho chính bạn).",
                 "Cột 'Loại khách': ghi Mới (khách hàng tiềm năng đang theo dõi bán hàng) hoặc Hiện hữu (đã có quan hệ tại TPBank). Để trống = Mới; riêng dòng có số dư/dư nợ/hạn mức tại TPBank thì tự hiểu là Hiện hữu."]
    ws.append(heads)   # sheet dữ liệu chỉ có dòng tiêu đề — ví dụ nằm ở sheet "Hướng dẫn" để không bị nhập nhầm
    fill = PatternFill("solid", fgColor="1F4E79")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 42
    for i, h in enumerate(heads, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(14, min(32, len(h) + 2))
    ws.freeze_panes = "A2"
    g = wb.create_sheet("Hướng dẫn")
    g.column_dimensions["A"].width = 120
    g.append(["HƯỚNG DẪN NHẬP DỮ LIỆU"])
    g["A1"].font = Font(bold=True, size=13)
    for n in notes:
        g.append([n])
        g.cell(row=g.max_row, column=1).alignment = Alignment(wrap_text=True)
    g.append([])
    g.append(["VÍ DỤ MỘT DÒNG (chỉ để tham khảo — KHÔNG nằm trong sheet 'Dữ liệu' nên sẽ không bị nhập)"])
    g.cell(row=g.max_row, column=1).font = Font(bold=True)
    for h, v in zip(heads, sample):
        g.append([f"{h}:  {v}" if v not in ("", None) else f"{h}:  (để trống)"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
