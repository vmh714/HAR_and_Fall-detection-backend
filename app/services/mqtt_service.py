import json
import asyncio
import ssl
import aiomqtt
from datetime import datetime
from sqlalchemy import select, update
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.domain import Device, Alert, DeviceEvent, Wearer
from app.schemas.mqtt import StatusPayload, AlertPayload, EventPayload

class MQTTService:
    def __init__(self):
        self.client = None
        self.topics = [
            "eldercare/+/status",
            "eldercare/+/alert/fall",
            "eldercare/+/event"
        ]

    async def run(self):
        """Main loop for MQTT client"""
        reconnect_interval = 5
        
        # Khởi tạo SSL Context nếu dùng mqtts hoặc wss
        tls_context = None
        if settings.MQTT_PROTOCOL in ["mqtts", "wss"]:
            tls_context = ssl.create_default_context()

        while True:
            try:
                async with aiomqtt.Client(
                    hostname=settings.MQTT_HOST,
                    port=settings.MQTT_PORT,
                    username=settings.MQTT_USERNAME,
                    password=settings.MQTT_PASSWORD,
                    tls_context=tls_context
                ) as client:
                    self.client = client
                    print(f"Connected to MQTT Broker at {settings.MQTT_HOST}")
                    
                    for topic in self.topics:
                        await client.subscribe(topic)
                    
                    async for message in client.messages:
                        await self.handle_message(message)
            
            except aiomqtt.MqttError as error:
                print(f"MQTT Error: {error}. Reconnecting in {reconnect_interval}s...")
                await asyncio.sleep(reconnect_interval)
            except Exception as e:
                print(f"Unexpected MQTT Error: {e}. Reconnecting in {reconnect_interval}s...")
                await asyncio.sleep(reconnect_interval)

    async def handle_message(self, message):
        topic = message.topic.value
        payload_str = message.payload.decode()
        print(f"Received MQTT message on {topic}: {payload_str}")
        
        try:
            data = json.loads(payload_str)
            parts = topic.split('/')
            device_id = parts[1]
            topic_type = "/".join(parts[2:])

            async with AsyncSessionLocal() as db:
                if topic_type == "status":
                    await self.process_status(db, device_id, data)
                elif topic_type == "alert/fall":
                    await self.process_alert(db, device_id, data)
                elif topic_type == "event":
                    await self.process_event(db, device_id, data)
                
                await db.commit()
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    async def process_status(self, db, device_id, data):
        payload = StatusPayload(**data)
        # Update device status in Postgres with current UTC time
        await db.execute(
            update(Device).where(Device.device_id == device_id).values(
                battery_pct=payload.battery_pct,
                last_online=datetime.utcnow()
            )
        )
        print(f"Updated status for device {device_id}")

    async def process_alert(self, db, device_id, data):
        payload = AlertPayload(**data)
        
        # Get current wearer if exists
        result = await db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        wearer_id = device.current_wearer_id if device else None

        new_alert = Alert(
            device_id=device_id,
            wearer_id=wearer_id,
            alert_type="FALL_DETECTED",
            confidence=payload.confidence,
            is_resolved=False
        )
        db.add(new_alert)
        print(f"Recorded Fall Alert for device {device_id}")

    async def process_event(self, db, device_id, data):
        payload = EventPayload(**data)
        
        # Get current wearer if exists
        result = await db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        wearer_id = device.current_wearer_id if device else None

        new_event = DeviceEvent(
            device_id=device_id,
            wearer_id=wearer_id,
            event_type=payload.event_type,
            description=payload.description
        )
        db.add(new_event)
        print(f"Recorded Event {payload.event_type} for device {device_id}")

mqtt_service = MQTTService()
