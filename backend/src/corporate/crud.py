"""Thêm / sửa / xóa khách hàng DN (nhập liệu thủ công) + chuyển danh mục."""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from src.database import SessionLocal
from src.accounts.deps import current_user, require_admin, client_ip
from src.accounts.service import audit
from .models import (CorpCustomer, CorpMonthly, CorpInteraction, CorpOpportunity, CorpMessage, CorpCampaignTarget,
                     CorpOptOut, customer_dict)
from .catalog import PRODUCTS, TITLES, LIFECYCLES
from .access import get_customer_or_403, is_admin

router = APIRouter(prefix="/api/corp", tags=["corporate-crud"])

LANGS = ("vi", "zh", "en")


def segment_for(rev_bn: float) -> str:
    return "Large" if rev_bn >= 1500 else "Middle" if rev_bn >= 300 else "SME"


class CustomerIn(BaseModel):
    name: str = Field(min_length=2)
    name_zh: Optional[str] = None
    tax_code: Optional[str] = None
    ownership: str = "Nội địa"
    investor_country: Optional[str] = None
    industry: str = "Chưa phân loại"
    province: str = "Chưa rõ"
    industrial_zone: Optional[str] = None
    employees: int = Field(0, ge=0)
    annual_revenue_bn: float = Field(0, ge=0)
    total_assets_bn: float = Field(0, ge=0)
    equity_bn: float = 0
    export_usd_m: float = Field(0, ge=0)
    import_usd_m: float = Field(0, ge=0)
    fx_exposure_usd_m: float = Field(0, ge=0)
    casa_balance_bn: float = Field(0, ge=0)
    deposit_bn: float = Field(0, ge=0)
    loan_outstanding_bn: float = Field(0, ge=0)
    credit_limit_bn: float = Field(0, ge=0)
    limit_expiry: Optional[date] = None
    debt_group: int = Field(1, ge=1, le=5)
    relationship_years: int = Field(0, ge=0)
    products_held: list[str] = []
    rm_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_name_zh: Optional[str] = None
    contact_title: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    preferred_language: str = "vi"
    lifecycle: str = "prospect"


