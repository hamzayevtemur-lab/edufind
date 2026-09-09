from .admin import router as admin_router
from .centers import router as centers_router
from .center import router as center_router
from .likes import router as likes_router
from .partners import router as partner_router
from .partner_portal import router as partner_portal_router

__all__ = [
    "admin_router",
    "centers_router",
    "center_router",
    "likes_router",    
    "partner_router",
    "partner_portal_router",
]