"""Seed ~220 synthetic Vietnamese corporate customers (domestic + FDI). Idempotent: only seeds an empty table.

All names/numbers are fictional (dữ liệu mô phỏng)."""
import os
import random
from datetime import date, timedelta

from src.database import SessionLocal, engine, Base
from .models import CorpCustomer, CorpMonthly, CorpInteraction, CorpOpportunity, CorpSetting
from .catalog import INDUSTRIES, LOCATIONS, FDI_COUNTRIES, PRODUCTS, STAGES, STAGE_PROB
from . import scoring

N_CUSTOMERS = 220

BRANDS_VI = ["Phú Hưng", "Thành Công", "Đại Dương", "Hoàng Gia", "Minh Long", "An Phát", "Việt Tiến", "Sao Mai",
             "Tân Thành", "Hòa Bình", "Bảo Minh", "Kim Long", "Thiên Phú", "Nam Việt", "Hưng Thịnh", "Đông Á",
             "Trường Sơn", "Lạc Hồng", "Phước Thành", "Vạn Phát", "Gia Bảo", "Tín Nghĩa", "Hải Âu", "Thái Bình",
             "Quang Minh", "Đại Phát", "Long Hải", "Tiến Đạt", "Mỹ Phong", "Kim Đồng", "Sài Gòn Xanh", "Cửu Long",
             "Đồng Tâm", "Hiệp Phước", "Tây Nam", "Phương Nam", "Nhất Thống", "Ánh Dương", "Vĩnh Tiến", "Bình Minh"]
LEGAL = ["Công ty TNHH", "Công ty Cổ phần", "Công ty TNHH MTV"]

FDI_BRANDS = {
    "Trung Quốc": [("Hongfa", "宏发"), ("Jiahua", "嘉华"), ("Dongfang Precision", "东方精密"), ("Huaxin", "华新"),
                   ("Zhongtai", "中泰"), ("Yuanda", "远大"), ("Mingyang", "明阳"), ("Fuhua", "富华"),
                   ("Kangda", "康达"), ("Lixin", "立信"), ("Shengda", "盛达"), ("Tianli", "天力"),
                   ("Ruixiang", "瑞祥"), ("Hengtong", "恒通"), ("Xinbao", "鑫宝"), ("Yongsheng", "永盛")],
    "Đài Loan": [("Fuxing", "福兴"), ("Yongfeng", "永丰"), ("Taihe", "泰和"), ("Chenghui", "成辉"),
                 ("Dahua", "大华"), ("Jinxing", "金兴"), ("Hongxin", "鸿信"), ("Weicheng", "伟诚"),
                 ("Zhenyu", "振裕"), ("Kaixuan", "凯旋")],
    "Hàn Quốc": [("Samil Tech", ""), ("Daehan Industry", ""), ("Hyunwoo Vina", ""), ("Jinyoung", ""),
                 ("Sunil Vina", ""), ("Haneul", ""), ("Daeyang", ""), ("Miraeco", "")],
    "Nhật Bản": [("Nishio Kogyo", ""), ("Hoshino Denki", ""), ("Takumi Precision", ""), ("Asahikawa Seiko", ""),
                 ("Fujimori", ""), ("Kitamura Plastics", ""), ("Sakaeya", "")],
    "Singapore": [("Eastbridge", ""), ("Straits Pacific", ""), ("Lion Harbour", ""), ("Orchid Logistics", "")],
}
ZH_SURN = [("Zhang", "张"), ("Li", "李"), ("Wang", "王"), ("Chen", "陈"), ("Lin", "林"),
           ("Huang", "黄"), ("Wu", "吴"), ("Liu", "刘"), ("Zhou", "周"), ("Yang", "杨")]
ZH_GIVEN = [("Wei", "伟"), ("Jun", "俊"), ("Hao", "浩"), ("Ming", "明"), ("Jing", "静"),
            ("Lei", "磊"), ("Qiang", "强"), ("Yan", "燕"), ("Jie", "杰"), ("Peng", "鹏")]