def validate_customer(d: dict) -> list[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ). Dùng chung cho nhập tay và import."""
    errs = []
    if d["ownership"] not in ("Nội địa", "FDI"):
        errs.append("Loại hình phải là 'Nội địa' hoặc 'FDI'")
    if d.get("tax_code") and not re.fullmatch(r"\d{10}(-\d{3})?", d["tax_code"]):
        errs.append("Mã số thuế phải gồm 10 chữ số (hoặc 10 số-3 số cho chi nhánh)")
    if d.get("contact_email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d["contact_email"]):
        errs.append("Email liên hệ không hợp lệ")
    if d.get("contact_phone") and not re.fullmatch(r"\+?\d{8,13}", d["contact_phone"]):
        errs.append("Số điện thoại liên hệ không hợp lệ")
    if d["preferred_language"] not in LANGS:
        errs.append("Ngôn ngữ ưu tiên phải là vi / zh / en")
    if d.get("lifecycle", "prospect") not in LIFECYCLES:
        errs.append("Loại khách phải là 'prospect' (KH mới) hoặc 'existing' (hiện hữu TPBank)")
    if d.get("contact_title") and d["contact_title"] not in TITLES:
        errs.append("Chức danh liên hệ phải là GD / PGD / KTT / CFO")
    bad = [p for p in d.get("products_held", []) if p not in PRODUCTS]
    if bad:
        errs.append("Sản phẩm không hợp lệ: " + ", ".join(bad))
    if d["credit_limit_bn"] and d["loan_outstanding_bn"] > d["credit_limit_bn"] * 1.5:
        errs.append("Dư nợ vượt quá 150% hạn mức — kiểm tra lại số liệu")
    if d["credit_limit_bn"] and not d.get("limit_expiry"):
        pass  # chỉ cảnh báo ở import, không chặn
    return errs


def normalize_input(d: dict) -> dict:
    d = dict(d)
    d["name"] = d["name"].strip()
    d["tax_code"] = (d.get("tax_code") or "").strip() or None
    if d["ownership"] == "Nội địa":
        d["investor_country"] = None
    d["segment"] = segment_for(d["annual_revenue_bn"])
    d["products_held"] = sorted(set(d.get("products_held") or []))
    if not d.get("contact_title"):
        d["contact_title"] = None
    return d


def next_id(db) -> str:
    n = 0
    for (cid,) in db.query(CorpCustomer.customer_id).filter(CorpCustomer.customer_id.like("DN%")):
        m = re.fullmatch(r"DN(\d+)", cid)
        if m:
            n = max(n, int(m.group(1)))
    return f"DN{n + 1:05d}"


@router.post("/customers")
def create_customer(body: CustomerIn, request: Request, user=Depends(current_user)):
    d = normalize_input(body.model_dump())
    errs = validate_customer(d)
    if errs:
        raise HTTPException(400, "; ".join(errs))
    db = SessionLocal()
    try:
        if d["tax_code"] and db.query(CorpCustomer).filter_by(tax_code=d["tax_code"]).first():
            raise HTTPException(409, "Mã số thuế đã tồn tại trong hệ thống")
        d["rm_name"] = (d.get("rm_name") or user.rm_name) if is_admin(user) else user.rm_name
        d["customer_id"] = next_id(db)
        db.add(CorpCustomer(**d)); db.commit()
        audit(user, "customer.create", "customer", d["customer_id"], d["name"], client_ip(request))
        return {"customer_id": d["customer_id"]}
    finally:
        db.close()


@router.put("/customers/{cid}")
def update_customer(cid: str, body: CustomerIn, request: Request, user=Depends(current_user)):
    d = normalize_input(body.model_dump())
    errs = validate_customer(d)
    if errs:
        raise HTTPException(400, "; ".join(errs))
    db = SessionLocal()
    try:
        c = get_customer_or_403(db, user, cid)
        if d["tax_code"]:
            dup = db.query(CorpCustomer).filter(CorpCustomer.tax_code == d["tax_code"], CorpCustomer.customer_id != cid).first()
            if dup:
                raise HTTPException(409, "Mã số thuế đã được dùng cho khách hàng khác")
        if is_admin(user):
            d["rm_name"] = d.get("rm_name") or c.rm_name
        else:
            d["rm_name"] = c.rm_name        # nhân viên không được chuyển danh mục
        before = customer_dict(c)
        for k, v in d.items():
            setattr(c, k, v)
        db.commit()
        changed = [k for k, v in d.items() if before.get(k) != (v.isoformat() if isinstance(v, date) else v)]
        audit(user, "customer.update", "customer", cid, ", ".join(changed)[:500], client_ip(request))
        return {"ok": True}
    finally:
        db.close()


def purge_customers(db, ids: list[str]):
    for model in (CorpMonthly, CorpInteraction, CorpOpportunity, CorpMessage, CorpCampaignTarget, CorpOptOut):
        db.query(model).filter(model.customer_id.in_(ids)).delete(synchronize_session=False)
    db.query(CorpCustomer).filter(CorpCustomer.customer_id.in_(ids)).delete(synchronize_session=False)


@router.delete("/customers/{cid}")
def delete_customer(cid: str, request: Request, admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        c = db.query(CorpCustomer).filter_by(customer_id=cid).first()
        if not c:
            raise HTTPException(404, "Không tìm thấy khách hàng")
        name = c.name
        purge_customers(db, [cid]); db.commit()
        audit(admin, "customer.delete", "customer", cid, name, client_ip(request))
        return {"ok": True}
    finally:
        db.close()


class ReassignIn(BaseModel):
    customer_ids: Optional[list[str]] = None
    from_rm: Optional[str] = None
    to_rm: str


@router.post("/customers/reassign")
def reassign(body: ReassignIn, request: Request, admin=Depends(require_admin)):
    if not body.customer_ids and not body.from_rm:
        raise HTTPException(400, "Chọn danh sách khách hàng hoặc cán bộ nguồn")
    db = SessionLocal()
    try:
        q = db.query(CorpCustomer)
        q = q.filter(CorpCustomer.customer_id.in_(body.customer_ids)) if body.customer_ids else q.filter(CorpCustomer.rm_name == body.from_rm)
        n = q.update({CorpCustomer.rm_name: body.to_rm}, synchronize_session=False)
        db.commit()
        audit(admin, "customer.reassign", "customer", None, f"{n} KH → {body.to_rm}", client_ip(request))
        return {"moved": n}
    finally:
        db.close()
