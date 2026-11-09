"""Dọn dữ liệu mô phỏng & dữ liệu rác (chỉ Admin).

Ba nhóm, chọn độc lập:
  retail     toàn bộ dữ liệu khách hàng cá nhân mô phỏng (customers + giao dịch, tương tác, định danh, đồng ý,
             danh sách chặn, phiên, lịch chăm sóc, nhật ký gửi). Giữ lại bảng danh mục sản phẩm.
  corp_demo  khách hàng DN mẫu (mã CORPxxxx) + dòng tiền, cơ hội, ghi chú tương tác, hội thoại, chiến dịch mẫu.
  junk       dòng mồ côi (không còn khách hàng), ghi chú trống, nhật ký chạy AI bị lỗi, chiến dịch rỗng.

Luôn: xem trước số dòng (dry-run) → sao lưu SQLite tự động → xóa trong 1 giao dịch → đặt cờ `_demo_cleared`
để lần khởi động sau không nạp lại dữ liệu mẫu. Không bao giờ đụng khách hàng DN thật (mã khác CORPxxxx).

Dùng qua giao diện (Cài đặt → Dọn dữ liệu) hoặc dòng lệnh:
  python -m src.corporate.cleanup                      # chỉ xem trước
  python -m src.corporate.cleanup --retail --corp-demo --junk --yes
"""
import os
import sys
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import and_, func, not_, or_, select

from src import backup as _backup
from src.accounts.deps import client_ip, require_admin
from src.accounts.service import audit
from src.database import (engine, AuditLog, CadenceJob, Consent, Customer, IdentityGraph, Interaction,
                          Session as RetailSession, SessionLocal, Suppression, Transaction)
from .models import (CorpAgentRun, CorpCampaign, CorpCampaignTarget, CorpCustomer, CorpInteraction, CorpMessage,
                     CorpMonthly, CorpOpportunity, CorpOptOut, CorpSetting)

router = APIRouter(prefix="/api/corp/admin", tags=["corporate-cleanup"])

DEMO_GLOB = "CORP[0-9][0-9][0-9][0-9]"
CONFIRM_WORD = "XOA"

# bảng con của khách hàng cá nhân (xóa trước bảng Customer)
RETAIL_CHILDREN = [("transactions", Transaction), ("interactions", Interaction), ("consents", Consent),
                   ("suppressions", Suppression), ("identity_graph", IdentityGraph), ("sessions", RetailSession),
                   ("cadence_jobs", CadenceJob), ("audit_logs", AuditLog)]
_RETAIL_KEY = {"transactions": "customer_id", "interactions": "customer_id", "consents": "canonical_id",
               "suppressions": "canonical_id", "identity_graph": "canonical_id", "sessions": "canonical_id",
               "cadence_jobs": "canonical_id", "audit_logs": "customer_id"}
CORP_CHILDREN = [("monthly", CorpMonthly), ("interactions", CorpInteraction), ("opportunities", CorpOpportunity),
                 ("messages", CorpMessage), ("targets", CorpCampaignTarget), ("optout", CorpOptOut)]


def _demo_ids(db) -> list[str]:
    return [r[0] for r in db.query(CorpCustomer.customer_id).filter(CorpCustomer.customer_id.op("GLOB")(DEMO_GLOB))]


def _orphan_filter(model, parent_ids):
    return and_(model.customer_id.isnot(None), not_(model.customer_id.in_(parent_ids)))


_CORP_LIVE = select(CorpCustomer.customer_id)
_RETAIL_LIVE = select(Customer.customer_id)


def _demo_campaign_ids(db, demo_ids: list[str]) -> list[int]:
    """Chiến dịch của hệ thống mẫu + chiến dịch chỉ nhắm vào KH mẫu (sẽ rỗng sau khi xóa KH mẫu)."""
    owned = {r[0] for r in db.query(CorpCampaign.id).filter(or_(CorpCampaign.owner == "demo", CorpCampaign.owner_rm == "Hệ thống (mẫu)"))}
    demo_set = set(demo_ids)
    with_demo, with_real = set(), set()
    for cid, cust in db.query(CorpCampaignTarget.campaign_id, CorpCampaignTarget.customer_id):
        (with_demo if cust in demo_set else with_real).add(cid)
    return sorted(owned | (with_demo - with_real))


