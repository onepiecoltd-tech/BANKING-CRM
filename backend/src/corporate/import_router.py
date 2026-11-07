"""API import dữ liệu: tải file → xem trước/kiểm tra → nhập (hoặc gửi chờ Admin duyệt)."""
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from src.config import settings as app_settings
from src.database import SessionLocal
from src.accounts.deps import current_user, require_admin, client_ip
from src.accounts.service import audit
from .models import CorpCustomer, CorpMonthly, CorpImportBatch, customer_dict
from .access import get_settings, is_admin
from . import importer as I
from .crud import CustomerIn, validate_customer, normalize_input, next_id, segment_for

router = APIRouter(prefix="/api/corp/import", tags=["corporate-import"])

MAX_PREVIEW = 30


def _batch_row(b: CorpImportBatch, full=False):
    d = {"id": b.id, "filename": b.filename, "kind": b.kind, "method": b.method, "target": b.target, "status": b.status,
         "created_by": b.created_by, "created_rm": b.created_rm, "created_at": b.created_at.isoformat() + "Z",
         "reviewed_by": b.reviewed_by, "reviewed_at": b.reviewed_at.isoformat() + "Z" if b.reviewed_at else None,
         "summary": b.summary or {}, "note": b.note, "row_count": len(b.rows or [])}
    if full:
        d["columns"], d["mapping"] = b.columns, b.mapping
    return d


def _own(db, user, bid) -> CorpImportBatch:
    b = db.query(CorpImportBatch).filter_by(id=bid).first()
    if not b or (not is_admin(user) and b.created_by != user.username):
        raise HTTPException(404, "Không tìm thấy lô import")
    return b


@router.get("/template")
def template(target: str = "customers", user=Depends(current_user)):
    if target not in ("customers", "monthly"):
        raise HTTPException(400, "target không hợp lệ")
    try:
        data = I.build_template(target)
    except ImportError:
        raise HTTPException(500, "Thiếu thư viện openpyxl — đóng và mở lại CRM.exe để cài")
    name = "mau_import_khach_hang_dn.xlsx" if target == "customers" else "mau_import_dong_tien_thang.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/upload")
async def upload(request: Request, filename: str, target: str = "customers", ocr: str = "auto", sheet: Optional[str] = None,
                 user=Depends(current_user)):
    """Thân request = nội dung file thô (không dùng multipart để khỏi cần thư viện bổ sung)."""
    if target not in ("customers", "monthly"):
        raise HTTPException(400, "target không hợp lệ")
    if ocr not in ("auto", "local", "cloud", "off"):
        raise HTTPException(400, "ocr không hợp lệ")
    cl = request.headers.get("content-length")
    if cl and int(cl) > I.MAX_BYTES:
        raise HTTPException(413, "File quá lớn (tối đa 20 MB)")
    data = await request.body()
    db = SessionLocal()
    try:
        cfg = get_settings(db)
        try:
            kind, res = I.parse_any(filename, data, target, sheet, ocr, bool(cfg["allow_cloud_ocr"]), app_settings.gemini_api_key)
        except I.ImportError_ as e:
            audit(user, "import.upload.failed", "import", None, f"{filename}: {e}", client_ip(request))
            raise HTTPException(422, str(e))
        mapping = I.auto_mapping(res["columns"], target)
        b = CorpImportBatch(filename=filename[:200], kind=kind, method=res["method"], target=target, status="Xem trước", mapping=mapping,
                            columns=res["columns"], rows=res["rows"], created_by=user.username, created_rm=user.rm_name,
                            summary={"rows": len(res["rows"]), "warnings": res["warnings"]})
        db.add(b); db.commit(); db.refresh(b)
        audit(user, "import.upload", "import", b.id, f"{filename} ({res['method']}, {len(res['rows'])} dòng)", client_ip(request))
        defs = I.field_defs(target)
        return {"batch": _batch_row(b, full=True), "sheets": res.get("sheets", []), "sheet": res.get("sheet"),
                "sample": res["rows"][:8], "warnings": res["warnings"],
                "fields": [{"key": k, "label": v[0], "required": k in ("name", "ref", "month")} for k, v in defs.items()],
                "requires_approval": bool(cfg["import_requires_approval"]) and not is_admin(user)}
    finally:
        db.close()


class PlanIn(BaseModel):
    mapping: dict
    update_existing: bool = True
    default_rm: Optional[str] = None


