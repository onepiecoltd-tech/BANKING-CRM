"""Lập luận & truy vết: giải thích vì sao hệ thống chấm điểm / đề xuất như vậy + lịch sử các lần chạy trợ lý."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from src.database import SessionLocal
from src.accounts.deps import current_user
from .models import CorpAgentRun, CorpOptOut, CorpMessage
from .catalog import PRODUCTS
from .access import get_settings, is_admin
from . import scoring
from .router import _get_one

router = APIRouter(prefix="/api/corp", tags=["corporate-reasoning"])

# Quy tắc cảnh báo — hiển thị ngưỡng & giá trị thực tế
def _rules(c, mt):
    util = mt["utilization"]
    d = mt["days_to_expiry"]
    return [
        {"code": "NHOM_NO", "name": "Nhóm nợ", "threshold": "≥ nhóm 2", "actual": f"nhóm {c['debt_group']}", "fired": c["debt_group"] >= 2},
        {"code": "HET_HAN_MUC", "name": "Hạn mức sắp hết hạn", "threshold": "≤ 60 ngày", "actual": (f"{d} ngày" if d is not None else "không có hạn mức"),
         "fired": bool(c["credit_limit_bn"]) and d is not None and d <= 60},
        {"code": "SU_DUNG_CAO", "name": "Sử dụng hạn mức cao", "threshold": "≥ 90%", "actual": (f"{util*100:.0f}%" if util is not None else "không có hạn mức"),
         "fired": util is not None and util >= 0.9},
        {"code": "DOANH_SO_GIAM", "name": "Doanh số qua tài khoản giảm (3T)", "threshold": "≤ −20%", "actual": f"{mt['inflow_trend_3m_pct']:+.1f}%",
         "fired": mt["inflow_trend_3m_pct"] <= -20},
        {"code": "CASA_GIAM", "name": "Số dư CASA giảm", "threshold": "≤ −30%", "actual": (f"{mt['balance_change_pct']:+.1f}%" if mt["balance_change_pct"] is not None else "chưa đủ dữ liệu"),
         "fired": mt["balance_change_pct"] is not None and mt["balance_change_pct"] <= -30},
    ]


@router.get("/reasoning/customer/{cid}")
def explain_customer(cid: str, user=Depends(current_user)):
    db = SessionLocal()
    try:
        c, ms = _get_one(db, cid, user)
        a = scoring.analyze(c, ms)
        mt = a["metrics"]
        cfg = get_settings(db)
        ranked = sorted(a["propensities"].items(), key=lambda kv: -kv[1]["score"])
        best2 = [v["score"] for _, v in ranked[:2] if v["score"] > 0] or [0]
        prop_avg = sum(best2) / len(best2)
        size = {"A": 100, "B": 65, "C": 35}[a["tier"]]
        urgency = min(100, sum(40 if f["severity"] == "high" else 20 for f in a["risk_flags"]))
        wallet = c["loan_outstanding_bn"] + c["deposit_bn"] + c["casa_balance_bn"]
        # kiểm tra tuân thủ khi tiếp cận
        opted = bool(db.query(CorpOptOut).filter_by(customer_id=cid).first())
        last_out = db.query(CorpMessage).filter_by(customer_id=cid, direction="out").order_by(CorpMessage.created_at.desc()).first()
        lc = c.get("last_contact_date")
        if isinstance(lc, str):
            lc = datetime.fromisoformat(lc).date()
        cands = [d for d in (lc, last_out.created_at.date() if last_out else None) if d]
        days_since = (date.today() - max(cands)).days if cands else None
        checks = [
            {"name": "Không nằm trong danh sách từ chối nhận tin", "ok": not opted, "detail": "Đã từ chối" if opted else "Đạt"},
            {"name": f"Nhóm nợ ≤ {cfg['max_debt_group_outreach']}", "ok": c["debt_group"] <= int(cfg["max_debt_group_outreach"]), "detail": f"Nhóm {c['debt_group']}"},
            {"name": f"Giãn cách liên hệ ≥ {cfg['freq_cap_days']} ngày", "ok": days_since is None or days_since >= int(cfg["freq_cap_days"]),
             "detail": f"{days_since} ngày kể từ lần liên hệ cuối" if days_since is not None else "Chưa liên hệ"},
            {"name": "Có thông tin liên hệ", "ok": bool(c.get("contact_phone") or c.get("contact_email")), "detail": "Đạt" if (c.get("contact_phone") or c.get("contact_email")) else "Thiếu"},
        ]
        return {
            "customer": {"customer_id": cid, "name": c["name"], "segment": c["segment"], "ownership": c["ownership"], "industry": c["industry"]},
            "inputs": [
                {"label": "Doanh thu năm", "value": f"{c['annual_revenue_bn']:,.1f} tỷ"}, {"label": "Dư nợ / Hạn mức", "value": f"{c['loan_outstanding_bn']:,.1f} / {c['credit_limit_bn']:,.1f} tỷ"},
                {"label": "CASA bình quân", "value": f"{c['casa_balance_bn']:,.1f} tỷ"}, {"label": "Xuất / Nhập khẩu", "value": f"{c['export_usd_m']:,.1f} / {c['import_usd_m']:,.1f} triệu USD"},
                {"label": "Lao động", "value": f"{c['employees']:,}"}, {"label": "Số năm quan hệ", "value": str(c["relationship_years"])},
            ],
            "metrics": [
                {"label": "Dòng tiền về BQ / tháng", "value": f"{mt['avg_monthly_inflow_bn']:,.1f} tỷ"}, {"label": "Xu hướng dòng tiền 3T", "value": f"{mt['inflow_trend_3m_pct']:+.1f}%"},
                {"label": "Tăng trưởng 6T", "value": f"{mt['inflow_growth_6m_pct']:+.1f}%"}, {"label": "Sử dụng hạn mức", "value": f"{mt['utilization']*100:.0f}%" if mt["utilization"] is not None else "—"},
                {"label": "Ngày đến hạn hạn mức", "value": str(mt["days_to_expiry"]) if mt["days_to_expiry"] is not None else "—"},
                {"label": "Thay đổi số dư", "value": f"{mt['balance_change_pct']:+.1f}%" if mt["balance_change_pct"] is not None else "—"},
            ],
            "rules": _rules(c, mt),
            "propensities": [{"code": k, "name": PRODUCTS[k]["vi"], "score": v["score"], "held": v["held"], "reasons": v["reasons"]} for k, v in ranked],
            "priority": {
                "score": a["priority_score"],
                "parts": [
                    {"label": "Tiềm năng sản phẩm (TB 2 điểm cao nhất)", "weight": 0.60, "value": round(prop_avg, 1), "contribution": round(0.60 * prop_avg, 1)},
                    {"label": f"Quy mô khách hàng (hạng {a['tier']})", "weight": 0.25, "value": size, "contribution": round(0.25 * size, 1),
                     "note": "Hạng A: doanh thu ≥ 800 tỷ hoặc tổng số dư ≥ 150 tỷ; B: ≥ 200 tỷ / ≥ 30 tỷ; còn lại C"},
                    {"label": "Mức khẩn cấp từ cảnh báo", "weight": 0.15, "value": urgency, "contribution": round(0.15 * urgency, 1)},
                ],
                "wallet_bn": round(wallet, 1),
            },
            "decision": a["next_best_action"],
            "compliance": checks,
        }
    finally:
        db.close()


def _run_row(r: CorpAgentRun, full=False):
    d = {"id": r.id, "username": r.username, "query": r.query, "total_matched": r.total_matched, "llm_used": r.llm_used,
         "llm_error": r.llm_error, "created_at": r.created_at.isoformat() + "Z", "step_count": len(r.steps or [])}
    if full:
        d["filters"], d["steps"] = r.filters, r.steps
    return d


@router.get("/reasoning/runs")
def runs(limit: int = Query(30, le=100), user=Depends(current_user)):
    db = SessionLocal()
    try:
        q = db.query(CorpAgentRun).order_by(CorpAgentRun.id.desc())
        if not is_admin(user):
            q = q.filter(CorpAgentRun.username == user.username)
        return {"items": [_run_row(r) for r in q.limit(limit)]}
    finally:
        db.close()


@router.get("/reasoning/runs/{rid}")
def run_detail(rid: int, user=Depends(current_user)):
    db = SessionLocal()
    try:
        r = db.query(CorpAgentRun).filter_by(id=rid).first()
        if not r or (not is_admin(user) and r.username != user.username):
            raise HTTPException(404, "Không tìm thấy lần chạy")
        return _run_row(r, full=True)
    finally:
        db.close()