def plan(db) -> dict:
    """Đếm số dòng sẽ bị xóa theo từng nhóm (không thay đổi gì)."""
    n = lambda q: q.scalar() or 0  # noqa: E731
    retail = {"customers": n(db.query(func.count(Customer.customer_id)))}
    for name, m in RETAIL_CHILDREN:
        retail[name] = n(db.query(func.count()).select_from(m))
    retail["total"] = sum(retail.values())

    ids = _demo_ids(db)
    demo = {"customers": len(ids)}
    for name, m in CORP_CHILDREN:
        demo[name] = n(db.query(func.count()).select_from(m).filter(m.customer_id.in_(ids))) if ids else 0
    demo["campaigns"] = len(_demo_campaign_ids(db, ids))
    demo["total"] = sum(demo.values())

    junk = junk_counts(db)
    junk["total"] = sum(junk.values())
    real = n(db.query(func.count(CorpCustomer.customer_id)).filter(not_(CorpCustomer.customer_id.op("GLOB")(DEMO_GLOB))))
    return {"retail": retail, "corp_demo": demo, "junk": junk, "real_corp_customers": real}


def junk_counts(db) -> dict:
    """Rác thật sự (không trùng với nhóm mẫu): dòng mồ côi, ghi chú trống, log AI lỗi, chiến dịch rỗng."""
    n = lambda q: q.scalar() or 0  # noqa: E731
    orphans = sum(n(db.query(func.count()).select_from(m).filter(_orphan_filter(m, _CORP_LIVE))) for _, m in CORP_CHILDREN)
    for name, m in RETAIL_CHILDREN:
        col = getattr(m, _RETAIL_KEY[name])
        orphans += n(db.query(func.count()).select_from(m).filter(col.isnot(None), not_(col.in_(_RETAIL_LIVE))))
    return {"orphans": orphans, "blank_notes": n(db.query(func.count(CorpInteraction.id)).filter(_BLANK_NOTE)),
            "failed_ai_runs": n(db.query(func.count(CorpAgentRun.id)).filter(_FAILED_RUN)),
            "empty_campaigns": len(_empty_campaign_ids(db))}


_BLANK_NOTE = and_(or_(CorpInteraction.summary.is_(None), func.trim(CorpInteraction.summary) == ""),
                   or_(CorpInteraction.outcome.is_(None), func.trim(CorpInteraction.outcome) == ""))
_FAILED_RUN = and_(CorpAgentRun.llm_error.isnot(None), CorpAgentRun.llm_error != "")


def _empty_campaign_ids(db) -> list[int]:
    used = {r[0] for r in db.query(CorpCampaignTarget.campaign_id).distinct()}
    used |= {r[0] for r in db.query(CorpMessage.campaign_id).filter(CorpMessage.campaign_id.isnot(None)).distinct()}
    return [cid for cid, in db.query(CorpCampaign.id) if cid not in used]


def _delete_retail(db) -> dict:
    out = {}
    for name, m in RETAIL_CHILDREN:
        out[name] = db.query(m).delete(synchronize_session=False)
    out["customers"] = db.query(Customer).delete(synchronize_session=False)
    return out


def _delete_corp_demo(db) -> dict:
    ids = _demo_ids(db)
    demo_cp = _demo_campaign_ids(db, ids)               # xác định trước khi xóa mục tiêu
    out = {"customers": len(ids)}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        for name, m in CORP_CHILDREN:
            out[name] = out.get(name, 0) + db.query(m).filter(m.customer_id.in_(chunk)).delete(synchronize_session=False)
        db.query(CorpCustomer).filter(CorpCustomer.customer_id.in_(chunk)).delete(synchronize_session=False)
    out["messages"] = out.get("messages", 0) + db.query(CorpMessage).filter(CorpMessage.created_by == "demo").delete(synchronize_session=False)
    if demo_cp:
        out["targets"] = out.get("targets", 0) + db.query(CorpCampaignTarget).filter(CorpCampaignTarget.campaign_id.in_(demo_cp)).delete(synchronize_session=False)
        out["campaigns"] = db.query(CorpCampaign).filter(CorpCampaign.id.in_(demo_cp)).delete(synchronize_session=False)
    return out