EN_NAMES = ["Kim Min-jun", "Park Ji-ho", "Tanaka Hiroshi", "Sato Kenji", "Lee Sung-min", "Tan Wei Ming", "Lim Chee Keong", "Suzuki Takeshi"]
VI_LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Võ", "Đặng", "Bùi", "Đỗ"]
VI_MID = ["Văn", "Thị", "Minh", "Quốc", "Thanh", "Hữu", "Ngọc", "Anh"]
VI_GIVEN = ["Hùng", "Lan", "Tuấn", "Hương", "Dũng", "Mai", "Long", "Hạnh", "Khoa", "Phương", "Nam", "Trang", "Hải", "Linh"]
RMS = ["Nguyễn Hoàng Nam", "Trần Thu Hà", "Lê Minh Quân", "Phạm Ngọc Anh"]

INTERACTION_TEXT = [
    ("Gặp trực tiếp", "Thăm nhà máy, trao đổi kế hoạch đơn hàng quý tới", "Khách hàng quan tâm, hẹn gửi đề xuất"),
    ("Điện thoại", "Hỏi thăm tình hình sản xuất, cập nhật biểu phí/ưu đãi mới", "Đã ghi nhận nhu cầu"),
    ("Zalo", "Gửi bảng tỷ giá & thông tin sản phẩm tài trợ nhập khẩu", "Đã xem, chưa phản hồi"),
    ("Email", "Gửi đề xuất hợp tác cung cấp dịch vụ thu hộ/chi hộ", "Chờ ý kiến kế toán trưởng"),
    ("Gặp trực tiếp", "Làm việc về hồ sơ gia hạn hạn mức tín dụng", "Khách hàng sẽ bổ sung BCTC"),
    ("Điện thoại", "Nhắc hồ sơ chứng từ giải ngân còn thiếu", "Hẹn bổ sung trong tuần"),
]


def _wchoice(rng, items):
    tot = sum(w for *_, w in items)
    x = rng.uniform(0, tot)
    for it in items:
        x -= it[-1]
        if x <= 0:
            return it
    return items[-1]


def _vi_person(rng):
    mid = rng.choice(VI_MID)
    return f"{rng.choice(VI_LAST)} {mid} {rng.choice(VI_GIVEN)}", mid == "Thị"


