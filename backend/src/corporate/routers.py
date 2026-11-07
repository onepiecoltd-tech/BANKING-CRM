"""Gom các router của bản Doanh nghiệp để api.py include."""
from .crud import router as crud_router
from .settings_router import router as settings_router
from .outreach import router as outreach_router
from .conversations import router as conv_router
from .reasoning import router as reasoning_router
from .analytics import router as analytics_router
from .import_router import router as import_router

ALL = [crud_router, settings_router, outreach_router, conv_router, reasoning_router, analytics_router, import_router]
