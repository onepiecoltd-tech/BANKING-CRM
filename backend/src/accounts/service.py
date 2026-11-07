"""Băm mật khẩu (scrypt, chỉ dùng thư viện chuẩn), phiên đăng nhập, ghi nhật ký."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.database import SessionLocal
from .models import AppUser, AppSession, AuditEvent

SESSION_HOURS = 12
MIN_PASSWORD = 8
ROLES = ("admin", "staff")

_N, _R, _P = 2 ** 14, 8, 1


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(h).decode())


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def check_password_policy(pw: str) -> Optional[str]:
    if len(pw or "") < MIN_PASSWORD:
        return f"Mật khẩu tối thiểu {MIN_PASSWORD} ký tự"
    if pw.isdigit() or pw.isalpha():
        return "Mật khẩu cần có cả chữ và số (hoặc ký tự đặc biệt)"
    return None


@dataclass
class AuthUser:
    id: int
    username: str
    full_name: str
    role: str
    rm_name: Optional[str]
    must_change_password: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> dict:
        return {"id": self.id, "username": self.username, "full_name": self.full_name, "role": self.role,
                "rm_name": self.rm_name, "must_change_password": self.must_change_password}


def _to_auth(u: AppUser) -> AuthUser:
    return AuthUser(u.id, u.username, u.full_name, u.role, u.rm_name or u.full_name, bool(u.must_change_password))


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user: AppUser) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    db.add(AppSession(token_hash=_th(token), user_id=user.id, created_at=now, last_seen=now,
                      expires_at=now + timedelta(hours=SESSION_HOURS)))
    user.last_login = now
    db.commit()
    return token


def user_from_token(token: Optional[str]) -> Optional[AuthUser]:
    if not token:
        return None
    db = SessionLocal()
    try:
        s = db.query(AppSession).filter_by(token_hash=_th(token)).first()
        now = datetime.utcnow()
        if not s or s.expires_at < now:
            if s:
                db.delete(s); db.commit()
            return None
        u = db.query(AppUser).filter_by(id=s.user_id).first()
        if not u or not u.is_active:
            return None
        # gia hạn trượt, tránh ghi DB mỗi request
        if (now - (s.last_seen or now)).total_seconds() > 300:
            s.last_seen = now
            s.expires_at = now + timedelta(hours=SESSION_HOURS)
            db.commit()
        return _to_auth(u)
    finally:
        db.close()


def revoke_token(token: str):
    db = SessionLocal()
    try:
        db.query(AppSession).filter_by(token_hash=_th(token)).delete()
        db.commit()
    finally:
        db.close()


def revoke_user_sessions(db, user_id: int, except_token: Optional[str] = None):
    q = db.query(AppSession).filter(AppSession.user_id == user_id)
    if except_token:
        q = q.filter(AppSession.token_hash != _th(except_token))
    q.delete(synchronize_session=False)


# ── chống dò mật khẩu: 5 lần sai → khóa 5 phút (theo tài khoản) ─────────────
_fails: dict = {}


def login_locked(username: str) -> int:
    _, until = _fails.get(username.lower(), (0, 0))
    return max(0, int(until - time.time()))


def login_failed(username: str):
    k = username.lower()
    n, _ = _fails.get(k, (0, 0))
    n += 1
    _fails[k] = (0, time.time() + 300) if n >= 5 else (n, 0)


def login_ok(username: str):
    _fails.pop(username.lower(), None)


# ── nhật ký ──────────────────────────────────────────────────────────────────
def audit(user, action: str, entity: str | None = None, entity_id: str | None = None, detail=None, ip: str | None = None):
    """user: AuthUser | None. Không bao giờ làm hỏng request chính."""
    try:
        db = SessionLocal()
        try:
            d = detail if (detail is None or isinstance(detail, str)) else json.dumps(detail, ensure_ascii=False, default=str)
            db.add(AuditEvent(username=getattr(user, "username", None), role=getattr(user, "role", None), action=action,
                              entity=entity, entity_id=str(entity_id) if entity_id is not None else None,
                              detail=(d or "")[:2000], ip=ip))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass
