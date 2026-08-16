"""API routes and endpoints package."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.medication_safety import router as medication_safety_router
from app.api.records import router as records_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(records_router)
api_router.include_router(medication_safety_router)

__all__ = [
    "api_router",
    "auth_router",
    "documents_router",
    "records_router",
    "medication_safety_router",
]
