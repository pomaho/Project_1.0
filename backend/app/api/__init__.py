from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.download import router as download_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.keywords import router as keywords_router
from app.api.search import router as search_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(keywords_router, prefix="/keywords", tags=["keywords"])
api_router.include_router(download_router, prefix="/download", tags=["download"])
