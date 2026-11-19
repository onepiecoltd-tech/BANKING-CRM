"""Tra cứu thông tin doanh nghiệp theo MST từ trang hồ sơ công khai (người đại diện, địa chỉ, tình trạng, SĐT nếu có).

Nguyên tắc (giống Craftbyte Lead Hunter):
  - Chỉ nhận hồ sơ khớp ĐÚNG MST (URL có tiền tố MST và bảng thông tin có dòng "Mã số thuế" = MST). Không khớp → bỏ.
  - Gặp CAPTCHA / bị chặn / quá giới hạn → DỪNG, ghi trạng thái "blocked". Không vượt chặn, không đổi IP, không thử lại dồn dập.
  - Chạy tuần tự, có độ trễ giữa các lượt. Mỗi giá trị lấy được lưu kèm URL nguồn + thời điểm tra.
  - Chỉ điền vào ô còn TRỐNG của hồ sơ khách; không bao giờ ghi đè dữ liệu người dùng đã nhập.
  - Email: trang công khai hầu như không có → không điền.
"""
import random
import re
import threading
import time
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, String, Text

from src.accounts.deps import client_ip, current_user
from src.accounts.service import audit
from src.database import Base, SessionLocal, engine
from .access import get_customer_or_403, is_admin, visible_ids
from .models import CorpCustomer

router = APIRouter(prefix="/api/corp/lookup", tags=["corporate-lookup"])

SOURCES = [("masothue.com", "https://masothue.com/{mst}"), ("tracuumasothue.com", "https://www.tracuumasothue.com/{mst}")]
UA = "Mozilla/5.0 (compatible; BankRM-CRM-Lookup/1.0)"
MST_RE = re.compile(r"^(?:\d{10}(?:-\d{3})?|\d{12})$")
PHONE_RE = re.compile(r"^(?:0\d{9,10}|\+84\d{9,10}|1800\d{4,6}|1900\d{4,6})$")
BLOCK_RE = re.compile(r"unusual traffic|verify you are human|checking your browser|just a moment|captcha|too many requests|"
                      r"access denied|xác minh bạn là con người|quá nhiều yêu cầu", re.I)
DELAY = (3.0, 6.0)          # giây giữa hai lượt tra


class CorpLookup(Base):
    __tablename__ = "corp_lookup"
    customer_id = Column(String, primary_key=True)
    tax_code = Column(String, nullable=False)
    status = Column(String, nullable=False)          # matched | not_found | blocked | error | bad_mst
    representative = Column(String)
    address = Column(String)
    operating_status = Column(String)
    phone = Column(String)
    source_url = Column(String)
    message = Column(Text)
    checked_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine, tables=[CorpLookup.__table__])


