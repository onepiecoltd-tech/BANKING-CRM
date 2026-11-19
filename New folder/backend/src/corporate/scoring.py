"""Rule-based opportunity scoring, risk flags and tiering for corporate customers.

Everything is explainable: each propensity comes with Vietnamese reasons the RM can read."""
from datetime import date, datetime
from .catalog import PRODUCTS, GUARANTEE_INDUSTRIES, CAPEX_INDUSTRIES

USD_VND_BN = 25.4  # 1 triệu USD ≈ 25,4 tỷ đồng (tỷ giá minh hoạ)


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def _days_to(d):
    if not d:
        return None
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    return (d - date.today()).days


def metrics(c: dict, monthly: list) -> dict:
    """Derived numbers used by scoring, messages and the UI."""
    m = sorted(monthly, key=lambda r: r["month"])
    inflows = [r["inflow_bn"] for r in m]
    last3 = sum(inflows[-3:]) / 3 if len(inflows) >= 3 else 0
    prev3 = sum(inflows[-6:-3]) / 3 if len(inflows) >= 6 else 0
    first6 = sum(inflows[:6]) / 6 if len(inflows) >= 12 else 0
    last6 = sum(inflows[-6:]) / 6 if len(inflows) >= 6 else 0
    util = (c["loan_outstanding_bn"] / c["credit_limit_bn"]) if c["credit_limit_bn"] else None
    bal = [r["avg_balance_bn"] for r in m]
    bal_drop = None
    if len(bal) >= 6 and sum(bal[:-2]) > 0:
        base = sum(bal[:-2]) / len(bal[:-2])
        bal_drop = (sum(bal[-2:]) / 2 - base) / base if base else None
    return {
        "avg_monthly_inflow_bn": round(sum(inflows) / len(inflows), 2) if inflows else 0,
        "inflow_trend_3m_pct": round((last3 - prev3) / prev3 * 100, 1) if prev3 else 0.0,
        "inflow_growth_6m_pct": round((last6 - first6) / first6 * 100, 1) if first6 else 0.0,
        "utilization": round(util, 3) if util is not None else None,
        "days_to_expiry": _days_to(c.get("limit_expiry")),
        "balance_change_pct": round(bal_drop * 100, 1) if bal_drop is not None else None,
        "trade_usd_m": round(c["export_usd_m"] + c["import_usd_m"], 2),
    }