def _find_existing(db, f, name_index, tax_index, id_index):
    if f.get("tax_code") and f["tax_code"] in tax_index:
        return tax_index[f["tax_code"]]
    if f.get("customer_id") and f["customer_id"] in id_index:
        return id_index[f["customer_id"]]
    if f.get("name") and not f.get("tax_code") and f["name"].casefold() in name_index:
        return name_index[f["name"].casefold()]
    return None


def plan(db, user, b: CorpImportBatch, mapping: dict, update_existing: bool, default_rm: Optional[str]):
    """Chạy kiểm tra toàn bộ dòng. Trả (results, stats). results[i] = {row, action, errors, warnings, data}."""
    mapping = {c: f for c, f in mapping.items() if f}
    if b.target == "monthly":
        return _plan_monthly(db, user, b, mapping)
    if "name" not in mapping.values():
        raise HTTPException(400, "Chưa ghép cột 'Tên doanh nghiệp' — đây là cột bắt buộc")
    all_c = db.query(CorpCustomer).all()
    tax_index = {c.tax_code: c for c in all_c if c.tax_code}
    id_index = {c.customer_id: c for c in all_c}
    name_index = {c.name.casefold(): c for c in all_c}
    seen_tax, seen_name = set(), set()
    results, stats = [], {"create": 0, "update": 0, "skip": 0, "error": 0, "warn": 0}
    admin = is_admin(user)
    rm_default = (default_rm if admin and default_rm else None) or user.rm_name
    for i, raw in enumerate(b.rows or []):
        f, errs, warns = I.normalize_customer_row(raw, mapping)
        action, data = "create", None
        if not f.get("name"):
            errs.append("Thiếu tên doanh nghiệp")
        # trùng lặp trong cùng file
        key = f.get("tax_code") or (f.get("name") or "").casefold()
        if key and key in (seen_tax | seen_name):
            errs.append("Trùng với một dòng phía trên trong cùng file")
        (seen_tax if f.get("tax_code") else seen_name).add(key)
        ex = _find_existing(db, f, name_index, tax_index, id_index) if f.get("name") else None
        # quyền: nhân viên chỉ được động tới khách của mình
        if ex is not None and not admin and ex.rm_name != user.rm_name:
            errs.append("Trùng với khách hàng thuộc danh mục cán bộ khác — liên hệ Admin")
            ex = None
        if not admin and f.get("rm_name") and f["rm_name"] != user.rm_name:
            warns.append("Cột cán bộ phụ trách bị bỏ qua — khách hàng sẽ gán cho bạn")
        if not errs:
            try:
                if ex is not None:
                    if not update_existing:
                        action = "skip"; warns.append("Đã có trong hệ thống — bỏ qua (không chọn cập nhật)")
                    else:
                        action = "update"
                        base = customer_dict(ex)
                        merged = {**base, **{k: v for k, v in f.items() if k not in ("customer_id", "rm_name")}}
                        if not admin or not f.get("rm_name"):
                            merged["rm_name"] = ex.rm_name
                        else:
                            merged["rm_name"] = f["rm_name"]
                        d = CustomerIn(**merged).model_dump()
                        d = normalize_input(d)
                        errs += validate_customer(d)
                        d["rm_name"] = merged["rm_name"]
                        data = {"id": ex.customer_id, "fields": {k: v for k, v in d.items() if k in f or k in ("segment",)}, "full": d}
                else:
                    fields = {k: v for k, v in f.items() if k not in ("customer_id",)}
                    fields["rm_name"] = (f.get("rm_name") if admin and f.get("rm_name") else rm_default)
                    d = CustomerIn(**fields).model_dump()
                    d = normalize_input(d)
                    errs += validate_customer(d)
                    d["rm_name"] = fields["rm_name"]
                    data = {"id": f.get("customer_id") if (f.get("customer_id") and f["customer_id"] not in id_index) else None, "full": d}
            except Exception as e:  # noqa: BLE001 — pydantic ValidationError
                msgs = getattr(e, "errors", None)
                if callable(msgs):
                    for er in e.errors():
                        errs.append(f"{'.'.join(map(str, er['loc']))}: {er['msg']}")
                else:
                    errs.append(str(e)[:150])
        if errs:
            action = "error"
        stats[action] += 1
        stats["warn"] += 1 if warns else 0
        results.append({"row": i + 2, "action": action, "name": f.get("name") or "", "errors": errs, "warnings": warns, "data": data})
    return results, stats


