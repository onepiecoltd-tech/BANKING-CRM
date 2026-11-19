"""Cài đặt DN (Admin chỉnh), thông tin hệ thống, xóa dữ liệu mẫu."""
import os
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

from src.config import settings as app_settings
from src.database import SessionLocal
from src.accounts.deps import current_user, require_admin, client_ip
from src.accounts.service import audit
from .models import CorpSetting, CorpCustomer, CorpCampaign, CorpCampaignTarget
from .access import get_settings, DEFAULTS, is_admin
from .crud import purge_customers
from src import backup as _backup

router = APIRouter(prefix="/api/corp", tags=["corporate-settings"])


def system_info(db) -> dict:
    return {
        "llm_backend": app_settings.llm_backend,
        "has_gemini_key": bool(app_settings.gemini_api_key),
        "sender_backend": app_settings.sender_backend,
        "ocr_local": _tesseract() is not None,
        "database": os.path.basename(app_settings.database_url.replace("sqlite:///", "")),
        "corp_customers": db.query(CorpCustomer).count(),
        "demo_customers": db.query(CorpCustomer).filter(CorpCustomer.customer_id.op("GLOB")("CORP[0-9][0-9][0-9][0-9]")).count(),
        "backup": _backup.latest_backup(),
        "backup_auto": bool(_backup.backup_dir() and _backup.sqlite_path()),
    }


def _tesseract():
    import shutil
    p = shutil.which("tesseract")
    if p:
        return p
    for cand in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(cand):
            return cand
    return None


@router.get("/settings")
def get_corp_settings(user=Depends(current_user)):
    db = SessionLocal()
    try:
        out = {"settings": get_settings(db)}
        if is_admin(user):
            out["system"] = system_info(db)
        else:
            out["settings"] = {k: v for k, v in out["settings"].items() if k in ("bank_name", "import_requires_approval", "allow_cloud_ocr", "freq_cap_days")}
            out["system"] = {"ocr_local": _tesseract() is not None, "has_gemini_key": bool(app_settings.gemini_api_key)}
        return out
    finally:
        db.close()


def _validate(key: str, v: Any):
    t = type(DEFAULTS[key])
    if t is bool:
        if not isinstance(v, bool):
            raise HTTPException(400, f"{key}: cần giá trị đúng/sai")
    elif t is int:
        if not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 365:
            raise HTTPException(400, f"{key}: cần số nguyên 0–365")
    else:
        if not isinstance(v, str) or not v.strip():
            raise HTTPException(400, f"{key}: không được để trống")
        if key in ("quiet_start", "quiet_end") and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise HTTPException(400, f"{key}: định dạng HH:MM")
        v = v.strip()[:80]
    if key == "max_debt_group_outreach" and not (1 <= v <= 5):
        raise HTTPException(400, "Ngưỡng nhóm nợ từ 1 đến 5")
    return v


@router.put("/settings")
def put_corp_settings(body: dict, request: Request, admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        changed = {}
        for k, v in body.items():
            if k not in DEFAULTS:
                raise HTTPException(400, f"Không có cài đặt '{k}'")
            v = _validate(k, v)
            row = db.query(CorpSetting).filter_by(key=k).first()
            if not row:
                row = CorpSetting(key=k); db.add(row)
            row.value = v; row.updated_by = admin.username; row.updated_at = datetime.utcnow()
            changed[k] = v
        db.commit()
        audit(admin, "settings.update", "settings", None, changed, client_ip(request))
        return {"settings": get_settings(db)}
    finally:
        db.close()


@router.get("/admin/backup")
def download_backup(request: Request, admin=Depends(require_admin)):
    """Tạo bản sao lưu CSDL ngay lúc này và trả về để Admin tải về máy (cất ở nơi an toàn, ngoài máy chủ)."""
    import tempfile
    if not _backup.sqlite_path():
        raise HTTPException(400, "Chỉ hỗ trợ tải sao lưu khi dùng SQLite")
    tmpdir = tempfile.mkdtemp(prefix="crm-bk-")
    try:
        path = _backup.make_backup(tmpdir)
    except Exception as e:  # noqa: BLE001
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(500, f"Không tạo được bản sao lưu: {e}")
    audit(admin, "backup.download", "database", None, os.path.basename(path), client_ip(request))

    def _cleanup():
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    return FileResponse(path, media_type="application/octet-stream", filename=os.path.basename(path),
                        background=BackgroundTask(_cleanup))


@router.post("/admin/clear-demo")
def clear_demo(request: Request, admin=Depends(require_admin)):
    """Xóa toàn bộ khách hàng mô phỏng (mã CORPxxxx) và dữ liệu liên quan, trước khi dùng dữ liệu thật."""
    db = SessionLocal()
    try:
        ids = [r[0] for r in db.query(CorpCustomer.customer_id).filter(CorpCustomer.customer_id.op("GLOB")("CORP[0-9][0-9][0-9][0-9]"))]
        marker = db.query(CorpSetting).filter_by(key="_demo_cleared").first()
        if not marker:
            db.add(CorpSetting(key="_demo_cleared", value=True, updated_by=admin.username))
        if not ids:
            db.commit()
            return {"deleted": 0}
        purge_customers(db, ids)
        # chiến dịch không còn mục tiêu nào
        live = {r[0] for r in db.query(CorpCampaignTarget.campaign_id).distinct()}
        for cp in db.query(CorpCampaign).all():
            if cp.id not in live:
                db.delete(cp)
        db.commit()
        audit(admin, "demo.clear", "customer", None, f"{len(ids)} KH mô phỏng", client_ip(request))
        return {"deleted": len(ids)}
    finally:
        db.close()
