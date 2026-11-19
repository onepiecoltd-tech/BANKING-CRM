"""/api/auth/* (đăng nhập) và /api/admin/* (quản lý người dùng, nhật ký)."""
import hmac
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel

from src.database import SessionLocal
from .models import AppUser, AuditEvent
from . import service as S
from .deps import current_user, require_admin, client_ip, bearer

router = APIRouter(tags=["accounts"])


def _user_row(u: AppUser) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role, "rm_name": u.rm_name,
            "is_active": bool(u.is_active), "must_change_password": bool(u.must_change_password),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None, "created_by": u.created_by}


# ── auth ─────────────────────────────────────────────────────────────────────
@router.get("/api/auth/status")
def status():
    db = SessionLocal()
    try:
        return {"initialized": db.query(AppUser).count() > 0, "setup_code_required": bool(os.getenv("CRM_SETUP_CODE"))}
    finally:
        db.close()


class SetupIn(BaseModel):
    username: str
    full_name: str
    password: str
    setup_code: Optional[str] = None


@router.post("/api/auth/setup")
def setup(body: SetupIn, request: Request):
    """Lần chạy đầu: tạo tài khoản Admin (chỉ khi chưa có người dùng nào)."""
    db = SessionLocal()
    try:
        if db.query(AppUser).count() > 0:
            raise HTTPException(409, "Hệ thống đã được thiết lập")
        need = os.getenv("CRM_SETUP_CODE")
        if need and not hmac.compare_digest((body.setup_code or "").strip().encode(), need.strip().encode()):
            raise HTTPException(403, "Mã thiết lập không đúng (xem biến CRM_SETUP_CODE trên máy chủ)")
        un = body.username.strip().lower()
        if len(un) < 3 or not un.replace(".", "").replace("_", "").isalnum():
            raise HTTPException(400, "Tên đăng nhập tối thiểu 3 ký tự, chỉ gồm chữ/số/._")
        err = S.check_password_policy(body.password)
        if err:
            raise HTTPException(400, err)
        u = AppUser(username=un, full_name=body.full_name.strip() or un, role="admin", rm_name=body.full_name.strip() or un,
                    password_hash=S.hash_password(body.password), created_by="setup")
        db.add(u); db.commit(); db.refresh(u)
        token = S.create_session(db, u)
        S.audit(S._to_auth(u), "setup.admin", "user", u.id, ip=client_ip(request))
        return {"token": token, "user": S._to_auth(u).public()}
    finally:
        db.close()


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    un = body.username.strip().lower()
    wait = S.login_locked(un)
    if wait:
        raise HTTPException(429, f"Đăng nhập sai quá nhiều lần. Thử lại sau {wait // 60 + 1} phút")
    db = SessionLocal()
    try:
        u = db.query(AppUser).filter_by(username=un).first()
        if not u or not u.is_active or not S.verify_password(body.password, u.password_hash):
            S.login_failed(un)
            S.audit(None, "login.failed", "user", un, ip=client_ip(request))
            raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
        S.login_ok(un)
        token = S.create_session(db, u)
        au = S._to_auth(u)
        S.audit(au, "login", "user", u.id, ip=client_ip(request))
        return {"token": token, "user": au.public()}
    finally:
        db.close()


@router.post("/api/auth/logout")
def logout(request: Request, user=Depends(current_user)):
    t = bearer(request)
    if t:
        S.revoke_token(t)
    S.audit(user, "logout", "user", user.id, ip=client_ip(request))
    return {"ok": True}


@router.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user.public()


class PwIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/api/auth/change-password")
def change_password(body: PwIn, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        u = db.query(AppUser).filter_by(id=user.id).first()
        if not S.verify_password(body.old_password, u.password_hash):
            raise HTTPException(400, "Mật khẩu hiện tại không đúng")
        err = S.check_password_policy(body.new_password)
        if err:
            raise HTTPException(400, err)
        if body.new_password == body.old_password:
            raise HTTPException(400, "Mật khẩu mới phải khác mật khẩu cũ")
        u.password_hash = S.hash_password(body.new_password)
        u.must_change_password = False
        S.revoke_user_sessions(db, u.id, except_token=bearer(request))
        db.commit()
        S.audit(user, "password.change", "user", u.id, ip=client_ip(request))
        return {"ok": True}
    finally:
        db.close()


# ── admin: người dùng ────────────────────────────────────────────────────────
@router.get("/api/admin/users")
def list_users(admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        return {"items": [_user_row(u) for u in db.query(AppUser).order_by(AppUser.role, AppUser.username)]}
    finally:
        db.close()


class UserIn(BaseModel):
    username: str
    full_name: str
    role: str = "staff"
    rm_name: Optional[str] = None
    password: str


@router.post("/api/admin/users")
def create_user(body: UserIn, request: Request, admin=Depends(require_admin)):
    un = body.username.strip().lower()
    if len(un) < 3 or not un.replace(".", "").replace("_", "").isalnum():
        raise HTTPException(400, "Tên đăng nhập tối thiểu 3 ký tự, chỉ gồm chữ/số/._")
    if body.role not in S.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    err = S.check_password_policy(body.password)
    if err:
        raise HTTPException(400, err)
    db = SessionLocal()
    try:
        if db.query(AppUser).filter_by(username=un).first():
            raise HTTPException(409, "Tên đăng nhập đã tồn tại")
        u = AppUser(username=un, full_name=body.full_name.strip() or un, role=body.role,
                    rm_name=(body.rm_name or body.full_name).strip(), password_hash=S.hash_password(body.password),
                    must_change_password=True, created_by=admin.username)
        db.add(u); db.commit(); db.refresh(u)
        S.audit(admin, "user.create", "user", u.id, {"username": un, "role": body.role}, client_ip(request))
        return _user_row(u)
    finally:
        db.close()


class UserPatch(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    rm_name: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


@router.patch("/api/admin/users/{uid}")
def patch_user(uid: int, body: UserPatch, request: Request, admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        u = db.query(AppUser).filter_by(id=uid).first()
        if not u:
            raise HTTPException(404, "Không tìm thấy người dùng")
        admins = db.query(AppUser).filter_by(role="admin", is_active=True).count()
        losing_admin = u.role == "admin" and u.is_active and (
            (body.role is not None and body.role != "admin") or body.is_active is False)
        if losing_admin and admins <= 1:
            raise HTTPException(400, "Phải còn ít nhất một Admin đang hoạt động")
        if u.id == admin.id and body.is_active is False:
            raise HTTPException(400, "Không thể tự khóa tài khoản của mình")
        changes = {}
        if body.full_name is not None and body.full_name.strip():
            u.full_name = body.full_name.strip(); changes["full_name"] = u.full_name
        if body.role is not None:
            if body.role not in S.ROLES:
                raise HTTPException(400, "Vai trò không hợp lệ")
            u.role = body.role; changes["role"] = body.role
        if body.rm_name is not None:
            u.rm_name = body.rm_name.strip() or u.full_name; changes["rm_name"] = u.rm_name
        if body.is_active is not None:
            u.is_active = body.is_active; changes["is_active"] = body.is_active
            if not body.is_active:
                S.revoke_user_sessions(db, u.id)
        if body.new_password:
            err = S.check_password_policy(body.new_password)
            if err:
                raise HTTPException(400, err)
            u.password_hash = S.hash_password(body.new_password)
            u.must_change_password = True
            S.revoke_user_sessions(db, u.id)
            changes["password"] = "reset"
        db.commit()
        S.audit(admin, "user.update", "user", u.id, changes, client_ip(request))
        return _user_row(u)
    finally:
        db.close()


# ── admin: nhật ký thao tác ──────────────────────────────────────────────────
@router.get("/api/admin/audit")
def audit_events(limit: int = Query(100, le=500), username: Optional[str] = None, action: Optional[str] = None,
                 admin=Depends(require_admin)):
    db = SessionLocal()
    try:
        q = db.query(AuditEvent).order_by(AuditEvent.id.desc())
        if username:
            q = q.filter(AuditEvent.username == username)
        if action:
            q = q.filter(AuditEvent.action.like(f"{action}%"))
        return {"items": [{"id": e.id, "ts": e.ts.isoformat() + "Z", "username": e.username, "role": e.role, "action": e.action,
                           "entity": e.entity, "entity_id": e.entity_id, "detail": e.detail, "ip": e.ip} for e in q.limit(limit)]}
    finally:
        db.close()
