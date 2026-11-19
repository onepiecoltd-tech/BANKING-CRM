"""Phân công khách hàng ↔ cán bộ bán hàng (CBBH) — chỉ Admin.

- GET  /api/corp/admin/assignment : khối lượng từng CBBH, khách chưa phân công, khách gán cho tên chưa có tài khoản.
- POST /api/corp/admin/assign     : gán hàng loạt theo danh sách mã KH hoặc theo bộ lọc (có chế độ xem trước).
"""
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func

from src.database import SessionLocal
from src.accounts.deps import require_admin, client_ip
from src.accounts.service import audit
from .models import CorpCustomer
from .access import rm_accounts, active_rm_names, NO_RM
from .router import _items, apply_filters, FILTER_KEYS

router = APIRouter(prefix="/api/corp/admin", tags=["corporate-assign"])

CHUNK = 400


def _blank():
    return {"total": 0, "prospect": 0, "existing": 0}


@router.get("/assignment")
def assignment(admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        by_rm = defaultdict(_blank)
        for rm, lc, n in db.query(CorpCustomer.rm_name, CorpCustomer.lifecycle, func.count()).group_by(CorpCustomer.rm_name, CorpCustomer.lifecycle):
            key = (rm or "").strip()
            kind = "existing" if lc == "existing" else "prospect"
            by_rm[key]["total"] += n
            by_rm[key][kind] += n
        accounts = rm_accounts(db)
        active = {a["rm_name"] for a in accounts if a["is_active"]}
        inactive = {a["rm_name"]: a["username"] for a in accounts if not a["is_active"]}
        rows = [{**a, **by_rm.get(a["rm_name"], _blank())} for a in accounts]
        known = {a["rm_name"] for a in accounts}
        unmatched = [{"rm_name": k, "inactive_user": inactive.get(k) if k not in active else None, **v}
                     for k, v in sorted(by_rm.items()) if k and k not in active]
        return {
            "total": sum(v["total"] for v in by_rm.values()),
            "accounts": rows,
            "unassigned": by_rm.get("", _blank()),
            "unmatched": unmatched,
            "unmatched_total": sum(u["total"] for u in unmatched),
            "known_names": sorted(known),
        }
    finally:
        db.close()


class AssignIn(BaseModel):
    to_rm: str
    customer_ids: Optional[list[str]] = None
    filters: Optional[dict] = None          # cùng tham số với danh sách KH; rm="__none__" = chưa phân công
    dry_run: bool = False


def resolve_ids(db, admin, body: AssignIn) -> list[str]:
    if body.customer_ids:
        seen, ids = set(), []
        for i in body.customer_ids:
            if i not in seen:
                seen.add(i); ids.append(i)
        return ids
    f = {k: str(v).strip() for k, v in (body.filters or {}).items() if k in FILTER_KEYS and v not in (None, "")}
    if not f:
        raise HTTPException(400, "Chọn danh sách khách hàng hoặc ít nhất một điều kiện lọc")
    return [it["c"]["customer_id"] for it in apply_filters(_items(db, admin), f)]


@router.post("/assign")
def assign(body: AssignIn, request: Request, admin=Depends(require_admin)):
    to = (body.to_rm or "").strip()
    db = SessionLocal()
    try:
        if to not in active_rm_names(db):
            raise HTTPException(400, "Cán bộ nhận phải có tài khoản đang hoạt động (tạo ở Quản trị → Người dùng)")
        ids = resolve_ids(db, admin, body)
        current = {}
        for i in range(0, len(ids), CHUNK):
            for cid, rm in db.query(CorpCustomer.customer_id, CorpCustomer.rm_name).filter(CorpCustomer.customer_id.in_(ids[i:i + CHUNK])):
                current[cid] = (rm or "").strip()
        todo = [c for c, rm in current.items() if rm != to]
        from_counts = defaultdict(int)
        for c in todo:
            from_counts[current[c] or ""] += 1
        summary = {"matched": len(current), "already": len(current) - len(todo), "moved": len(todo),
                   "from": [{"rm_name": k, "count": v} for k, v in sorted(from_counts.items(), key=lambda kv: -kv[1])]}
        if body.dry_run:
            return {**summary, "dry_run": True}
        for i in range(0, len(todo), CHUNK):
            db.query(CorpCustomer).filter(CorpCustomer.customer_id.in_(todo[i:i + CHUNK])).update({CorpCustomer.rm_name: to}, synchronize_session=False)
        db.commit()
        src = ", ".join(f"{(x['rm_name'] or 'chưa phân công')}: {x['count']}" for x in summary["from"][:6])
        audit(admin, "customer.assign", "customer", None, f"{summary['moved']} KH → {to} (từ {src})"[:480], client_ip(request))
        return summary
    finally:
        db.close()