def build_customers(rng: random.Random):
    today = date.today()
    used, rows = set(), []
    inds = list(INDUSTRIES.keys())
    for i in range(1, N_CUSTOMERS + 1):
        fdi = rng.random() < 0.45
        ind = rng.choice(inds)
        ip = INDUSTRIES[ind]
        prov, zones, _ = _wchoice(rng, LOCATIONS)
        zone = rng.choice(zones) if (fdi or rng.random() < 0.6) else None
        country = _wchoice(rng, FDI_COUNTRIES)[0] if fdi else None

        name_zh = None
        if fdi:
            for _ in range(20):
                latin, zh = rng.choice(FDI_BRANDS[country])
                nm = f"Công ty TNHH {latin} Việt Nam"
                if nm not in used:
                    break
            else:
                nm = f"Công ty TNHH {latin} {ip['short']} Việt Nam"
            name_zh = f"{zh}(越南)有限责任公司" if zh else None
        else:
            for _ in range(30):
                nm = f"{rng.choice(LEGAL)} {ip['short']} {rng.choice(BRANDS_VI)}"
                if nm not in used:
                    break
            else:
                nm = f"{nm} {i}"
        used.add(nm)

        rev = min(8000, max(25, rng.lognormvariate(5.5, 1.0)))
        if fdi:
            rev *= rng.uniform(1.0, 1.6)
        rev = round(rev, 1)
        seg = "Large" if rev >= 1500 else "Middle" if rev >= 300 else "SME"
        assets = round(rev * rng.uniform(0.6, 1.6), 1)
        equity = round(assets * rng.uniform(0.2, 0.55), 1)
        emp = int(max(8, rev * ip["emp_per_bn"] * rng.uniform(0.5, 1.4)))
        rev_usd = rev / 25.4  # triệu USD
        exp_m = round(rev_usd * rng.uniform(*ip["export"]) * (1.2 if fdi else 1), 2)
        imp_m = round(rev_usd * rng.uniform(*ip["import"]) * 0.6, 2)
        fx = round((exp_m + imp_m) * rng.uniform(0.15, 0.35), 2)

        has_loan = rng.random() < 0.62
        loan = round(assets * rng.uniform(0.04, 0.3), 1) if has_loan else 0.0
        limit = round(loan * rng.uniform(1.0, 1.5), 1) if has_loan else 0.0
        expiry = today + timedelta(days=rng.randint(-12, 420)) if limit else None
        if limit and rng.random() < 0.18:
            expiry = today + timedelta(days=rng.randint(5, 85))          # hạn mức sắp hết hạn
        if limit and rng.random() < 0.15:
            loan = round(limit * rng.uniform(0.9, 0.99), 1)               # dùng gần hết hạn mức
        dg = rng.choices([1, 2, 3, 4, 5], [88, 8, 2.5, 1, 0.5])[0] if loan else 1
        casa = round(rev * rng.uniform(0.008, 0.05), 1)
        dep = round(rev * rng.uniform(0, 0.04), 1) if rng.random() < 0.4 else 0.0

        held = ["DONG_TIEN"] if rng.random() < 0.25 else []
        if loan:
            held.append("VAY_VLD")
        if imp_m >= 1 and rng.random() < 0.35:
            held.append("LC")
        if (exp_m + imp_m) >= 0.5 and rng.random() < 0.5:
            held.append("TTQT")
        if fx >= 1.5 and rng.random() < 0.3:
            held.append("NGOAI_TE")
        if emp >= 50 and rng.random() < 0.35:
            held.append("LUONG")
        if dep > 0:
            held.append("TIEN_GUI")
        if loan and rng.random() < 0.2:
            held.append("BAO_LANH")

        # liên hệ
        chinese_contact = fdi and country in ("Trung Quốc", "Đài Loan") and rng.random() < 0.6
        if chinese_contact:
            sn, sz = rng.choice(ZH_SURN)
            gn, gz = rng.choice(ZH_GIVEN)
            cname, cname_zh, lang = f"{sn} {gn}", sz + gz, "zh"
            title = rng.choice(["GD", "CFO", "PGD"])
        elif fdi and country in ("Hàn Quốc", "Nhật Bản", "Singapore") and rng.random() < 0.5:
            cname, cname_zh, lang = rng.choice(EN_NAMES), None, "en"
            title = rng.choice(["GD", "CFO"])
        else:
            cname, _f = _vi_person(rng)
            cname_zh, lang = None, "vi"
            title = rng.choice(["GD", "KTT", "KTT", "CFO", "PGD"])

        rows.append(dict(
            customer_id=f"CORP{i:04d}", name=nm, name_zh=name_zh,
            tax_code=f"{rng.randint(3000000000, 3999999999)}", segment=seg,
            ownership="FDI" if fdi else "Nội địa", investor_country=country, industry=ind,
            province=prov, industrial_zone=zone, employees=emp, annual_revenue_bn=rev,
            total_assets_bn=assets, equity_bn=equity, export_usd_m=exp_m, import_usd_m=imp_m,
            fx_exposure_usd_m=fx, casa_balance_bn=casa, deposit_bn=dep, loan_outstanding_bn=loan,
            credit_limit_bn=limit, limit_expiry=expiry, debt_group=dg,
            relationship_years=rng.randint(0, 12), products_held=sorted(set(held)),
            rm_name=rng.choice(RMS), contact_name=cname, contact_name_zh=cname_zh, contact_title=title,
            contact_phone=f"09{rng.randint(10000000, 99999999)}",
            contact_email=f"finance{i}@example.com.vn", preferred_language=lang,
            last_contact_date=today - timedelta(days=rng.randint(2, 150)),
        ))
    return rows


