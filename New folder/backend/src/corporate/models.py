"""Corporate (Khách hàng Doanh nghiệp) tables — share the same SQLite DB/Base as retail."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, JSON, DateTime, Date
from src.database import Base


class CorpCustomer(Base):
    __tablename__ = "corp_customers"

    customer_id = Column(String, primary_key=True)          # CORP0001
    name = Column(String, nullable=False)                   # tên tiếng Việt
    name_zh = Column(String, nullable=True)                 # tên tiếng Trung (FDI TQ/ĐL)
    tax_code = Column(String, nullable=True)                # mã số thuế (mô phỏng)
    segment = Column(String, nullable=False)                # SME | Middle | Large
    ownership = Column(String, nullable=False)              # Nội địa | FDI
    investor_country = Column(String, nullable=True)        # Trung Quốc, Đài Loan, ...
    industry = Column(String, nullable=False)
    province = Column(String, nullable=False)
    industrial_zone = Column(String, nullable=True)
    employees = Column(Integer, default=0)
    annual_revenue_bn = Column(Float, default=0)            # tỷ đồng
    total_assets_bn = Column(Float, default=0)
    equity_bn = Column(Float, default=0)
    export_usd_m = Column(Float, default=0)                 # triệu USD / năm
    import_usd_m = Column(Float, default=0)
    fx_exposure_usd_m = Column(Float, default=0)
    casa_balance_bn = Column(Float, default=0)              # số dư bình quân không kỳ hạn
    deposit_bn = Column(Float, default=0)                   # tiền gửi có kỳ hạn
    loan_outstanding_bn = Column(Float, default=0)
    credit_limit_bn = Column(Float, default=0)
    limit_expiry = Column(Date, nullable=True)
    debt_group = Column(Integer, default=1)                 # nhóm nợ 1-5
    relationship_years = Column(Integer, default=0)
    products_held = Column(JSON, default=list)
    rm_name = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_name_zh = Column(String, nullable=True)
    contact_title = Column(String, nullable=True)           # key: GD | KTT | CFO | PGD
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    preferred_language = Column(String, default="vi")       # vi | zh | en
    lifecycle = Column(String, default="prospect")          # prospect = KH mới/tiềm năng | existing = KH hiện hữu TPBank
    last_contact_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CorpMonthly(Base):
    __tablename__ = "corp_monthly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, index=True, nullable=False)
    month = Column(String, nullable=False)                  # YYYY-MM
    inflow_bn = Column(Float, default=0)
    outflow_bn = Column(Float, default=0)
    trade_usd_m = Column(Float, default=0)
    avg_balance_bn = Column(Float, default=0)


class CorpInteraction(Base):
    __tablename__ = "corp_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, index=True, nullable=False)
    date = Column(Date, nullable=False)
    channel = Column(String, nullable=False)                # Gặp trực tiếp | Điện thoại | Zalo | Email
    summary = Column(String, nullable=False)
    outcome = Column(String, nullable=True)


class CorpOpportunity(Base):
    __tablename__ = "corp_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, index=True, nullable=False)
    product = Column(String, nullable=False)                # mã sản phẩm
    stage = Column(String, nullable=False, default="Tiếp cận")
    expected_amount_bn = Column(Float, default=0)
    probability = Column(Integer, default=15)
    next_action = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


def customer_dict(c: CorpCustomer) -> dict:
    d = {col.name: getattr(c, col.name) for col in c.__table__.columns}
    for k in ("limit_expiry", "last_contact_date"):
        if d.get(k):
            d[k] = d[k].isoformat()
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d


# ── Mở rộng: chiến dịch, hội thoại, cài đặt, import, nhật ký trợ lý ───────────
from sqlalchemy import Text  # noqa: E402


class CorpCampaign(Base):
    __tablename__ = "corp_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    product = Column(String, nullable=False)
    channel = Column(String, default="zalo")                # zalo | email | call
    language = Column(String, default="auto")               # auto | vi | zh | en
    framework = Column(String, default="consultative")      # consultative | aida | spin
    filters = Column(JSON, default=dict)
    status = Column(String, default="Đang chạy")            # Nháp | Đang chạy | Hoàn tất
    owner = Column(String, nullable=True)                   # username người tạo
    owner_rm = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CorpCampaignTarget(Base):
    __tablename__ = "corp_campaign_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, index=True, nullable=False)
    customer_id = Column(String, index=True, nullable=False)
    status = Column(String, default="Chưa liên hệ")         # Chưa liên hệ | Đã liên hệ | Phản hồi | Quan tâm | Chuyển đổi | Từ chối
    language = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CorpMessage(Base):
    __tablename__ = "corp_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, index=True, nullable=False)
    campaign_id = Column(Integer, nullable=True)
    direction = Column(String, nullable=False)              # out | in
    channel = Column(String, default="zalo")
    language = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    intent = Column(String, nullable=True)                  # cho tin nhắn đến
    product = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CorpOptOut(Base):
    __tablename__ = "corp_optout"

    customer_id = Column(String, primary_key=True)
    reason = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CorpSetting(Base):
    __tablename__ = "corp_settings"

    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=True)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CorpImportBatch(Base):
    __tablename__ = "corp_import_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    kind = Column(String, nullable=False)                   # xlsx | csv | pdf
    method = Column(String, nullable=True)                  # excel | csv | pdf-text | pdf-table | ocr-tesseract | ocr-gemini
    target = Column(String, default="customers")            # customers | monthly
    status = Column(String, default="Xem trước")            # Xem trước | Chờ duyệt | Đã nhập | Từ chối | Hủy
    mapping = Column(JSON, default=dict)
    columns = Column(JSON, default=list)
    rows = Column(JSON, default=list)                       # dòng thô (list[dict])
    summary = Column(JSON, default=dict)
    note = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_rm = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


class CorpAgentRun(Base):
    __tablename__ = "corp_agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=True)
    query = Column(Text, nullable=False)
    filters = Column(JSON, default=dict)
    steps = Column(JSON, default=list)
    total_matched = Column(Integer, default=0)
    llm_used = Column(Boolean, default=False)
    llm_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
