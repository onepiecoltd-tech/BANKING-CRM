"""Tài khoản, phiên đăng nhập và nhật ký thao tác (dùng chung DB/Base với phần còn lại)."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from src.database import Base


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="staff")      # admin | staff
    rm_name = Column(String, nullable=True)                      # tên hiển thị trên danh mục KH được giao (corp_customers.rm_name)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)


class AppSession(Base):
    __tablename__ = "app_sessions"

    token_hash = Column(String, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "app_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    username = Column(String, index=True, nullable=True)
    role = Column(String, nullable=True)
    action = Column(String, index=True, nullable=False)          # vd: login, customer.create, import.approve
    entity = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    ip = Column(String, nullable=True)
