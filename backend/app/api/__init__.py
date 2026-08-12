"""API routes and endpoints package."""

from fastapi import APIRouter

from app.api.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)

__all__ = ["api_router", "auth_router"]
