"""Phân tích số liệu bản DN: phễu tiếp cận, tỷ lệ phản hồi, rủi ro, bán chéo, pipeline, hiệu quả theo cán bộ (Admin)."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from src.database import SessionLocal
from src.accounts.deps import current_user
from .models import CorpMessage, CorpOpportunity, CorpInteraction, CorpCampaignTarget, CorpCampaign
from .catalog import PRODUCTS, STAGES
from .access import is_admin
from .router import _items
from .outreach import _camp_row, _camp_scope, TARGET_STATUS

router = APIRouter(prefix="/api/corp", tags=["corporate-analytics"])

WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def _rate(a, b):
    return round(a / b * 100) if b else 0


@router.get("/analytics")
def analytics(user=Depends(current_user)):
    db = SessionLocal()
    try:
        items = _items(db, user)
        by_id = {it["c"]["customer_id"]: it for it in items}
        vis = set(by_id)
        msgs = [m for m in db.query(CorpMessage).order_by(CorpMessage.created_at) if m.customer_id in vis]
        contacted = {m.customer_id for m in msgs if m.direction == "out"}
        replied = {m.customer_id for m in msgs if m.direction == "in"}
        interested = {m.customer_id for m in msgs if m.direction == "in" and m.intent in ("interested", "meeting", "docs")}
        opps = [o for o in db.query(CorpOpportunity).all() if o.customer_id in vis]
        won = {o.customer_id for o in opps if o.stage == "Triển khai"}
        tg = [t for t in db.query(CorpCampaignTarget).all() if t.customer_id in vis]
        won |= {t.customer_id for t in tg if t.status == "Chuyển đổi"}

        # tỷ lệ phản hồi theo nhóm
        def grp(keyf):
            ct, rp = Counter(), Counter()
            for cid in contacted:
                k = keyf(by_id[cid]["c"]) or "Khác"
                ct[k] += 1
                if cid in replied:
                    rp[k] += 1
            return [{"name": k, "contacted": n, "replied": rp[k], "rate": _rate(rp[k], n)} for k, n in ct.most_common(8)]

        # theo thứ trong tuần: tin đi có phản hồi trong 7 ngày
        wd_out, wd_hit = Counter(), Counter()
        per = defaultdict(list)
        for m in msgs:
            per[m.customer_id].append(m)
        for cid, ms in per.items():
            for i, m in enumerate(ms):
                if m.direction != "out":
                    continue
                wd = m.created_at.weekday()
                wd_out[wd] += 1
                if any(x.direction == "in" and x.created_at > m.created_at and (x.created_at - m.created_at).days <= 7 for x in ms[i + 1:]):
                    wd_hit[wd] += 1
        weekday = [{"name": WEEKDAYS[i], "sent": wd_out[i], "replied": wd_hit[i], "rate": _rate(wd_hit[i], wd_out[i])} for i in range(7)]

        # rủi ro
        risk = Counter()
        for it in items:
            sev = {f["severity"] for f in it["a"]["risk_flags"]}
            risk["Cao" if "high" in sev else "Trung bình" if "medium" in sev else "Thấp"] += 1
        flags = Counter(f["code"] for it in items for f in it["a"]["risk_flags"])
        cross = Counter()
        for it in items:
            for code, p in it["a"]["propensities"].items():
                if p["score"] >= 60 and not p["held"]:
                    cross[code] += 1

        # pipeline
        pipe = []
        for s in STAGES:
            os_ = [o for o in opps if o.stage == s]
            pipe.append({"stage": s, "count": len(os_), "value_bn": round(sum(o.expected_amount_bn for o in os_), 1)})
        closed = [o for o in opps if o.stage in ("Triển khai", "Thất bại")]
        win_rate = _rate(sum(1 for o in closed if o.stage == "Triển khai"), len(closed))

        # hoạt động theo tháng (6 tháng)
        today = date.today()
        months = []
        y, m_ = today.year, today.month
        for _ in range(6):
            months.append(f"{y}-{m_:02d}")
            m_ -= 1
            if m_ == 0:
                y, m_ = y - 1, 12
        months.reverse()
        act = Counter()
        for r in db.query(CorpInteraction).all():
            if r.customer_id in vis:
                act[r.date.strftime("%Y-%m")] += 1
        activity = [{"month": mo, "interactions": act[mo]} for mo in months]

        camps = [_camp_row(db, cp) for cp in _camp_scope(db.query(CorpCampaign), user).order_by(CorpCampaign.id.desc()).limit(8)]

        out = {
            "kpis": {
                "customers": len(items), "contacted": len(contacted), "replied": len(replied), "reply_rate": _rate(len(replied & contacted), len(contacted)),
                "interested": len(interested), "converted": len(won), "conv_rate": _rate(len(won & contacted), len(contacted)),
                "at_risk": risk["Cao"], "crosssell": sum(cross.values()), "win_rate": win_rate,
            },
            "reply_by_segment": grp(lambda c: c["segment"]),
            "reply_by_country": grp(lambda c: c["investor_country"] or "Nội địa"),
            "reply_by_industry": grp(lambda c: c["industry"]),
            "reply_by_weekday": weekday,
            "funnel": [{"stage": "Đã tiếp cận", "value": len(contacted)}, {"stage": "Phản hồi", "value": len(replied & contacted)},
                       {"stage": "Quan tâm", "value": len(interested & contacted)}, {"stage": "Chuyển đổi", "value": len(won & contacted)}],
            "risk": [{"name": k, "value": risk[k]} for k in ("Cao", "Trung bình", "Thấp")],
            "flags": [{"code": k, "value": v} for k, v in flags.most_common()],
            "crosssell": [{"code": k, "name": PRODUCTS[k]["vi"], "value": v} for k, v in cross.most_common()],
            "pipeline": pipe, "activity": activity, "campaigns": camps,
        }
        if is_admin(user):
            rm = defaultdict(lambda: {"customers": 0, "loan_bn": 0.0, "casa_bn": 0.0, "tier_a": 0, "risk_high": 0, "pipeline_bn": 0.0, "weighted_bn": 0.0, "touches_30d": 0})
            for it in items:
                r = rm[it["c"]["rm_name"] or "Chưa giao"]
                r["customers"] += 1; r["loan_bn"] += it["c"]["loan_outstanding_bn"]; r["casa_bn"] += it["c"]["casa_balance_bn"]
                r["tier_a"] += it["a"]["tier"] == "A"
                r["risk_high"] += any(f["severity"] == "high" for f in it["a"]["risk_flags"])
            for o in opps:
                if o.stage not in ("Triển khai", "Thất bại"):
                    r = rm[by_id[o.customer_id]["c"]["rm_name"] or "Chưa giao"]
                    r["pipeline_bn"] += o.expected_amount_bn; r["weighted_bn"] += o.expected_amount_bn * o.probability / 100
            since = today - timedelta(days=30)
            for r_ in db.query(CorpInteraction).filter(CorpInteraction.date >= since):
                if r_.customer_id in by_id:
                    rm[by_id[r_.customer_id]["c"]["rm_name"] or "Chưa giao"]["touches_30d"] += 1
            out["rm_performance"] = sorted(
                [{"rm": k, **{kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()}} for k, v in rm.items()],
                key=lambda r: -r["customers"])
        return out
    finally:
        db.close()
