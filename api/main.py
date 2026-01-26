from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    documents_router,
    upload_router,
    health_router,
    templates_router,
    export_router,
    stats_router,
    categories_router,
    auth_router,
)
from core.config import get_settings
from models import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="OCR4All API",
    description="Document OCR and metadata extraction pipeline",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router)
app.include_router(upload_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(templates_router, prefix=settings.api_prefix)
app.include_router(export_router, prefix=settings.api_prefix)
app.include_router(stats_router, prefix=settings.api_prefix)
app.include_router(categories_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