def build_monthly(c: dict, rng: random.Random):
    today = date.today()
    months = []
    y, m = today.year, today.month
    for k in range(11, -1, -1):
        mm = m - k
        yy = y
        while mm <= 0:
            mm += 12; yy -= 1
        months.append(f"{yy}-{mm:02d}")
    base = c["annual_revenue_bn"] / 12 * rng.uniform(0.3, 0.8)
    slope = rng.uniform(-0.01, 0.025)
    drop = rng.random() < 0.12
    out = []
    for idx, mo in enumerate(months):
        seas = 1 + 0.12 * ((idx % 12) in (8, 9, 10)) - 0.1 * ((idx % 12) == 1)
        v = base * (1 + slope * idx) * seas * rng.uniform(0.9, 1.1)
        if drop and idx >= 9:
            v *= rng.uniform(0.55, 0.75)
        out.append(dict(
            customer_id=c["customer_id"], month=mo,
            inflow_bn=round(v, 2), outflow_bn=round(v * rng.uniform(0.9, 1.05), 2),
            trade_usd_m=round((c["export_usd_m"] + c["import_usd_m"]) / 12 * rng.uniform(0.7, 1.3), 2),
            avg_balance_bn=round(c["casa_balance_bn"] * rng.uniform(0.8, 1.2) * (0.6 if drop and idx >= 10 else 1), 2),
        ))
    return out


def _migrate_columns():
    """Bảng cũ (DB đã có dữ liệu) chưa có cột mới → thêm vào, không mất dữ liệu."""
    from sqlalchemy import inspect, text
    cols = {c["name"] for c in inspect(engine).get_columns("corp_customers")}
    if "lifecycle" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE corp_customers ADD COLUMN lifecycle VARCHAR DEFAULT 'prospect'"))
            # KH đã có số dư/dư nợ/hạn mức tại TPBank → hiện hữu; còn lại → KH mới
            conn.execute(text("UPDATE corp_customers SET lifecycle = CASE WHEN COALESCE(loan_outstanding_bn,0) > 0 "
                              "OR COALESCE(casa_balance_bn,0) > 0 OR COALESCE(deposit_bn,0) > 0 "
                              "OR COALESCE(credit_limit_bn,0) > 0 THEN 'existing' ELSE 'prospect' END"))


def ensure_seed():
    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    if os.getenv("CRM_SEED_DEMO", "1") == "0":
        return False          # bản triển khai thật: không nạp khách hàng mô phỏng
    db = SessionLocal()
    try:
        if db.query(CorpCustomer).count() > 0 or db.query(CorpSetting).filter_by(key="_demo_cleared").first():
            return False
        rng = random.Random(20261107)
        custs = build_customers(rng)
        all_monthly = {}
        for c in custs:
            c["lifecycle"] = "existing" if (c["loan_outstanding_bn"] or c["casa_balance_bn"] or c["deposit_bn"] or c["credit_limit_bn"]) else "prospect"
            db.add(CorpCustomer(**c))
            ms = build_monthly(c, rng)
            all_monthly[c["customer_id"]] = ms
            for r in ms:
                db.add(CorpMonthly(**r))
            for _ in range(rng.randint(0, 4)):
                ch, summ, out = rng.choice(INTERACTION_TEXT)
                db.add(CorpInteraction(customer_id=c["customer_id"], channel=ch, summary=summ, outcome=out,
                                       date=date.today() - timedelta(days=rng.randint(3, 180))))
        # pipeline mẫu từ các cơ hội điểm cao
        scored = []
        for c in custs:
            a = scoring.analyze(c, all_monthly[c["customer_id"]])
            for t in a["top_opportunities"][:1]:
                scored.append((t["score"], c, t))
        scored.sort(key=lambda x: -x[0])
        for _, c, t in scored[:48]:
            stage = rng.choices(STAGES, [20, 28, 18, 12, 8, 14])[0]
            db.add(CorpOpportunity(
                customer_id=c["customer_id"], product=t["product"], stage=stage,
                expected_amount_bn=t["expected_amount_bn"], probability=STAGE_PROB[stage],
                next_action=rng.choice(["Gửi đề xuất", "Hẹn gặp CFO", "Thu thập BCTC", "Chờ phản hồi", "Trình hồ sơ"]),
                due_date=date.today() + timedelta(days=rng.randint(-3, 30)),
            ))
        db.commit()
        return True
    finally:
        db.close()


if __name__ == "__main__":
    print("seeded" if ensure_seed() else "already seeded")