# ── phân tích HTML (stdlib, không cần thư viện ngoài) ───────────────────────────
def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _fold(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", _clean(s)).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


class _Tables(HTMLParser):
    """Gom mọi bảng thành danh sách hàng; mỗi ô giữ text + text của thẻ <a> đầu tiên."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._t, self._row, self._cell, self._a, self.h1, self._in_h1 = [], [], None, None, None, "", False

    def handle_starttag(self, tag, attrs):
        if tag == "table": self._t.append([])
        elif tag == "tr" and self._t: self._row = []
        elif tag in ("td", "th") and self._row is not None: self._cell = {"text": [], "a": []}
        elif tag == "a" and self._cell is not None: self._a = []
        elif tag == "h1": self._in_h1 = True
        elif tag in ("br", "p", "div") and self._cell is not None: self._cell["text"].append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append({"text": "".join(self._cell["text"]), "a": self._cell["a"]}); self._cell = None
        elif tag == "tr" and self._row is not None and self._t:
            self._t[-1].append(self._row); self._row = None
        elif tag == "table" and self._t:
            self.tables.append(self._t.pop())
        elif tag == "a" and self._a is not None and self._cell is not None:
            t = _clean("".join(self._a))
            if t: self._cell["a"].append(t)
            self._a = None
        elif tag == "h1": self._in_h1 = False

    def handle_data(self, data):
        if self._cell is not None: self._cell["text"].append(data)
        if self._a is not None: self._a.append(data)
        if self._in_h1: self.h1 += data


def _field(rows, labels):
    want = {_fold(x) for x in labels}
    for r in rows:
        if len(r) >= 2 and re.sub(r"^[^a-z0-9]+", "", _fold(r[0]["text"])) in want:
            return r[1]
    return None


def _first_line(cell):
    if not cell: return ""
    return next((_clean(x) for x in cell["text"].splitlines() if _clean(x)), "")


def _valid_phone(digits: str) -> str:
    # trang che một phần số ("0223 Ẩn số điện thoại") → giữ tiền tố hợp lệ dài nhất
    for n in range(len(digits), 8, -1):
        if PHONE_RE.match(digits[:n]): return digits[:n]
    return ""


def parse_profile(html: str, mst: str) -> Optional[dict]:
    """Trả hồ sơ nếu và chỉ nếu có bảng thông tin với dòng Mã số thuế == mst."""
    p = _Tables(); p.feed(html)
    for rows in p.tables:
        cell = _field(rows, ["Mã số thuế"])
        if not cell or _clean(cell["text"]) != mst:
            continue
        name = re.sub(rf"^{re.escape(mst)}\s*[-–:]\s*", "", _clean(p.h1))
        rep_cell = _field(rows, ["Người đại diện", "Người đại diện pháp luật", "Đại diện pháp luật"])
        rep = _clean(rep_cell["a"][0]) if rep_cell and rep_cell["a"] else _first_line(rep_cell)
        raw_phone = (_field(rows, ["Điện thoại", "Số điện thoại"]) or {"text": ""})["text"]
        phones = []
        for m in re.findall(r"(?:\+84|0)\d(?:[\s().-]*\d){8,10}|(?:1800|1900)(?:[\s.-]*\d){4,6}", raw_phone):
            v = _valid_phone(re.sub(r"[\s().-]", "", m))
            if v and v not in phones: phones.append(v)
        return {"name": name, "representative": rep, "phone": "; ".join(phones),
                "address": _clean((_field(rows, ["Địa chỉ"]) or _field(rows, ["Địa chỉ thuế"]) or {"text": ""})["text"]),
                "operating_status": _clean((_field(rows, ["Tình trạng", "Tình trạng hoạt động"]) or {"text": ""})["text"])}
    return None


# ── tra một MST ────────────────────────────────────────────────────────────────
def lookup_mst(mst: str, session=None) -> dict:
    mst = _clean(mst)
    if not MST_RE.match(mst):
        return {"status": "bad_mst", "message": "MST không hợp lệ (cần 10 hoặc 13 số, hoặc 12 số CCCD)."}
    s = session or requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "vi,en;q=0.5"})
    last = "Không có nguồn nào trả hồ sơ khớp MST."
    for host, tpl in SOURCES:
        try:
            r = s.get(tpl.format(mst=mst), timeout=20, allow_redirects=True)
        except requests.RequestException as e:
            last = f"Lỗi kết nối {host}: {e.__class__.__name__}"; continue
        if r.status_code in (403, 429, 503) or (r.status_code == 200 and len(r.text) < 3000 and BLOCK_RE.search(r.text)) \
                or "/cdn-cgi/" in r.url or re.search(r'id="challenge-|g-recaptcha|hcaptcha', r.text[:60000]):
            return {"status": "blocked", "message": f"{host} yêu cầu xác minh/giới hạn truy cập (HTTP {r.status_code}). Đã dừng; hãy thử lại sau."}
        if r.status_code == 404:
            last = f"{host}: không có hồ sơ MST này."; continue
        from urllib.parse import urlparse
        path = urlparse(r.url).path
        if not re.match(rf"^/{re.escape(mst)}-[a-z0-9-]+/?$", path, re.I):
            last = f"{host}: trang trả về không phải hồ sơ của MST {mst} (bỏ qua để tránh ghi nhầm)."; continue
        prof = parse_profile(r.text, mst)
        if prof:
            prof.update(status="matched", source_url=r.url.split("?")[0], message="Khớp MST")
            return prof
        last = f"{host}: không đọc được bảng thông tin (cấu trúc trang có thể đã đổi)."
    return {"status": "not_found", "message": last}


def apply_to_customer(db, c: CorpCustomer, res: dict) -> list[str]:
    """Điền vào ô trống của hồ sơ khách; trả danh sách trường đã điền."""
    filled = []
    if res.get("status") != "matched":
        return filled
    if res.get("representative") and not c.contact_name:
        c.contact_name = res["representative"][:160]; filled.append("contact_name")
        if not c.contact_title:
            c.contact_title = "GD"; filled.append("contact_title")
    if res.get("phone") and not c.contact_phone:
        c.contact_phone = res["phone"].split(";")[0].strip(); filled.append("contact_phone")
    return filled


def run_one(db, c: CorpCustomer, session=None) -> dict:
    res = lookup_mst(c.tax_code or "", session)
    row = db.get(CorpLookup, c.customer_id) or CorpLookup(customer_id=c.customer_id, tax_code=c.tax_code or "")
    row.tax_code = c.tax_code or ""; row.status = res["status"]; row.message = res.get("message")
    row.checked_at = datetime.utcnow()
    if res["status"] == "matched":
        row.representative, row.address = res.get("representative"), res.get("address")
        row.operating_status, row.phone, row.source_url = res.get("operating_status"), res.get("phone"), res.get("source_url")
    db.merge(row)
    res["filled"] = apply_to_customer(db, c, res)
    db.commit()
    return res


def _row_dict(r: CorpLookup):
    return {"customer_id": r.customer_id, "tax_code": r.tax_code, "status": r.status, "message": r.message,
            "representative": r.representative, "address": r.address, "operating_status": r.operating_status,
            "phone": r.phone, "source_url": r.source_url, "checked_at": r.checked_at.isoformat() if r.checked_at else None}


# ── API ────────────────────────────────────────────────────────────────────────
@router.get("/{cid}")
def last_result(cid: str, user=Depends(current_user)):
    db = SessionLocal()
    try:
        get_customer_or_403(db, user, cid)
        r = db.get(CorpLookup, cid)
        return _row_dict(r) if r else {"status": "none"}
    finally:
        db.close()


@router.post("/{cid}")
def lookup_one(cid: str, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        c = get_customer_or_403(db, user, cid)
        res = run_one(db, c)
        audit(user, "customer.lookup", "customer", cid, f"{res['status']} {','.join(res.get('filled', []))}"[:300], client_ip(request))
        return {**res, "customer_id": cid}
    finally:
        db.close()


# tra hàng loạt: 1 tiến trình nền, tuần tự, dừng ngay khi bị chặn
JOB = {"running": False, "total": 0, "done": 0, "matched": 0, "not_found": 0, "filled": 0, "state": "idle", "message": "", "stop": False}
_lock = threading.Lock()


class BatchIn(BaseModel):
    ids: Optional[list[str]] = None      # bỏ trống = mọi khách có MST trong phạm vi quyền
    only_missing: bool = True            # chỉ khách thiếu người liên hệ hoặc SĐT, và chưa tra thành công
    limit: int = 200


def _batch_worker(ids: list[str]):
    s = requests.Session()
    try:
        for cid in ids:
            if JOB["stop"]:
                JOB.update(state="stopped", message="Đã dừng theo yêu cầu."); break
            db = SessionLocal()
            try:
                c = db.query(CorpCustomer).filter_by(customer_id=cid).first()
                if not c:
                    continue
                res = run_one(db, c, s)
            finally:
                db.close()
            JOB["done"] += 1
            if res["status"] == "blocked":
                JOB.update(state="blocked", message=res["message"]); break
            if res["status"] == "matched":
                JOB["matched"] += 1; JOB["filled"] += len(res.get("filled", []))
            else:
                JOB["not_found"] += 1
            time.sleep(random.uniform(*DELAY))
        else:
            JOB.update(state="done", message="Hoàn tất.")
    except Exception as e:  # noqa: BLE001
        JOB.update(state="error", message=f"{e.__class__.__name__}: {e}")
    finally:
        JOB["running"] = False


@router.post("/batch/start")
def batch_start(body: BatchIn, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        q = db.query(CorpCustomer).filter(CorpCustomer.tax_code.isnot(None), CorpCustomer.tax_code != "")
        vis = visible_ids(db, user)
        if vis is not None:
            q = q.filter(CorpCustomer.customer_id.in_(vis))
        if body.ids:
            q = q.filter(CorpCustomer.customer_id.in_(body.ids))
        if body.only_missing:
            done = {r[0] for r in db.query(CorpLookup.customer_id).filter(CorpLookup.status == "matched")}
            rows = [c for c in q if (not c.contact_name or not c.contact_phone) and c.customer_id not in done]
        else:
            rows = list(q)
        rows = [c for c in rows if MST_RE.match((c.tax_code or "").strip())][: max(1, min(body.limit, 500))]
        ids = [c.customer_id for c in rows]
    finally:
        db.close()
    if not ids:
        raise HTTPException(400, "Không có khách hàng nào cần tra (cần có MST hợp lệ và còn thiếu người liên hệ/SĐT).")
    with _lock:
        if JOB["running"]:
            raise HTTPException(409, "Đang có một lượt tra hàng loạt chạy. Chờ hoàn tất hoặc dừng trước.")
        JOB.update(running=True, total=len(ids), done=0, matched=0, not_found=0, filled=0, state="running", message="", stop=False)
    audit(user, "customer.lookup_batch", "customer", "-", f"{len(ids)} khách", client_ip(request))
    threading.Thread(target=_batch_worker, args=(ids,), daemon=True).start()
    return dict(JOB)


@router.get("/batch/status")
def batch_status(user=Depends(current_user)):
    return dict(JOB)


@router.post("/batch/stop")
def batch_stop(user=Depends(current_user)):
    JOB["stop"] = True
    return dict(JOB)
