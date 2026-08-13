"""API routes and endpoints package."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(documents_router)

__all__ = ["api_router", "auth_router", "documents_router"]

