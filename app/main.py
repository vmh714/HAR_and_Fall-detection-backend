from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import os
from contextlib import asynccontextmanager
from app.patch_loop import patch_asyncio_loop

# Apply Windows loop patch early
patch_asyncio_loop()

from app.services.mqtt_service import mqtt_service
from app.services.alert_maintenance import auto_resolve_stale_alerts_loop
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # MQTT chạy trên THREAD RIÊNG (không phải task trên main loop) — để một lần
    # mạng flap làm sập loop MQTT KHÔNG kéo theo HTTP server. Xem MQTTService.start().
    mqtt_service.start()
    print("Starting up MQTT Bridge (isolated thread)...")

    # Setup auto-resolve alerts background task
    resolve_task = asyncio.create_task(auto_resolve_stale_alerts_loop())
    print("Starting up auto-resolve stale alerts task...")

    yield

    # Teardown
    mqtt_service.stop()
    print("MQTT Bridge stopped.")

    resolve_task.cancel()
    try:
        await resolve_task
    except asyncio.CancelledError:
        print("Auto-resolve task stopped.")

    print("Shutting down background tasks...")

app = FastAPI(
    title="Elderly Monitoring IoT Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/firmware", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from app.api.api_v1.api import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Elderly Monitoring API is running"}
