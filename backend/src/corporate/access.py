"""Phạm vi dữ liệu theo vai trò: Admin thấy tất cả; Nhân viên chỉ thấy khách hàng do mình phụ trách (rm_name)."""
from fastapi import HTTPException
from src.accounts.models import AppUser
from .models import CorpCustomer, CorpSetting

NO_RM = "__none__"      # giá trị lọc: khách hàng chưa phân công cho ai

DEFAULTS = {
    "bank_name": "TPBank",
    "freq_cap_days": 14,
    "max_debt_group_outreach": 2,
    "quiet_start": "20:00",
    "quiet_end": "08:00",
    "import_requires_approval": True,
    "allow_cloud_ocr": False,
    "llm_enabled": True,
}


def get_settings(db) -> dict:
    import os
    out = dict(DEFAULTS)
    env_bank = os.getenv("CORP_BANK_NAME")
    if env_bank:
        out["bank_name"] = env_bank
    for r in db.query(CorpSetting).all():
        if r.key in DEFAULTS and r.value is not None:
            out[r.key] = r.value
    return out


def is_admin(user) -> bool:
    return bool(user and user.role == "admin")


def rm_filter(q, user):
    """Áp bộ lọc theo cán bộ lên query CorpCustomer."""
    if is_admin(user):
        return q
    return q.filter(CorpCustomer.rm_name == user.rm_name)


def visible_ids(db, user):
    """None = tất cả (admin); ngược lại là tập mã KH được phép."""
    if is_admin(user):
        return None
    return {r[0] for r in db.query(CorpCustomer.customer_id).filter(CorpCustomer.rm_name == user.rm_name)}


def get_customer_or_403(db, user, cid) -> CorpCustomer:
    c = db.query(CorpCustomer).filter_by(customer_id=cid).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng")
    if not is_admin(user) and c.rm_name != user.rm_name:
        raise HTTPException(403, "Khách hàng này không thuộc danh mục bạn phụ trách")
    return c


def rm_accounts(db) -> list[dict]:
    """Mọi tài khoản có thể giữ danh mục khách hàng (CBBH); rm_name là tên khớp với corp_customers.rm_name."""
    return [{"username": u.username, "full_name": u.full_name, "role": u.role, "rm_name": (u.rm_name or u.full_name),
             "is_active": bool(u.is_active)} for u in db.query(AppUser).order_by(AppUser.full_name).all()]


def active_rm_names(db) -> set[str]:
    return {a["rm_name"] for a in rm_accounts(db) if a["is_active"]}
