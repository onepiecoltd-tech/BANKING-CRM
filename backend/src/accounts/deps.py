"""FastAPI dependencies + middleware kiểm tra đăng nhập."""
from typing import Optional
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse

from .service import user_from_token, AuthUser

# Các đường dẫn không cần đăng nhập
PUBLIC_PATHS = {"/api/health", "/api/auth/status", "/api/auth/setup", "/api/auth/login"}
# Dịch vụ nội bộ (WhatsApp service / webhook) — chỉ chấp nhận từ máy cục bộ nếu không có token
LOOPBACK_ONLY = ("/api/outreach/twilio-webhook", "/api/outreach/reply")


def bearer(request: Request) -> Optional[str]:
    h = request.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return None


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/") or path in PUBLIC_PATHS:
        return await call_next(request)
    token = bearer(request)
    user = user_from_token(token)
    if user:
        request.state.user = user
        request.state.token = token
        return await call_next(request)
    if path in LOOPBACK_ONLY and request.client and request.client.host in ("127.0.0.1", "::1", "localhost"):
        return await call_next(request)
    return JSONResponse({"detail": "Chưa đăng nhập hoặc phiên đã hết hạn"}, status_code=401)


def current_user(request: Request) -> AuthUser:
    u = getattr(request.state, "user", None)
    if not u:
        raise HTTPException(401, "Chưa đăng nhập hoặc phiên đã hết hạn")
    return u


def require_admin(request: Request) -> AuthUser:
    u = current_user(request)
    if not u.is_admin:
        raise HTTPException(403, "Chỉ Quản trị viên (Admin) mới được thực hiện thao tác này")
    return u


def client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None