def propensities(c: dict, mt: dict) -> dict:
    """product_code -> {score, held, reasons[]}"""
    held = set(c.get("products_held") or [])
    imp, exp, fx = c["import_usd_m"], c["export_usd_m"], c["fx_exposure_usd_m"]
    rev, emp = c["annual_revenue_bn"], c["employees"]
    out = {}

    def put(code, score, reasons, is_held=None):
        out[code] = {
            "score": int(_clip(round(score))),
            "held": code in held if is_held is None else is_held,
            "reasons": reasons,
        }

    healthy = c["debt_group"] == 1
    pen = 0 if healthy else 40
    notes_pen = [] if healthy else [f"Nợ nhóm {c['debt_group']} — cần thẩm định thận trọng"]

    # Vay vốn lưu động (mới / tăng hạn mức / gia hạn)
    r, s = [], 20
    if "VAY_VLD" in held:
        u, d = mt["utilization"], mt["days_to_expiry"]
        s = 25
        if u is not None and u >= 0.85:
            s += 45; r.append(f"Sử dụng hạn mức {u*100:.0f}% — nhu cầu tăng hạn mức")
        if d is not None and d <= 90:
            s += 35; r.append(f"Hạn mức hết hạn sau {d} ngày — cần gia hạn/tái cấp" if d >= 0 else f"Hạn mức đã quá hạn {-d} ngày — cần xử lý ngay")
        if not r:
            r.append("Đang dùng hạn mức, chưa có tín hiệu cần điều chỉnh")
        put("VAY_VLD", s - pen * 0.7, r + notes_pen, is_held=True)
    else:
        if mt["inflow_growth_6m_pct"] > 10:
            s += 30; r.append(f"Doanh số qua tài khoản tăng {mt['inflow_growth_6m_pct']:.0f}% (6T gần nhất)")
        if rev >= 150:
            s += 15; r.append(f"Doanh thu ~{rev:,.0f} tỷ đồng/năm — quy mô phù hợp vay VLĐ")
        if c["loan_outstanding_bn"] == 0:
            s += 10; r.append("Chưa có dư nợ tại ngân hàng — dư địa lớn")
        put("VAY_VLD", s - pen, (r or ["Chưa có tín hiệu rõ"]) + notes_pen, is_held=False)

    # Vay đầu tư
    r, s = [], 15
    if c["industry"] in CAPEX_INDUSTRIES:
        s += 20; r.append(f"Ngành {c['industry']} có nhu cầu đầu tư mở rộng")
    if c["equity_bn"] >= 100:
        s += 15; r.append(f"Vốn chủ sở hữu ~{c['equity_bn']:,.0f} tỷ — đủ năng lực đối ứng")
    if mt["inflow_growth_6m_pct"] > 15:
        s += 20; r.append("Doanh số tăng mạnh — khả năng mở rộng công suất")
    if c["ownership"] == "FDI" and c["relationship_years"] >= 3:
        s += 10; r.append("FDI gắn bó >3 năm — thường mở rộng nhà máy theo giai đoạn")
    put("VAY_DT", s - pen, (r or ["Chưa có tín hiệu rõ"]) + notes_pen)

    # L/C nhập khẩu
    r, s = [], 0
    if imp >= 1:
        s = 35 + min(40, imp * 3); r.append(f"Nhập khẩu ~{imp:.1f} triệu USD/năm")
        if exp > 0:
            s += 5
    put("LC", s, r or ["Kim ngạch nhập khẩu thấp"])

    # UPAS
    r, s = [], 0
    if imp >= 3:
        s = 30 + min(45, imp * 2.5); r.append(f"Nhập khẩu ~{imp:.1f} triệu USD/năm — cần tài trợ trả chậm chi phí thấp")
        if "LC" in held:
            s += 10; r.append("Đã dùng L/C — chuyển sang UPAS để tối ưu chi phí vốn")
    put("UPAS", s - pen * 0.5, r or ["Kim ngạch nhập khẩu chưa đủ lớn cho UPAS"])

    # Bảo lãnh
    r, s = [], 15
    if c["industry"] in GUARANTEE_INDUSTRIES:
        s += 30; r.append(f"Ngành {c['industry']} thường cần bảo lãnh (dự thầu/thực hiện HĐ/thanh toán)")
    if rev >= 200:
        s += 20; r.append("Quy mô doanh thu đủ lớn để nhận hợp đồng có yêu cầu bảo lãnh")
    if c["credit_limit_bn"] > 0:
        s += 10; r.append("Đã có hạn mức tín dụng — có thể cấp hạn mức bảo lãnh kèm theo")
    put("BAO_LANH", s - pen * 0.5, (r or ["Chưa có tín hiệu rõ"]) + notes_pen)

    # TTQT
    r, s = [], 0
    if exp + imp >= 0.5:
        s = 30 + min(50, (exp + imp) * 2); r.append(f"Kim ngạch XNK ~{exp+imp:.1f} triệu USD/năm")
    put("TTQT", s, r or ["Kim ngạch XNK thấp"])

    # Ngoại tệ
    r, s = [], 0
    if fx >= 1.5:
        s = 35 + min(45, fx * 4); r.append(f"Trạng thái ngoại tệ ~{fx:.1f} triệu USD — rủi ro tỷ giá")
        if "TTQT" in held:
            s += 5
    put("NGOAI_TE", s, r or ["Rủi ro tỷ giá nhỏ"])

    # Lương
    r, s = [], 0
    if emp >= 50:
        s = 30 + min(55, emp / 15); r.append(f"{emp:,} lao động — chi lương qua ngân hàng")
        if c["ownership"] == "FDI" and emp >= 300:
            s += 8; r.append("FDI quy mô lớn: cơ hội thẻ lương + tín dụng cá nhân cho công nhân")
    put("LUONG", s, r or ["Số lao động ít"])

    # Quản lý dòng tiền
    r, s = [], 0
    inflow = mt["avg_monthly_inflow_bn"]
    if inflow >= 5:
        s = 30 + min(45, inflow / 3); r.append(f"Dòng tiền về ~{inflow:,.1f} tỷ/tháng — phù hợp thu hộ/chi hộ tự động")
    put("DONG_TIEN", s, r or ["Dòng tiền chưa lớn"])

    # Tiền gửi
    r, s = [], 0
    if c["casa_balance_bn"] >= 5:
        s = 25 + min(55, c["casa_balance_bn"] * 1.2); r.append(f"CASA bình quân ~{c['casa_balance_bn']:,.1f} tỷ — có thể chuyển một phần sang gửi có kỳ hạn")
    put("TIEN_GUI", s, r or ["Số dư chưa đáng kể"])

    for code, v in out.items():
        if v["held"] and code != "VAY_VLD":
            v["score"] = 0
            v["reasons"] = ["Khách hàng đang sử dụng"]
    return out


def risk_flags(c: dict, mt: dict) -> list:
    flags = []
    if c["debt_group"] >= 2:
        flags.append({"code": "NHOM_NO", "severity": "high" if c["debt_group"] >= 3 else "medium",
                      "text": f"Nợ nhóm {c['debt_group']}"})
    d = mt["days_to_expiry"]
    if c["credit_limit_bn"] and d is not None and d <= 60:
        flags.append({"code": "HET_HAN_MUC", "severity": "high" if d <= 30 else "medium",
                      "text": f"Hạn mức hết hạn sau {d} ngày" if d >= 0 else f"Hạn mức quá hạn {-d} ngày"})
    if mt["utilization"] is not None and mt["utilization"] >= 0.9:
        flags.append({"code": "SU_DUNG_CAO", "severity": "medium", "text": f"Sử dụng hạn mức {mt['utilization']*100:.0f}%"})
    if mt["inflow_trend_3m_pct"] <= -20:
        flags.append({"code": "DOANH_SO_GIAM", "severity": "high" if mt["inflow_trend_3m_pct"] <= -35 else "medium",
                      "text": f"Doanh số qua tài khoản giảm {abs(mt['inflow_trend_3m_pct']):.0f}% (3T gần nhất)"})
    if mt["balance_change_pct"] is not None and mt["balance_change_pct"] <= -30:
        flags.append({"code": "CASA_GIAM", "severity": "medium", "text": f"Số dư CASA giảm {abs(mt['balance_change_pct']):.0f}% — nguy cơ chuyển dòng tiền sang ngân hàng khác"})
    return flags


def tier(c: dict) -> str:
    wallet = c["loan_outstanding_bn"] + c["deposit_bn"] + c["casa_balance_bn"]
    if c["annual_revenue_bn"] >= 800 or wallet >= 150:
        return "A"
    if c["annual_revenue_bn"] >= 200 or wallet >= 30:
        return "B"
    return "C"


def expected_amount_bn(code: str, c: dict, mt: dict) -> float:
    rev = c["annual_revenue_bn"]
    f = {
        "VAY_VLD": max(5, rev * 0.08),
        "VAY_DT": max(10, c["equity_bn"] * 0.4),
        "LC": c["import_usd_m"] * USD_VND_BN / 4,
        "UPAS": c["import_usd_m"] * USD_VND_BN / 4 * 0.8,
        "BAO_LANH": max(3, rev * 0.05),
        "TTQT": (c["export_usd_m"] + c["import_usd_m"]) * USD_VND_BN / 12,
        "NGOAI_TE": c["fx_exposure_usd_m"] * USD_VND_BN * 0.5,
        "LUONG": c["employees"] * 0.009 * 3,
        "DONG_TIEN": mt["avg_monthly_inflow_bn"] * 0.5,
        "TIEN_GUI": c["casa_balance_bn"] * 0.4,
    }[code]
    return round(f, 1)


def analyze(c: dict, monthly: list) -> dict:
    mt = metrics(c, monthly)
    props = propensities(c, mt)
    flags = risk_flags(c, mt)
    ranked = sorted(
        [(k, v) for k, v in props.items() if v["score"] > 0],
        key=lambda kv: kv[1]["score"], reverse=True,
    )
    top = [{"product": k, "name": PRODUCTS[k]["vi"], "score": v["score"], "reasons": v["reasons"],
            "expected_amount_bn": expected_amount_bn(k, c, mt)} for k, v in ranked[:3] if v["score"] >= 50]
    t = tier(c)
    size = {"A": 100, "B": 65, "C": 35}[t]
    urgency = min(100, sum(40 if f["severity"] == "high" else 20 for f in flags))
    best2 = [v["score"] for _, v in ranked[:2]] or [0]
    priority = round(0.6 * (sum(best2) / len(best2)) + 0.25 * size + 0.15 * urgency, 1)
    nba = None
    if top:
        nba = {"product": top[0]["product"], "name": top[0]["name"], "why": "; ".join(top[0]["reasons"][:2])}
    elif flags:
        nba = {"product": None, "name": "Xử lý cảnh báo", "why": flags[0]["text"]}
    return {
        "tier": t,
        "metrics": mt,
        "propensities": props,
        "top_opportunities": top,
        "risk_flags": flags,
        "priority_score": priority,
        "next_best_action": nba,
        "wallet_share_pct": round(len(c.get("products_held") or []) / len(PRODUCTS) * 100),
    }
