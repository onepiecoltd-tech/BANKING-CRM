"""Sao lưu SQLite: tự động hằng ngày (luồng nền) + tạo bản sao tức thời để Admin tải về.

Bật bằng biến môi trường:
  CRM_BACKUP_DIR        thư mục lưu (bản Docker đặt /data/backups). Không đặt = tắt sao lưu tự động.
  CRM_BACKUP_KEEP_DAYS  số ngày giữ bản sao (mặc định 14).
Chỉ hỗ trợ SQLite; với CSDL khác hãy dùng công cụ sao lưu của chính CSDL đó.
"""
import glob
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.engine import make_url

from src.config import settings

PREFIX = "banking_crm-"


def sqlite_path() -> Optional[str]:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    return os.path.abspath(url.database)


def backup_dir() -> Optional[str]:
    d = os.getenv("CRM_BACKUP_DIR", "").strip()
    return os.path.abspath(d) if d else None


def make_backup(dest_dir: str, keep_days: Optional[int] = None) -> str:
    """Sao lưu nhất quán (an toàn khi đang ghi) bằng backup API của SQLite. Trả về đường dẫn file."""
    src_path = sqlite_path()
    if not src_path:
        raise RuntimeError("Chỉ hỗ trợ sao lưu SQLite")
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, f"{PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
    tmp = out + ".part"
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True, timeout=30)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    os.replace(tmp, out)
    if keep_days is not None:
        prune(dest_dir, keep_days)
    return out


def prune(dest_dir: str, keep_days: int) -> int:
    cutoff = time.time() - keep_days * 86400
    n = 0
    for f in glob.glob(os.path.join(dest_dir, PREFIX + "*.db")):
        try:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
                n += 1
        except OSError:
            pass
    return n


def latest_backup(dest_dir: Optional[str] = None) -> Optional[dict]:
    d = dest_dir or backup_dir()
    if not d:
        return None
    files = sorted(glob.glob(os.path.join(d, PREFIX + "*.db")), key=os.path.getmtime)
    if not files:
        return None
    f = files[-1]
    return {"file": os.path.basename(f), "bytes": os.path.getsize(f),
            "at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"), "count": len(files)}


def _loop(d: str, keep: int):
    while True:
        try:
            last = latest_backup(d)
            if not last or time.time() - datetime.fromisoformat(last["at"]).timestamp() > 23 * 3600:
                p = make_backup(d, keep)
                print("backup ok:", p, flush=True)
        except Exception as e:  # noqa: BLE001 — sao lưu lỗi không được làm sập API
            print("backup failed:", e, flush=True)
        time.sleep(3600)


def start_scheduler() -> bool:
    d = backup_dir()
    if not d or not sqlite_path():
        return False
    keep = int(os.getenv("CRM_BACKUP_KEEP_DAYS", "14") or 14)
    threading.Thread(target=_loop, args=(d, keep), daemon=True, name="crm-backup").start()
    return True
