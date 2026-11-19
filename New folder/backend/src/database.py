"""
Database setup and models using SQLAlchemy ORM.
"""
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from src.config import settings

Base = declarative_base()


class Customer(Base):
    """Customer base information."""
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    city = Column(String, nullable=True)
    segment = Column(String, nullable=False)  # mass, affluent, premium
    occupation = Column(String, nullable=True)
    annual_income = Column(Float, nullable=True)
    kyc_status = Column(String, default="verified")  # verified, pending, failed
    relationship_years = Column(Integer, default=0)
    
    # Product holdings
    has_credit_card = Column(Boolean, default=False)
    has_personal_loan = Column(Boolean, default=False)
    has_home_loan = Column(Boolean, default=False)
    has_fd = Column(Boolean, default=False)
    
    # Financial metrics
    monthly_avg_balance = Column(Float, default=0.0)
    credit_score = Column(Integer, nullable=True)
    last_contact_date = Column(DateTime, nullable=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="customer")
    interactions = relationship("Interaction", back_populates="customer")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Transaction(Base):
    """Customer transactions."""
    __tablename__ = "transactions"

    txn_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)  # salary, shopping, healthcare, etc.
    channel = Column(String, nullable=True)  # ATM, online, branch, etc.
    merchant = Column(String, nullable=True)
    
    # Relationship
    customer = relationship("Customer", back_populates="transactions")
    
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    """Banking products."""
    __tablename__ = "products"

    product_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    product_type = Column(String, nullable=False)  # personal_loan, credit_card, fd, home_loan
    min_income = Column(Float, default=0.0)
    min_credit_score = Column(Integer, default=0)
    eligible_segments = Column(JSON, default=["mass", "affluent", "premium"])
    interest_rate = Column(Float, nullable=True)
    features = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class Interaction(Base):
    """Customer interactions (outreach and responses)."""
    __tablename__ = "interactions"

    interaction_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    channel = Column(String, nullable=True)  # whatsapp, email, sms, call
    product_offered = Column(String, nullable=True)
    message = Column(String, nullable=True)
    response = Column(String, nullable=True)
    converted = Column(Boolean, default=False)
    pipeline_state = Column(String, default="NEW")  # NEW, CONTACTED, ENGAGED, etc.
    framework_used = Column(String, nullable=True)  # AIDA, SPIN, etc.
    
    # Relationship
    customer = relationship("Customer", back_populates="interactions")
    
    created_at = Column(DateTime, default=datetime.utcnow)


class IdentityGraph(Base):
    """Identity resolution graph."""
    __tablename__ = "identity_graph"

    id = Column(String, primary_key=True)
    identifier_value = Column(String, nullable=False)
    identifier_type = Column(String, nullable=False)  # mobile, email, pan, aadhaar, customer_id
    canonical_id = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    source = Column(String, nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)


class Consent(Base):
    """Customer consent records."""
    __tablename__ = "consents"

    id = Column(String, primary_key=True)
    canonical_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # whatsapp, email, sms, call
    opted_in = Column(Boolean, default=True)
    dnd_window = Column(String, nullable=True)  # "21:00-09:00"
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Suppression(Base):
    """Suppression rules."""
    __tablename__ = "suppressions"

    id = Column(String, primary_key=True)
    canonical_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)  # opted_out, frequency_capped, dnd, compliance, cooldown
    expires_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    """Customer session for authentication."""
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    canonical_id = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    otp_verified = Column(Boolean, default=False)
    scope = Column(JSON, default=[])  # what data can be accessed
    expires_at = Column(DateTime, nullable=True)


class CadenceJob(Base):
    """Scheduled cadence jobs for followups."""
    __tablename__ = "cadence_jobs"

    job_id = Column(String, primary_key=True)
    canonical_id = Column(String, nullable=False)
    product_id = Column(String, nullable=False)
    next_run_at = Column(DateTime, nullable=False)
    step = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit trail for every significant action — banking compliance."""
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String, nullable=False)        # SEND, REPLY, OPT_OUT, CAMPAIGN_RUN, VALIDATION_FAIL
    actor = Column(String, nullable=True)          # "system" | "rm" | "ai_agent"
    customer_id = Column(String, nullable=True)
    product_id = Column(String, nullable=True)
    channel = Column(String, nullable=True)        # whatsapp, twilio
    details = Column(JSON, nullable=True)          # arbitrary extra data
    outcome = Column(String, nullable=True)        # success, blocked, suppressed, error
    created_at = Column(DateTime, default=datetime.utcnow)


# Database engine and session
engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
