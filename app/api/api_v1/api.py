from fastapi import APIRouter
from app.api.api_v1.endpoints import wearers, devices, auth, dashboard, history, data_collection

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(wearers.router, prefix="/wearers", tags=["wearers"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(data_collection.router, prefix="/data-collection", tags=["data-collection"])