def _plan_monthly(db, user, b, mapping):
    if "ref" not in mapping.values() or "month" not in mapping.values():
        raise HTTPException(400, "Cần ghép cột 'Mã KH hoặc MST' và 'Tháng'")
    q = db.query(CorpCustomer)
    if not is_admin(user):
        q = q.filter(CorpCustomer.rm_name == user.rm_name)
    own = q.all()
    by_ref = {}
    for c in own:
        by_ref[c.customer_id] = c
        if c.tax_code:
            by_ref[c.tax_code] = c
    results, stats = [], {"create": 0, "update": 0, "skip": 0, "error": 0, "warn": 0}
    seen = set()
    for i, raw in enumerate(b.rows or []):
        f, errs, warns = I.normalize_monthly_row(raw, mapping)
        c = by_ref.get(f.get("ref", ""))
        if f.get("ref") and not c:
            errs.append("Không tìm thấy khách hàng (hoặc không thuộc danh mục của bạn)")
        if c and f.get("month"):
            if (c.customer_id, f["month"]) in seen:
                errs.append("Trùng khách hàng + tháng trong cùng file")
            seen.add((c.customer_id, f["month"]))
        action, data = "create", None
        if not errs:
            ex = db.query(CorpMonthly).filter_by(customer_id=c.customer_id, month=f["month"]).first()
            action = "update" if ex else "create"
            data = {"customer_id": c.customer_id, "month": f["month"], "values": {k: v for k, v in f.items() if k not in ("ref", "month")}}
        else:
            action = "error"
        stats[action] += 1
        results.append({"row": i + 2, "action": action, "name": f.get("ref", ""), "errors": errs, "warnings": warns, "data": data})
    return results, stats


@router.post("/{bid}/preview")
def preview(bid: int, body: PlanIn, user=Depends(current_user)):
    db = SessionLocal()
    try:
        b = _own(db, user, bid)
        if b.status not in ("Xem trước", "Chờ duyệt"):
            raise HTTPException(409, f"Lô này đã ở trạng thái '{b.status}'")
        res, stats = plan(db, user, b, body.mapping, body.update_existing, body.default_rm)
        bad = [r for r in res if r["errors"] or r["warnings"]][:MAX_PREVIEW]
        ok = [r for r in res if not r["errors"] and not r["warnings"]][: max(0, 12 - len(bad))]
        for r in bad + ok:
            r.pop("data", None)
        unmapped = [c for c in b.columns if not body.mapping.get(c)]
        return {"stats": stats, "total": len(res), "problems": bad, "ok_sample": ok, "unmapped": unmapped}
    finally:
        db.close()


def _apply(db, user_name: str, results, b):
    created = updated = 0
    ids = {c.customer_id for c in db.query(CorpCustomer.customer_id)}
    if b.target == "monthly":
        for r in results:
            if r["action"] not in ("create", "update"):
                continue
            d = r["data"]
            ex = db.query(CorpMonthly).filter_by(customer_id=d["customer_id"], month=d["month"]).first()
            if ex:
                for k, v in d["values"].items():
                    setattr(ex, k, v)
                updated += 1
            else:
                db.add(CorpMonthly(customer_id=d["customer_id"], month=d["month"], **d["values"]))
                created += 1
        return created, updated
    for r in results:
        if r["action"] == "create":
            full = dict(r["data"]["full"])
            cid = r["data"].get("id") or next_id(db)
            while cid in ids:
                cid = next_id(db)
            ids.add(cid)
            full["customer_id"] = cid
            full.pop("created_at", None)
            db.add(CorpCustomer(**full)); db.flush()
            created += 1
        elif r["action"] == "update":
            c = db.query(CorpCustomer).filter_by(customer_id=r["data"]["id"]).first()
            full = r["data"]["full"]
            for k, v in full.items():
                if k in ("customer_id", "created_at"):
                    continue
                setattr(c, k, v)
            updated += 1
    return created, updated


def _execute(db, actor, b: CorpImportBatch, body: PlanIn, as_user):
    res, stats = plan(db, as_user, b, body.mapping, body.update_existing, body.default_rm)
    created, updated = _apply(db, actor, res, b)
    b.summary = {**(b.summary or {}), "created": created, "updated": updated, "skipped": stats["skip"], "errors": stats["error"],
                 "error_rows": [{"row": r["row"], "name": r["name"], "errors": r["errors"]} for r in res if r["action"] == "error"][:200]}
    b.status = "Đã nhập"
    b.mapping = body.mapping
    return created, updated, stats


class CommitIn(PlanIn):
    note: Optional[str] = None


