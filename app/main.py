from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager
from app.patch_loop import patch_asyncio_loop

# Apply Windows loop patch early
patch_asyncio_loop()

from app.services.mqtt_service import mqtt_service
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup MQTT connection in background
    mqtt_task = asyncio.create_task(mqtt_service.run())
    print("Starting up MQTT Bridge...")
    yield
    # Teardown MQTT connection
    mqtt_task.cancel()
    try:
        await mqtt_task
    except asyncio.CancelledError:
        print("MQTT Bridge stopped.")
    print("Shutting down MQTT Bridge...")

app = FastAPI(
    title="Elderly Monitoring IoT Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Explicitly allow frontend origin for credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.api_v1.api import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Elderly Monitoring API is running"}
