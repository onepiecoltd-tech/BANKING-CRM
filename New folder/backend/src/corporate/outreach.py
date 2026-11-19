"""Trung tâm tiếp cận (chọn tệp KH, kiểm tra loại trừ tuân thủ, soạn hàng loạt, ghi nhận đã gửi) + Chiến dịch."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from src.database import SessionLocal
from src.accounts.deps import current_user, client_ip
from src.accounts.service import audit
from .models import (CorpMonthly, CorpCustomer, CorpMessage, CorpInteraction, CorpOpportunity, CorpOptOut, CorpCampaign,
                     CorpCampaignTarget, customer_dict)
from .catalog import PRODUCTS, STAGE_PROB
from .access import get_settings, rm_filter, get_customer_or_403, is_admin
from . import scoring, messages
from .router import _items, _summary, _get_one

router = APIRouter(prefix="/api/corp", tags=["corporate-outreach"])

CHANNEL_LABEL = {"zalo": "Zalo", "email": "Email", "call": "Điện thoại"}
TARGET_STATUS = ["Chưa liên hệ", "Đã liên hệ", "Phản hồi", "Quan tâm", "Chuyển đổi", "Từ chối"]


# ── tệp khách hàng + loại trừ ────────────────────────────────────────────────
class AudienceIn(BaseModel):
    product: str
    channel: str = "zalo"
    segment: Optional[str] = None
    ownership: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    province: Optional[str] = None
    tier: Optional[str] = None
    rm: Optional[str] = None
    min_score: int = 60
    limit: int = 300


def _last_out_map(db, ids):
    m = {}
    for r in db.query(CorpMessage).filter(CorpMessage.direction == "out").order_by(CorpMessage.created_at):
        if r.customer_id in ids:
            m[r.customer_id] = r.created_at.date()
    return m


def _suppression_reason(c, cfg, channel, optout, last_out, today):
    if c["customer_id"] in optout:
        return "optout", "Khách hàng đã từ chối nhận tin"
    if c["debt_group"] > int(cfg["max_debt_group_outreach"]):
        return "debt", f"Nợ nhóm {c['debt_group']} — không chào bán chéo"
    cap = int(cfg["freq_cap_days"])
    cands = []
    lc = c.get("last_contact_date")
    if lc:
        cands.append(datetime.fromisoformat(lc).date() if isinstance(lc, str) else lc)
    if last_out.get(c["customer_id"]):
        cands.append(last_out[c["customer_id"]])
    last = max(cands) if cands else None
    if last and cap and (today - last).days < cap:
        return "freq", f"Đã liên hệ {(today - last).days} ngày trước (giới hạn {cap} ngày)"
    if channel == "email" and not c.get("contact_email"):
        return "contact", "Thiếu email liên hệ"
    if channel in ("zalo", "call") and not c.get("contact_phone"):
        return "contact", "Thiếu số điện thoại liên hệ"
    return None, None


def build_audience(db, user, a: AudienceIn):
    if a.product not in PRODUCTS:
        raise HTTPException(400, "Sản phẩm không hợp lệ")
    if a.channel not in CHANNEL_LABEL:
        raise HTTPException(400, "Kênh không hợp lệ")
    cfg = get_settings(db)
    items = _items(db, user)
    ids = {it["c"]["customer_id"] for it in items}
    optout = {r.customer_id for r in db.query(CorpOptOut)}
    last_out = _last_out_map(db, ids)
    today = date.today()
    eligible, suppressed = [], []
    for it in items:
        c, an = it["c"], it["a"]
        if a.segment and c["segment"] != a.segment: continue
        if a.ownership and c["ownership"] != a.ownership: continue
        if a.country and c["investor_country"] != a.country: continue
        if a.industry and c["industry"] != a.industry: continue
        if a.province and c["province"] != a.province: continue
        if a.tier and an["tier"] != a.tier: continue
        if a.rm and c["rm_name"] != a.rm: continue
        p = an["propensities"][a.product]
        if p["held"] and a.product != "VAY_VLD":
            continue
        if p["score"] < a.min_score:
            continue
        s = _summary(c, an)
        s["product_score"] = p["score"]
        s["reasons"] = p["reasons"][:3]
        s["expected_amount_bn"] = scoring.expected_amount_bn(a.product, c, an["metrics"])
        code, why = _suppression_reason(c, cfg, a.channel, optout, last_out, today)
        if code:
            s["suppress_code"], s["suppress_reason"] = code, why
            suppressed.append(s)
        else:
            eligible.append(s)
    eligible.sort(key=lambda s: -s["product_score"])
    suppressed.sort(key=lambda s: -s["product_score"])
    reasons = {}
    for s in suppressed:
        reasons[s["suppress_code"]] = reasons.get(s["suppress_code"], 0) + 1
    return {"eligible": eligible[: a.limit], "eligible_total": len(eligible), "suppressed": suppressed[:100],
            "suppressed_total": len(suppressed), "suppress_counts": reasons,
            "rules": {"freq_cap_days": cfg["freq_cap_days"], "max_debt_group": cfg["max_debt_group_outreach"],
                      "quiet": f"{cfg['quiet_start']}–{cfg['quiet_end']}"}}


@router.post("/outreach/audience")
def audience(body: AudienceIn, user=Depends(current_user)):
    db = SessionLocal()
    try:
        return build_audience(db, user, body)
    finally:
        db.close()


class DraftsIn(BaseModel):
    product: str
    channel: str = "zalo"
    language: str = "auto"
    framework: str = "consultative"
    customer_ids: list[str]


def make_drafts(db, user, body: DraftsIn):
    if body.product not in PRODUCTS:
        raise HTTPException(400, "Sản phẩm không hợp lệ")
    if body.channel not in CHANNEL_LABEL:
        raise HTTPException(400, "Kênh không hợp lệ")
    if body.framework not in messages.FRAMEWORKS:
        raise HTTPException(400, "Khung soạn tin không hợp lệ")
    cfg = get_settings(db)
    out = []
    for cid in body.customer_ids[:200]:
        c, ms = _get_one(db, cid, user)
        d = messages.draft(c, scoring.metrics(c, ms), body.product, body.channel,
                           None if body.language == "auto" else body.language, user.full_name, cfg["bank_name"], body.framework)
        d["customer_name"] = c["name"]
        out.append(d)
    return out


@router.post("/outreach/drafts")
def drafts(body: DraftsIn, user=Depends(current_user)):
    db = SessionLocal()
    try:
        return {"drafts": make_drafts(db, user, body), "frameworks": messages.FRAMEWORKS}
    finally:
        db.close()


# ── ghi nhận đã gửi ──────────────────────────────────────────────────────────
class SentItem(BaseModel):
    customer_id: str
    product: Optional[str] = None
    channel: str = "zalo"
    language: Optional[str] = None
    subject: Optional[str] = None
    body: str
    campaign_id: Optional[int] = None
    target_id: Optional[int] = None


class SentIn(BaseModel):
    items: list[SentItem]
    create_opportunity: bool = True


def log_sent(db, user, items: list[SentItem], create_opportunity=True) -> dict:
    cfg = get_settings(db)
    optout = {r.customer_id for r in db.query(CorpOptOut)}
    done, blocked = 0, []
    for it in items:
        c = get_customer_or_403(db, user, it.customer_id)
        if it.customer_id in optout:
            blocked.append({"customer_id": it.customer_id, "reason": "Khách hàng đã từ chối nhận tin"})
            continue
        now = datetime.utcnow()
        db.add(CorpMessage(customer_id=it.customer_id, campaign_id=it.campaign_id, direction="out", channel=it.channel,
                           language=it.language, subject=it.subject, body=it.body, product=it.product,
                           created_by=user.username, created_at=now))
        db.add(CorpInteraction(customer_id=it.customer_id, date=date.today(), channel=CHANNEL_LABEL.get(it.channel, it.channel),
                               summary=f"Gửi nội dung giới thiệu {PRODUCTS[it.product]['vi']}" if it.product in PRODUCTS else "Gửi nội dung tiếp cận",
                               outcome="Đã gửi"))
        c.last_contact_date = date.today()
        if it.target_id:
            t = db.query(CorpCampaignTarget).filter_by(id=it.target_id).first()
            if t and t.status == "Chưa liên hệ":
                t.status = "Đã liên hệ"
            if t:
                t.sent_at, t.updated_at = now, now
        if create_opportunity and it.product in PRODUCTS:
            exists = db.query(CorpOpportunity).filter(CorpOpportunity.customer_id == it.customer_id, CorpOpportunity.product == it.product,
                                                      CorpOpportunity.stage.notin_(["Thất bại", "Triển khai"])).first()
            if not exists:
                cd = customer_dict(c)
                ms = [{k: getattr(r, k) for k in ("month", "inflow_bn", "outflow_bn", "trade_usd_m", "avg_balance_bn")}
                      for r in db.query(CorpMonthly).filter_by(customer_id=it.customer_id)]
                db.add(CorpOpportunity(customer_id=it.customer_id, product=it.product, stage="Tiếp cận", probability=STAGE_PROB["Tiếp cận"],
                                       expected_amount_bn=scoring.expected_amount_bn(it.product, cd, scoring.metrics(cd, ms)),
                                       next_action="Theo dõi phản hồi sau khi gửi", due_date=date.today() + timedelta(days=cfg["freq_cap_days"] // 2 or 3)))
        done += 1
    db.commit()
    return {"logged": done, "blocked": blocked}


@router.post("/outreach/log")
def log(body: SentIn, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        r = log_sent(db, user, body.items, body.create_opportunity)
        audit(user, "outreach.log", "customer", None, f"{r['logged']} tin, chặn {len(r['blocked'])}", client_ip(request))
        return r
    finally:
        db.close()


# ── chiến dịch ───────────────────────────────────────────────────────────────
def _camp_scope(q, user):
    return q if is_admin(user) else q.filter(CorpCampaign.owner == user.username)


def _camp_row(db, cp: CorpCampaign):
    ts = db.query(CorpCampaignTarget).filter_by(campaign_id=cp.id).all()
    counts = {s: 0 for s in TARGET_STATUS}
    for t in ts:
        counts[t.status] = counts.get(t.status, 0) + 1
    n = len(ts)
    reached = n - counts["Chưa liên hệ"]
    replied = counts["Phản hồi"] + counts["Quan tâm"] + counts["Chuyển đổi"] + counts["Từ chối"]
    return {"id": cp.id, "name": cp.name, "product": cp.product, "product_name": PRODUCTS[cp.product]["vi"], "channel": cp.channel,
            "language": cp.language, "framework": cp.framework, "status": cp.status, "owner": cp.owner, "owner_rm": cp.owner_rm,
            "created_at": cp.created_at.isoformat(), "total": n, "counts": counts,
            "contacted_pct": round(reached / n * 100) if n else 0, "reply_pct": round(replied / reached * 100) if reached else 0,
            "interest_pct": round((counts["Quan tâm"] + counts["Chuyển đổi"]) / reached * 100) if reached else 0,
            "conv_pct": round(counts["Chuyển đổi"] / reached * 100) if reached else 0}


@router.get("/campaigns")
def list_campaigns(user=Depends(current_user)):
    db = SessionLocal()
    try:
        rows = _camp_scope(db.query(CorpCampaign), user).order_by(CorpCampaign.id.desc()).all()
        return {"items": [_camp_row(db, cp) for cp in rows]}
    finally:
        db.close()


class CampaignIn(BaseModel):
    name: str
    product: str
    channel: str = "zalo"
    language: str = "auto"
    framework: str = "consultative"
    segment: Optional[str] = None
    ownership: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    province: Optional[str] = None
    tier: Optional[str] = None
    rm: Optional[str] = None
    min_score: int = 60
    customer_ids: Optional[list[str]] = None     # nếu có: chỉ lấy tập con của tệp đủ điều kiện


@router.post("/campaigns")
def create_campaign(body: CampaignIn, request: Request, user=Depends(current_user)):
    if not body.name.strip():
        raise HTTPException(400, "Nhập tên chiến dịch")
    db = SessionLocal()
    try:
        aud = build_audience(db, user, AudienceIn(**{k: v for k, v in body.model_dump().items() if k in AudienceIn.model_fields}, limit=500))
        chosen = aud["eligible"]
        if body.customer_ids is not None:
            keep = set(body.customer_ids)
            chosen = [s for s in chosen if s["customer_id"] in keep]
        if not chosen:
            raise HTTPException(400, "Không có khách hàng đủ điều kiện trong tệp đã chọn")
        filters = {k: v for k, v in body.model_dump().items() if k in ("segment", "ownership", "country", "industry", "province", "tier", "rm", "min_score") and v}
        cp = CorpCampaign(name=body.name.strip()[:120], product=body.product, channel=body.channel, language=body.language,
                          framework=body.framework, filters=filters, owner=user.username, owner_rm=user.rm_name)
        db.add(cp); db.flush()
        ds = make_drafts(db, user, DraftsIn(product=body.product, channel=body.channel, language=body.language,
                                            framework=body.framework, customer_ids=[s["customer_id"] for s in chosen]))
        by = {d["customer_id"]: d for d in ds}
        for s in chosen:
            d = by[s["customer_id"]]
            db.add(CorpCampaignTarget(campaign_id=cp.id, customer_id=s["customer_id"], language=d["language"], subject=d["subject"], body=d["body"]))
        db.commit()
        audit(user, "campaign.create", "campaign", cp.id, f"{cp.name}: {len(chosen)} KH", client_ip(request))
        return {"id": cp.id, "targets": len(chosen), "skipped": aud["suppressed_total"]}
    finally:
        db.close()


@router.get("/campaigns/{cid}")
def campaign_detail(cid: int, user=Depends(current_user)):
    db = SessionLocal()
    try:
        cp = _camp_scope(db.query(CorpCampaign), user).filter_by(id=cid).first()
        if not cp:
            raise HTTPException(404, "Không tìm thấy chiến dịch")
        custs = {c.customer_id: c for c in rm_filter(db.query(CorpCustomer), user)}
        rows = []
        for t in db.query(CorpCampaignTarget).filter_by(campaign_id=cid).order_by(CorpCampaignTarget.id):
            c = custs.get(t.customer_id)
            if not c:
                continue
            rows.append({"id": t.id, "customer_id": t.customer_id, "name": c.name, "contact_name": c.contact_name, "segment": c.segment,
                         "industry": c.industry, "rm_name": c.rm_name, "status": t.status, "language": t.language, "subject": t.subject,
                         "body": t.body, "sent_at": t.sent_at.isoformat() if t.sent_at else None})
        return {"campaign": _camp_row(db, cp), "targets": rows, "statuses": TARGET_STATUS}
    finally:
        db.close()


class TargetPatch(BaseModel):
    status: str


@router.patch("/campaigns/{cid}/targets/{tid}")
def patch_target(cid: int, tid: int, body: TargetPatch, request: Request, user=Depends(current_user)):
    if body.status not in TARGET_STATUS:
        raise HTTPException(400, "Trạng thái không hợp lệ")
    db = SessionLocal()
    try:
        cp = _camp_scope(db.query(CorpCampaign), user).filter_by(id=cid).first()
        t = db.query(CorpCampaignTarget).filter_by(id=tid, campaign_id=cid).first()
        if not cp or not t:
            raise HTTPException(404, "Không tìm thấy mục tiêu chiến dịch")
        get_customer_or_403(db, user, t.customer_id)
        t.status, t.updated_at = body.status, datetime.utcnow()
        if body.status in ("Quan tâm", "Chuyển đổi"):
            exists = db.query(CorpOpportunity).filter(CorpOpportunity.customer_id == t.customer_id, CorpOpportunity.product == cp.product,
                                                      CorpOpportunity.stage.notin_(["Thất bại"])).first()
            if exists:
                if body.status == "Chuyển đổi":
                    exists.stage, exists.probability, exists.updated_at = "Triển khai", STAGE_PROB["Triển khai"], datetime.utcnow()
                elif exists.stage == "Tiếp cận":
                    exists.stage, exists.probability, exists.updated_at = "Đang tư vấn", STAGE_PROB["Đang tư vấn"], datetime.utcnow()
        if body.status == "Từ chối":
            opp = db.query(CorpOpportunity).filter(CorpOpportunity.customer_id == t.customer_id, CorpOpportunity.product == cp.product,
                                                   CorpOpportunity.stage.in_(["Tiếp cận", "Đang tư vấn"])).first()
            if opp:
                opp.stage, opp.probability, opp.updated_at = "Thất bại", 0, datetime.utcnow()
        db.commit()
        audit(user, "campaign.target", "campaign", cid, f"{t.customer_id} → {body.status}", client_ip(request))
        return {"ok": True}
    finally:
        db.close()


@router.post("/campaigns/{cid}/targets/{tid}/sent")
def target_sent(cid: int, tid: int, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        cp = _camp_scope(db.query(CorpCampaign), user).filter_by(id=cid).first()
        t = db.query(CorpCampaignTarget).filter_by(id=tid, campaign_id=cid).first()
        if not cp or not t:
            raise HTTPException(404, "Không tìm thấy mục tiêu chiến dịch")
        r = log_sent(db, user, [SentItem(customer_id=t.customer_id, product=cp.product, channel=cp.channel, language=t.language,
                                         subject=t.subject, body=t.body or "", campaign_id=cp.id, target_id=t.id)])
        if r["blocked"]:
            raise HTTPException(409, r["blocked"][0]["reason"])
        audit(user, "campaign.sent", "campaign", cid, t.customer_id, client_ip(request))
        return r
    finally:
        db.close()


class CampaignPatch(BaseModel):
    status: str


@router.patch("/campaigns/{cid}")
def patch_campaign(cid: int, body: CampaignPatch, request: Request, user=Depends(current_user)):
    if body.status not in ("Đang chạy", "Hoàn tất"):
        raise HTTPException(400, "Trạng thái không hợp lệ")
    db = SessionLocal()
    try:
        cp = _camp_scope(db.query(CorpCampaign), user).filter_by(id=cid).first()
        if not cp:
            raise HTTPException(404, "Không tìm thấy chiến dịch")
        cp.status = body.status
        db.commit()
        audit(user, "campaign.status", "campaign", cid, body.status, client_ip(request))
        return {"ok": True}
    finally:
        db.close()


@router.delete("/campaigns/{cid}")
def delete_campaign(cid: int, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        cp = _camp_scope(db.query(CorpCampaign), user).filter_by(id=cid).first()
        if not cp:
            raise HTTPException(404, "Không tìm thấy chiến dịch")
        db.query(CorpCampaignTarget).filter_by(campaign_id=cid).delete()
        db.delete(cp); db.commit()
        audit(user, "campaign.delete", "campaign", cid, cp.name, client_ip(request))
        return {"ok": True}
    finally:
        db.close()
