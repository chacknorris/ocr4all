from api.routes.documents import router as documents_router
from api.routes.upload import router as upload_router
from api.routes.health import router as health_router
from api.routes.templates import router as templates_router
from api.routes.export import router as export_router
from api.routes.stats import router as stats_router
from api.routes.categories import router as categories_router
from api.routes.auth import router as auth_router

__all__ = [
    "documents_router",
    "upload_router",
    "health_router",
    "templates_router",
    "export_router",
    "stats_router",
    "categories_router",
    "auth_router",
]