def _delete_junk(db) -> dict:
    out = {"orphans": 0}
    for _, m in CORP_CHILDREN:
        out["orphans"] += db.query(m).filter(_orphan_filter(m, _CORP_LIVE)).delete(synchronize_session=False)
    for name, m in RETAIL_CHILDREN:
        col = getattr(m, _RETAIL_KEY[name])
        out["orphans"] += db.query(m).filter(col.isnot(None), not_(col.in_(_RETAIL_LIVE))).delete(synchronize_session=False)
    out["blank_notes"] = db.query(CorpInteraction).filter(_BLANK_NOTE).delete(synchronize_session=False)
    out["failed_ai_runs"] = db.query(CorpAgentRun).filter(_FAILED_RUN).delete(synchronize_session=False)
    empty = _empty_campaign_ids(db)
    out["empty_campaigns"] = db.query(CorpCampaign).filter(CorpCampaign.id.in_(empty)).delete(synchronize_session=False) if empty else 0
    return out


def run_cleanup(db, retail: bool, corp_demo: bool, junk: bool, backup_to: str | None = None) -> dict:
    """Thực hiện dọn. Trả về số dòng đã xóa theo nhóm + tên file sao lưu. Ném RuntimeError nếu không sao lưu được."""
    if not (retail or corp_demo or junk):
        raise ValueError("Chưa chọn nhóm dữ liệu nào")
    if not _backup.sqlite_path():
        raise RuntimeError("Chỉ hỗ trợ dọn khi dùng SQLite (cần sao lưu tự động trước khi xóa)")
    dest = backup_to or _backup.backup_dir() or os.path.join(tempfile.gettempdir(), "crm-cleanup-backup")
    bk = _backup.make_backup(dest)                       # sao lưu trước, lỗi thì dừng — chưa xóa gì
    res: dict = {"backup": os.path.basename(bk), "backup_path": bk}
    try:
        if retail:
            res["retail"] = _delete_retail(db)
        if corp_demo:
            res["corp_demo"] = _delete_corp_demo(db)
        if junk:
            res["junk"] = _delete_junk(db)             # chạy sau cùng để quét cả phần mồ côi do các bước trên để lại
        if retail or corp_demo:
            if not db.query(CorpSetting).filter_by(key="_demo_cleared").first():
                db.add(CorpSetting(key="_demo_cleared", value=True, updated_by="cleanup", updated_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
        raise
    res["vacuumed"] = _vacuum()
    return res


def _vacuum() -> bool:
    """Thu nhỏ file CSDL sau khi xóa nhiều dòng (best-effort: bỏ qua nếu đang có giao dịch khác)."""
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql("VACUUM")
        return True
    except Exception:  # noqa: BLE001
        return False


class CleanupIn(BaseModel):
    retail: bool = False
    corp_demo: bool = False
    junk: bool = False
    confirm: str = ""


@router.get("/cleanup")
def cleanup_plan(admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        p = plan(db)
        p["backup_ok"] = bool(_backup.sqlite_path())
        return p
    finally:
        db.close()


@router.post("/cleanup")
def cleanup_run(body: CleanupIn, request: Request, admin=Depends(require_admin)):
    if body.confirm.strip().upper() != CONFIRM_WORD:
        raise HTTPException(400, f"Gõ {CONFIRM_WORD} để xác nhận")
    if not (body.retail or body.corp_demo or body.junk):
        raise HTTPException(400, "Chọn ít nhất một nhóm dữ liệu")
    db = SessionLocal()
    try:
        try:
            res = run_cleanup(db, body.retail, body.corp_demo, body.junk)
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        total = sum(sum(v.values()) for k, v in res.items() if isinstance(v, dict))
        picked = ",".join(k for k, v in (("retail", body.retail), ("corp_demo", body.corp_demo), ("junk", body.junk)) if v)
        audit(admin, "data.cleanup", "database", None, f"{picked}: {total} dòng; sao lưu {res['backup']}", client_ip(request))
        res.pop("backup_path", None)
        res["deleted_total"] = total
        res["plan"] = plan(db)
        return res
    finally:
        db.close()


def _cli(argv: list[str]) -> int:
    want = {"retail": "--retail" in argv, "corp_demo": "--corp-demo" in argv, "junk": "--junk" in argv}
    db = SessionLocal()
    try:
        p = plan(db)
        print("Sẽ xóa (xem trước):")
        for k, v in p.items():
            print(f"  {k}: {v}")
        if "--yes" not in argv or not any(want.values()):
            print("\nChưa xóa gì. Thêm --retail/--corp-demo/--junk và --yes để thực hiện (tự sao lưu trước).")
            return 0
        res = run_cleanup(db, **want)
        print("\nĐã xóa:", {k: v for k, v in res.items() if k != "backup_path"})
        print("Sao lưu:", res["backup_path"])
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
