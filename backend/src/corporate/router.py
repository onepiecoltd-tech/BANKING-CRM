"""REST API for the corporate edition — mounted at /api/corp."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel

from src.database import SessionLocal
from .models import CorpCustomer, CorpMonthly, CorpInteraction, CorpOpportunity, CorpAgentRun, customer_dict
from .catalog import PRODUCTS, STAGES, STAGE_PROB, INDUSTRIES, TITLES, LANG_NAMES, LIFECYCLES
from . import scoring, messages, agent
from .seed import ensure_seed
from .access import rm_filter, visible_ids, get_customer_or_403, get_settings, is_admin
from src.accounts.deps import current_user, require_admin, client_ip
from src.accounts.service import audit

router = APIRouter(prefix="/api/corp", tags=["corporate"])


# ── helpers ──────────────────────────────────────────────────────────────────
def _load_all(db, user):
    custs = [customer_dict(c) for c in rm_filter(db.query(CorpCustomer), user).all()]
    ids = {c["customer_id"] for c in custs}
    monthly = defaultdict(list)
    for r in db.query(CorpMonthly).all():
        if r.customer_id not in ids:
            continue
        monthly[r.customer_id].append({k: getattr(r, k) for k in ("month", "inflow_bn", "outflow_bn", "trade_usd_m", "avg_balance_bn")})
    return custs, monthly


def _items(db, user):
    custs, monthly = _load_all(db, user)
    return [{"c": c, "a": scoring.analyze(c, monthly[c["customer_id"]])} for c in custs]


def _summary(c, a):
    top = a["top_opportunities"][0] if a["top_opportunities"] else None
    headline = None
    if top:
        headline = f"{top['name']} (điểm {top['score']}) — {top['reasons'][0]}"
    elif a["risk_flags"]:
        headline = a["risk_flags"][0]["text"]
    return {
        "customer_id": c["customer_id"], "name": c["name"], "name_zh": c["name_zh"], "segment": c["segment"],
        "ownership": c["ownership"], "investor_country": c["investor_country"], "industry": c["industry"],
        "province": c["province"], "industrial_zone": c["industrial_zone"], "employees": c["employees"],
        "annual_revenue_bn": c["annual_revenue_bn"], "loan_outstanding_bn": c["loan_outstanding_bn"],
        "casa_balance_bn": c["casa_balance_bn"], "debt_group": c["debt_group"], "tier": a["tier"],
        "priority_score": a["priority_score"], "products_held": c["products_held"],
        "preferred_language": c["preferred_language"], "contact_name": c["contact_name"],
        "lifecycle": c.get("lifecycle") or "prospect", "rm_name": c["rm_name"], "risk_flags": a["risk_flags"], "top_opportunities": a["top_opportunities"],
        "next_best_action": a["next_best_action"], "headline": headline,
        "import_usd_m": c["import_usd_m"], "export_usd_m": c["export_usd_m"],
    }


def _get_one(db, cid, user):
    c = get_customer_or_403(db, user, cid)
    cd = customer_dict(c)
    ms = sorted(({k: getattr(r, k) for k in ("month", "inflow_bn", "outflow_bn", "trade_usd_m", "avg_balance_bn")}
                 for r in db.query(CorpMonthly).filter_by(customer_id=cid)), key=lambda r: r["month"])
    return cd, ms


# ── meta / KPIs ──────────────────────────────────────────────────────────────
@router.get("/meta")
def meta(user=Depends(current_user)):
    db = SessionLocal()
    try:
        cs = db.query(CorpCustomer).all()
        return {
            "products": [{"code": k, **v} for k, v in PRODUCTS.items()],
            "stages": STAGES,
            "segments": ["SME", "Middle", "Large"],
            "industries": sorted({c.industry for c in cs}),
            "provinces": sorted({c.province for c in cs}),
            "countries": sorted({c.investor_country for c in cs if c.investor_country}),
            "languages": LANG_NAMES,
            "lifecycles": [{"code": k, "name": v} for k, v in LIFECYCLES.items()],
            "bank_name": get_settings(db)["bank_name"],
            "rm_names": sorted({c.rm_name for c in cs if c.rm_name}) if is_admin(user) else [user.rm_name],
        }
    finally:
        db.close()


@router.get("/kpis")
def kpis(user=Depends(current_user)):
    db = SessionLocal()
    try:
        items = _items(db, user)
        vis = {it["c"]["customer_id"] for it in items}
        opps = [o for o in db.query(CorpOpportunity).all() if o.customer_id in vis]
        n = len(items)
        cross = Counter()
        for it in items:
            for code, p in it["a"]["propensities"].items():
                if p["score"] >= 60:
                    cross[code] += 1
        flags = Counter(f["code"] for it in items for f in it["a"]["risk_flags"])
        active = [o for o in opps if o.stage not in ("Thất bại", "Triển khai")]
        return {
            "total": n,
            "prospects": sum(1 for it in items if (it["c"].get("lifecycle") or "prospect") == "prospect"),
            "existing": sum(1 for it in items if it["c"].get("lifecycle") == "existing"),
            "fdi": sum(1 for it in items if it["c"]["ownership"] == "FDI"),
            "loans_bn": round(sum(it["c"]["loan_outstanding_bn"] for it in items), 1),
            "casa_bn": round(sum(it["c"]["casa_balance_bn"] for it in items), 1),
            "deposit_bn": round(sum(it["c"]["deposit_bn"] for it in items), 1),
            "trade_usd_m": round(sum(it["c"]["export_usd_m"] + it["c"]["import_usd_m"] for it in items), 1),
            "tier": dict(Counter(it["a"]["tier"] for it in items)),
            "segments": dict(Counter(it["c"]["segment"] for it in items)),
            "countries": dict(Counter(it["c"]["investor_country"] or "Nội địa" for it in items)),
            "industries": dict(Counter(it["c"]["industry"] for it in items).most_common()),
            "provinces": dict(Counter(it["c"]["province"] for it in items).most_common()),
            "crosssell": [{"code": k, "name": PRODUCTS[k]["vi"], "count": v} for k, v in cross.most_common()],
            "flags": dict(flags),
            "pipeline_count": len(active),
            "pipeline_value_bn": round(sum(o.expected_amount_bn for o in active), 1),
            "pipeline_weighted_bn": round(sum(o.expected_amount_bn * o.probability / 100 for o in active), 1),
        }
    finally:
        db.close()


@router.get("/signals")
def signals(limit: int = 8, user=Depends(current_user)):
    """Việc cần làm hôm nay: hạn mức sắp hết hạn, doanh số giảm, nợ nhóm ≥2, sử dụng hạn mức cao."""
    db = SessionLocal()
    try:
        items = _items(db, user)
        out = {}
        for code, key in [("HET_HAN_MUC", "limit_expiry"), ("DOANH_SO_GIAM", "inflow_drop"),
                          ("NHOM_NO", "debt"), ("SU_DUNG_CAO", "high_util"), ("CASA_GIAM", "casa_drop")]:
            rows = []
            for it in items:
                fl = next((f for f in it["a"]["risk_flags"] if f["code"] == code), None)
                if fl:
                    rows.append({"customer_id": it["c"]["customer_id"], "name": it["c"]["name"], "tier": it["a"]["tier"],
                                 "severity": fl["severity"], "text": fl["text"], "rm_name": it["c"]["rm_name"]})
            rows.sort(key=lambda r: (r["severity"] != "high", r["tier"]))
            out[key] = {"count": len(rows), "items": rows[:limit]}
        return out
    finally:
        db.close()


# ── customers ────────────────────────────────────────────────────────────────
@router.get("/customers")
def list_customers(
    q: Optional[str] = None, segment: Optional[str] = None, ownership: Optional[str] = None,
    country: Optional[str] = None, industry: Optional[str] = None, province: Optional[str] = None,
    tier: Optional[str] = None, product: Optional[str] = None, risk: Optional[str] = None,
    sort: str = "priority", limit: int = Query(50, le=500), offset: int = 0, rm: Optional[str] = None,
    lifecycle: Optional[str] = None,
    user=Depends(current_user),
):
    db = SessionLocal()
    try:
        items = _items(db, user)
        ql = (q or "").lower()
        res = []
        for it in items:
            c, a = it["c"], it["a"]
            if ql and ql not in c["name"].lower() and ql not in (c["name_zh"] or "") and ql not in c["tax_code"] and ql not in c["customer_id"].lower():
                continue
            if rm and c["rm_name"] != rm: continue
            if lifecycle and (c.get("lifecycle") or "prospect") != lifecycle: continue
            if segment and c["segment"] != segment: continue
            if ownership and c["ownership"] != ownership: continue
            if country and c["investor_country"] != country: continue
            if industry and c["industry"] != industry: continue
            if province and c["province"] != province: continue
            if tier and a["tier"] != tier: continue
            if product and a["propensities"].get(product, {}).get("score", 0) < 60: continue
            if risk and not any(f["code"] == risk for f in a["risk_flags"]): continue
            res.append(it)
        keyf = {
            "priority": lambda it: -it["a"]["priority_score"],
            "revenue": lambda it: -it["c"]["annual_revenue_bn"],
            "loan": lambda it: -it["c"]["loan_outstanding_bn"],
            "name": lambda it: it["c"]["name"],
        }.get(sort, lambda it: -it["a"]["priority_score"])
        res.sort(key=keyf)
        return {"total": len(res), "limit": limit, "offset": offset,
                "items": [_summary(it["c"], it["a"]) for it in res[offset:offset + limit]]}
    finally:
        db.close()


@router.get("/customers/{cid}")
def customer_detail(cid: str, user=Depends(current_user)):
    db = SessionLocal()
    try:
        c, ms = _get_one(db, cid, user)
        a = scoring.analyze(c, ms)
        inter = [{"date": r.date.isoformat(), "channel": r.channel, "summary": r.summary, "outcome": r.outcome}
                 for r in db.query(CorpInteraction).filter_by(customer_id=cid).order_by(CorpInteraction.date.desc())]
        opps = [_opp(o) for o in db.query(CorpOpportunity).filter_by(customer_id=cid)]
        return {"customer": c, "monthly": ms, "analysis": a,
                "products": {k: v for k, v in PRODUCTS.items()}, "interactions": inter, "opportunities": opps}
    finally:
        db.close()


class InteractionIn(BaseModel):
    channel: str = "Điện thoại"
    summary: str
    outcome: Optional[str] = None


@router.post("/customers/{cid}/interactions")
def add_interaction(cid: str, body: InteractionIn, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        c = get_customer_or_403(db, user, cid)
        db.add(CorpInteraction(customer_id=cid, date=date.today(), channel=body.channel, summary=body.summary, outcome=body.outcome))
        c.last_contact_date = date.today()
        db.commit()
        audit(user, "interaction.add", "customer", cid, body.channel, client_ip(request))
        return {"ok": True}
    finally:
        db.close()


class DraftIn(BaseModel):
    product: str
    channel: str = "zalo"            # zalo | email | call
    language: Optional[str] = None   # vi | zh | en (mặc định theo khách hàng)
    rm_name: str = "Chuyên viên QHKH"
    bank_name: Optional[str] = None


@router.post("/customers/{cid}/draft")
def make_draft(cid: str, body: DraftIn, user=Depends(current_user)):
    if body.product not in PRODUCTS:
        raise HTTPException(400, "Sản phẩm không hợp lệ")
    if body.channel not in ("zalo", "email", "call"):
        raise HTTPException(400, "Kênh không hợp lệ")
    db = SessionLocal()
    try:
        c, ms = _get_one(db, cid, user)
        return messages.draft(c, scoring.metrics(c, ms), body.product, body.channel, body.language,
                              body.rm_name if body.rm_name != "Chuyên viên QHKH" else user.full_name,
                              body.bank_name or get_settings(db)["bank_name"])
    finally:
        db.close()


# ── pipeline ─────────────────────────────────────────────────────────────────
def _opp(o: CorpOpportunity, name: str | None = None):
    return {"id": o.id, "customer_id": o.customer_id, "customer_name": name, "product": o.product,
            "product_name": PRODUCTS[o.product]["vi"], "stage": o.stage, "expected_amount_bn": o.expected_amount_bn,
            "probability": o.probability, "next_action": o.next_action,
            "due_date": o.due_date.isoformat() if o.due_date else None}


@router.get("/opportunities")
def list_opps(user=Depends(current_user)):
    db = SessionLocal()
    try:
        names = {c.customer_id: c.name for c in rm_filter(db.query(CorpCustomer.customer_id, CorpCustomer.name, CorpCustomer.rm_name), user)}
        rows = [_opp(o, names.get(o.customer_id)) for o in db.query(CorpOpportunity).order_by(CorpOpportunity.updated_at.desc())
                if o.customer_id in names]
        by = {s: [r for r in rows if r["stage"] == s] for s in STAGES}
        return {"stages": STAGES, "by_stage": by,
                "totals": {s: round(sum(r["expected_amount_bn"] for r in by[s]), 1) for s in STAGES}}
    finally:
        db.close()


class OppIn(BaseModel):
    customer_id: str
    product: str
    expected_amount_bn: Optional[float] = None
    next_action: Optional[str] = None


@router.post("/opportunities")
def create_opp(body: OppIn, request: Request, user=Depends(current_user)):
    if body.product not in PRODUCTS:
        raise HTTPException(400, "Sản phẩm không hợp lệ")
    db = SessionLocal()
    try:
        c, ms = _get_one(db, body.customer_id, user)
        amt = body.expected_amount_bn
        if amt is None:
            amt = scoring.expected_amount_bn(body.product, c, scoring.metrics(c, ms))
        o = CorpOpportunity(customer_id=body.customer_id, product=body.product, stage="Tiếp cận", probability=STAGE_PROB["Tiếp cận"],
                            expected_amount_bn=amt, next_action=body.next_action or "Liên hệ lần đầu",
                            due_date=date.today() + timedelta(days=7))
        db.add(o); db.commit(); db.refresh(o)
        audit(user, "opportunity.create", "customer", body.customer_id, body.product, client_ip(request))
        return _opp(o, c["name"])
    finally:
        db.close()


class OppPatch(BaseModel):
    stage: Optional[str] = None
    next_action: Optional[str] = None
    expected_amount_bn: Optional[float] = None


@router.patch("/opportunities/{oid}")
def patch_opp(oid: int, body: OppPatch, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        o = db.query(CorpOpportunity).filter_by(id=oid).first()
        if not o:
            raise HTTPException(404, "Không tìm thấy cơ hội")
        get_customer_or_403(db, user, o.customer_id)
        if body.stage:
            if body.stage not in STAGES:
                raise HTTPException(400, "Giai đoạn không hợp lệ")
            o.stage = body.stage
            o.probability = STAGE_PROB[body.stage]
        if body.next_action is not None:
            o.next_action = body.next_action
        if body.expected_amount_bn is not None:
            o.expected_amount_bn = body.expected_amount_bn
        o.updated_at = datetime.utcnow()
        db.commit()
        audit(user, "opportunity.update", "opportunity", oid, f"{body.stage or ''} {body.next_action or ''}".strip(), client_ip(request))
        return _opp(o)
    finally:
        db.close()


# ── assistant ────────────────────────────────────────────────────────────────
class AgentIn(BaseModel):
    query: str
    use_llm: bool = True
    rm_name: str = "Chuyên viên QHKH"


@router.post("/agent")
def run_agent(body: AgentIn, user=Depends(current_user)):
    if not body.query.strip():
        raise HTTPException(400, "Câu hỏi trống")
    db = SessionLocal()
    try:
        cfg = get_settings(db)
        body.use_llm = body.use_llm and bool(cfg["llm_enabled"])
        if body.rm_name == "Chuyên viên QHKH":
            body.rm_name = user.full_name
        steps = []
        f = agent.parse_query(body.query)
        steps.append({"step": "Phân tích yêu cầu", "detail": "; ".join(agent.describe_filters(f))})
        items = _items(db, user)
        steps.append({"step": "Truy vấn danh mục khách hàng DN", "detail": f"{len(items)} khách hàng"})
        matched = agent.apply(f, items)
        steps.append({"step": "Lọc & xếp hạng", "detail": f"{len(matched)} khách hàng phù hợp" + (f" · xếp theo điểm {PRODUCTS[f['product']]['vi']}" if f["product"] else " · xếp theo điểm ưu tiên")})
        shown_items = matched[: f["limit"]]
        shown = []
        for it in shown_items:
            s = _summary(it["c"], it["a"])
            if f["product"]:
                p = it["a"]["propensities"][f["product"]]
                s["product_score"] = p["score"]
                s["headline"] = f"{PRODUCTS[f['product']]['vi']} — điểm {p['score']}: " + "; ".join(p["reasons"][:2])
            shown.append(s)
        drafts = []
        if f["draft"] and shown_items:
            for it in shown_items[:5]:
                code = f["product"] or (it["a"]["top_opportunities"][0]["product"] if it["a"]["top_opportunities"] else None)
                if not code:
                    continue
                try:
                    drafts.append(messages.draft(it["c"], it["a"]["metrics"], code, f["channel"], f["language"], body.rm_name, cfg["bank_name"])
                                  | {"customer_name": it["c"]["name"]})
                except KeyError:
                    continue
            steps.append({"step": "Soạn nội dung tiếp cận", "detail": f"{len(drafts)} bản nháp ({f['channel']}, {f['language'] or 'theo ngôn ngữ khách hàng'})"})
        answer = agent.template_answer(f, len(matched), shown)
        llm_used, llm_error = False, None
        if body.use_llm and shown:
            text, err = agent.llm_summary(body.query, f, len(matched), shown)
            if text:
                answer, llm_used = text, True
            llm_error = err
            steps.append({"step": "Tổng hợp bằng LLM", "detail": "Hoàn tất" if llm_used else f"Dùng tóm tắt mặc định ({llm_error or 'không có phản hồi'})"})
        run = CorpAgentRun(username=user.username, query=body.query[:1000], filters=f, steps=steps, total_matched=len(matched),
                           llm_used=llm_used, llm_error=llm_error)
        db.add(run); db.commit()
        return {"query": body.query, "filters": f, "steps": steps, "total_matched": len(matched), "customers": shown,
                "drafts": drafts, "answer": answer, "llm_used": llm_used, "llm_error": llm_error, "run_id": run.id}
    finally:
        db.close()