@router.post("/{bid}/commit")
def commit(bid: int, body: CommitIn, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        b = _own(db, user, bid)
        if b.status != "Xem trước":
            raise HTTPException(409, f"Lô này đã ở trạng thái '{b.status}'")
        cfg = get_settings(db)
        if not is_admin(user) and cfg["import_requires_approval"]:
            res, stats = plan(db, user, b, body.mapping, body.update_existing, body.default_rm)   # kiểm tra trước khi gửi duyệt
            if stats["create"] + stats["update"] == 0:
                raise HTTPException(400, "Không có dòng hợp lệ nào để gửi duyệt")
            b.mapping = {c: f for c, f in body.mapping.items() if f}
            b.status = "Chờ duyệt"
            b.note = (body.note or "")[:300] or None
            b.summary = {**(b.summary or {}), "pending": stats, "update_existing": body.update_existing}
            db.commit()
            audit(user, "import.submit", "import", bid, f"{b.filename}: {stats['create']} mới, {stats['update']} cập nhật", client_ip(request))
            return {"status": "Chờ duyệt", "stats": stats}
        created, updated, stats = _execute(db, user.username, b, body, user)
        b.reviewed_by, b.reviewed_at = user.username, datetime.utcnow()
        db.commit()
        audit(user, "import.commit", "import", bid, f"{b.filename}: +{created} / ~{updated}", client_ip(request))
        return {"status": "Đã nhập", "created": created, "updated": updated, "stats": stats}
    finally:
        db.close()


@router.get("/batches")
def batches(user=Depends(current_user)):
    db = SessionLocal()
    try:
        q = db.query(CorpImportBatch).order_by(CorpImportBatch.id.desc())
        if not is_admin(user):
            q = q.filter(CorpImportBatch.created_by == user.username)
        items = [_batch_row(b) for b in q.limit(100)]
        return {"items": items, "pending": sum(1 for i in items if i["status"] == "Chờ duyệt")}
    finally:
        db.close()


@router.get("/{bid}")
def batch_detail(bid: int, user=Depends(current_user)):
    db = SessionLocal()
    try:
        b = _own(db, user, bid)
        return {"batch": _batch_row(b, full=True), "sample": (b.rows or [])[:8]}
    finally:
        db.close()


@router.post("/{bid}/approve")
def approve(bid: int, request: Request, admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        b = db.query(CorpImportBatch).filter_by(id=bid).first()
        if not b:
            raise HTTPException(404, "Không tìm thấy lô import")
        if b.status != "Chờ duyệt":
            raise HTTPException(409, f"Lô này đang ở trạng thái '{b.status}'")
        # Thực hiện với quyền của người gửi để rm_name/giới hạn giữ nguyên như lúc kiểm tra
        from src.accounts.service import AuthUser
        owner = AuthUser(0, b.created_by or "", b.created_by or "", "staff", b.created_rm, False)
        body = PlanIn(mapping=b.mapping or {}, update_existing=bool((b.summary or {}).get("update_existing", True)))
        created, updated, stats = _execute(db, admin.username, b, body, owner)
        b.reviewed_by, b.reviewed_at = admin.username, datetime.utcnow()
        db.commit()
        audit(admin, "import.approve", "import", bid, f"{b.filename}: +{created} / ~{updated} (gửi bởi {b.created_by})", client_ip(request))
        return {"status": "Đã nhập", "created": created, "updated": updated}
    finally:
        db.close()


class RejectIn(BaseModel):
    note: Optional[str] = None


@router.post("/{bid}/reject")
def reject(bid: int, body: RejectIn, request: Request, admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        b = db.query(CorpImportBatch).filter_by(id=bid).first()
        if not b or b.status != "Chờ duyệt":
            raise HTTPException(404, "Không có lô nào đang chờ duyệt với mã này")
        b.status, b.reviewed_by, b.reviewed_at, b.note = "Từ chối", admin.username, datetime.utcnow(), (body.note or "")[:300] or b.note
        db.commit()
        audit(admin, "import.reject", "import", bid, body.note, client_ip(request))
        return {"status": "Từ chối"}
    finally:
        db.close()


@router.delete("/{bid}")
def cancel(bid: int, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        b = _own(db, user, bid)
        if b.status not in ("Xem trước", "Chờ duyệt"):
            raise HTTPException(409, "Chỉ hủy được lô chưa nhập")
        if b.status == "Chờ duyệt" and not is_admin(user):
            pass  # người gửi được rút lại lô của mình
        b.status, b.rows = "Hủy", []
        db.commit()
        audit(user, "import.cancel", "import", bid, b.filename, client_ip(request))
        return {"ok": True}
    finally:
        db.close()
