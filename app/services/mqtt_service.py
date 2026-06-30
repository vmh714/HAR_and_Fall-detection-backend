import json
import re
import asyncio
import ssl
import threading
import aiomqtt
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db.session import AsyncSessionLocal, create_session_factory
from app.models.domain import Device, Alert, DeviceEvent, Wearer
from app.models.base import Organization
from app.schemas.mqtt import StatusPayload, AlertPayload, EventPayload

class MQTTService:
    def __init__(self):
        self.client = None
        self.topics = [
            "eldercare/+/status",
            "eldercare/+/config/status",
            "eldercare/+/alert/fall",
            "eldercare/+/event"
        ]
        # Mỗi loop có engine riêng (xem run()); handle_message dùng factory này,
        # fallback về AsyncSessionLocal khi gọi trực tiếp ngoài thread (vd test).
        self.session_factory = None
        # Trạng thái thread giám sát (xem start()/stop()).
        self._thread: threading.Thread | None = None
        self._stop: threading.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Thread supervisor ─────────────────────────────────────────────────────
    # MQTT chạy trên THREAD RIÊNG + event loop riêng. Lý do: aiomqtt đăng ký socket
    # broker vào selector của loop đang chạy. Nếu socket chết đột ngột lúc mạng flap,
    # selector ném OSError [WinError 10038] ở TẦNG EVENT LOOP — không try/except nào
    # trong coroutine bắt được, cả loop chết. Trước đây MQTT là task trên main loop
    # của uvicorn → kéo sập luôn HTTP server (mất device card). Tách thread riêng:
    # loop MQTT sập thì chỉ thread này dựng lại, main loop (HTTP) sống nguyên.
    def start(self):
        """Khởi động MQTT bridge trên thread daemon riêng."""
        if self._thread and self._thread.is_alive():
            return
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._thread_main, name="mqtt-bridge", daemon=True)
        self._thread.start()

    def _thread_main(self):
        assert self._stop is not None
        while not self._stop.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(self.run())
            except Exception as e:
                # Bao gồm WinError 10038 thoát ra từ run_until_complete — nuốt ở đây
                # để dựng lại loop, KHÔNG để lan ra giết process.
                print(f"[MQTT] event loop sập ({e!r}); dựng lại sau 5s...")
            finally:
                self._loop = None
                try:
                    loop.close()
                except Exception:
                    pass
            if not self._stop.is_set():
                self._stop.wait(5)

    def stop(self):
        """Dừng MQTT bridge (gọi khi app shutdown)."""
        if not self._thread:
            return
        if self._stop:
            self._stop.set()
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=10)
        self._thread = None

    async def publish(self, topic: str, payload, qos: int = 1, retain: bool = False):
        """Publish AN TOÀN từ event loop KHÁC (vd HTTP handler trên main loop của
        uvicorn). aiomqtt client sống trên loop của thread MQTT → không được await
        client.publish() trực tiếp (future ack thuộc loop khác → "attached to a
        different loop"). Schedule coroutine sang đúng loop MQTT bằng
        run_coroutine_threadsafe, rồi bắc cầu kết quả về loop gọi qua wrap_future
        (không block loop gọi)."""
        loop = self._loop
        client = self.client
        if loop is None or client is None or loop.is_closed():
            raise RuntimeError("MQTT bridge chưa sẵn sàng")
        cfut = asyncio.run_coroutine_threadsafe(
            client.publish(topic, payload=payload, qos=qos, retain=retain), loop
        )
        await asyncio.wrap_future(cfut)

    async def run(self):
        """Main loop for MQTT client — chạy trong event loop của thread riêng."""
        reconnect_interval = 5

        # Engine riêng cho loop hiện tại (asyncpg pool gắn với loop này).
        engine, self.session_factory = create_session_factory()

        # Khởi tạo SSL Context nếu dùng mqtts hoặc wss
        tls_context = None
        if settings.MQTT_PROTOCOL in ["mqtts", "wss"]:
            tls_context = ssl.create_default_context()

        try:
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
        finally:
            self.session_factory = None
            await engine.dispose()

    async def handle_message(self, message):
        topic = message.topic.value
        payload_str = message.payload.decode()
        print(f"Received MQTT message on {topic}: {payload_str}")
        
        try:
            data = json.loads(payload_str)
            parts = topic.split('/')
            # parts[1] = khóa topic = MAC (vân tay phần cứng), KHÔNG phải device_id ngữ nghĩa
            mac = parts[1]
            topic_type = "/".join(parts[2:])

            data["device_id"] = mac  # MQTTBase.device_id (str) — chỉ để thoả schema

            # Dùng engine của loop MQTT (self.session_factory); fallback global khi
            # process_* được gọi trực tiếp ngoài thread (vd unit test).
            session_factory = self.session_factory or AsyncSessionLocal
            async with session_factory() as db:
                if topic_type == "status":
                    await self.process_status(db, mac, data)
                elif topic_type == "config/status":
                    await self.process_config_status(db, mac, data)
                elif topic_type == "alert/fall":
                    await self.process_alert(db, mac, data)
                elif topic_type == "event":
                    await self.process_event(db, mac, data)

                await db.commit()
        except Exception as e:
            # KHÔNG nuốt im lặng: với alert "sống còn" (QoS1) một lỗi validation =
            # mất cảnh báo ngã. Log đủ topic + payload để truy vết / dead-letter.
            print(f"[MQTT][DROP] topic={topic} err={e} payload={payload_str}")

    # ── Auto-provision helpers ────────────────────────────────────────────────
    async def _resolve_org_id(self, db):
        """Org nhận thiết bị auto-provision: settings.ORG_ID nếu set, else org duy nhất (cũ nhất)."""
        if settings.ORG_ID:
            return UUID(settings.ORG_ID)
        result = await db.execute(
            select(Organization).order_by(Organization.created_at).limit(1)
        )
        org = result.scalar_one_or_none()
        return org.id if org else None

    async def _next_device_id(self, db, org_id):
        """Sinh device_id ngữ nghĩa kế tiếp trong org: esp32_eldercare_01, _02, ..."""
        prefix = settings.DEVICE_ID_PREFIX
        result = await db.execute(
            select(Device.device_id).where(Device.org_id == org_id)
        )
        pat = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        max_n = 0
        for did in result.scalars().all():
            m = pat.match(did or "")
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"{prefix}{max_n + 1:02d}"

    async def _get_or_create_device_by_mac(self, db, mac):
        """Khớp Device theo MAC (khóa topic); chưa có thì auto-provision với device_id ngữ nghĩa."""
        result = await db.execute(
            select(Device).options(selectinload(Device.wearer)).where(Device.mac == mac)
        )
        device = result.scalar_one_or_none()
        if device:
            return device

        org_id = await self._resolve_org_id(db)
        if org_id is None:
            print(f"[MQTT] Bỏ qua auto-provision mac={mac}: chưa có Organization nào")
            return None

        # Migration: nhận lại thiết bị cũ (đăng ký trước khi có cột mac). Nếu org có ĐÚNG MỘT
        # device chưa gắn mac → coi đây chính là nó: gắn mac, giữ nguyên device_id + toàn bộ lịch
        # sử (Postgres alerts/events + InfluxDB tag device_id không đổi → log cũ/mới liền mạch).
        if settings.ADOPT_SINGLE_LEGACY_DEVICE:
            legacy = await db.execute(
                select(Device).options(selectinload(Device.wearer))
                .where(Device.org_id == org_id, Device.mac.is_(None))
            )
            legacy_devices = legacy.scalars().all()
            if len(legacy_devices) == 1:
                dev = legacy_devices[0]
                dev.mac = mac
                print(f"Adopted legacy device {dev.device_id} → mac={mac}")
                return dev

        device_id = await self._next_device_id(db, org_id)
        device = Device(device_id=device_id, mac=mac, org_id=org_id, is_active=True)
        db.add(device)
        try:
            await db.flush()
        except IntegrityError:
            # Hiếm: 2 message gần nhau tạo trùng — rollback rồi đọc lại theo mac
            await db.rollback()
            result = await db.execute(
                select(Device).options(selectinload(Device.wearer)).where(Device.mac == mac)
            )
            return result.scalar_one_or_none()
        print(f"Auto-provisioned {device_id} (mac={mac})")
        return device

    # ── Handlers ──────────────────────────────────────────────────────────────
    async def process_config_status(self, db, mac, data):
        from app.schemas.mqtt import ConfigStatusPayload
        payload = ConfigStatusPayload(**data)

        # config/status fire lúc connect/reconnect (trước status đầu) → điểm provision đẹp nhất
        device = await self._get_or_create_device_by_mac(db, mac)
        if not device:
            return

        if payload.interval is not None and device.telemetry_interval != payload.interval:
            device.telemetry_interval = payload.interval
        if payload.fall_threshold is not None and device.fall_threshold != payload.fall_threshold:
            device.fall_threshold = payload.fall_threshold
        if payload.fall_cooldown is not None and device.fall_cooldown != payload.fall_cooldown:
            device.fall_cooldown = payload.fall_cooldown
        if payload.fall_confirm_window is not None and device.fall_confirm_window != payload.fall_confirm_window:
            device.fall_confirm_window = payload.fall_confirm_window
        if payload.stream_timeout is not None and device.stream_timeout != payload.stream_timeout:
            device.stream_timeout = payload.stream_timeout
        if payload.rssi_interval is not None and device.rssi_interval != payload.rssi_interval:
            device.rssi_interval = payload.rssi_interval
        # Auto-report firmware version (đúng sau mỗi OTA reboot vì device reconnect)
        if payload.fw_version and device.firmware_version != payload.fw_version:
            device.firmware_version = payload.fw_version

        print(f"Updated config status from {device.device_id} (mac={mac})")

    async def process_status(self, db, mac, data):
        from app.db.influx_client import influx_manager, Point
        payload = StatusPayload(**data)

        # 1. Update Postgres (Current status for Dashboard) — provision dự phòng nếu lỡ config/status
        device = await self._get_or_create_device_by_mac(db, mac)
        if not device:
            return

        device.battery_pct = payload.battery_pct
        device.last_online = datetime.fromtimestamp(payload.timestamp, timezone.utc) if payload.timestamp else datetime.now(timezone.utc)
        if payload.rssi is not None:
            device.last_rssi = payload.rssi

        # 2. Calculate Distance if wearer exists
        # Đếm walk/run riêng (firmware D-010) → quãng đường đúng theo loại:
        #   distance = walk_steps * 0.415*h + run_steps * 0.5*h
        distance_m = 0.0
        if device.wearer:
            height_m = device.wearer.height_cm / 100
            distance_m = (payload.walk_steps * 0.415 * height_m) + (payload.run_steps * 0.5 * height_m)

        # 3. Write to InfluxDB (Historical data for Charts)
        # Tag bằng device_id NGỮ NGHĨA (không phải mac) để history/FE nhất quán với dashboard.
        point = (
            Point("telemetry")
            .tag("device_id", device.device_id)
            .tag("state", payload.state)
            .tag("ai_pred", payload.ai_pred)
            .field("battery_pct", float(payload.battery_pct))
            .field("steps", int(payload.steps))
            .field("walk_steps", int(payload.walk_steps))
            .field("run_steps", int(payload.run_steps))
            .field("ai_conf", float(payload.ai_conf))
            .field("distance_m", float(distance_m))
        )
        if device.wearer and device.current_wearer_id:
            point = point.tag("wearer_id", str(device.current_wearer_id))
        # rssi chỉ ghi khi payload có (firmware đọc AT+CSQ — hiện chưa gửi). Khi
        # firmware bổ sung, đường ghi này đã sẵn → Vitals chart hết rỗng.
        if payload.rssi is not None:
            point = point.field("rssi", int(payload.rssi))
        if payload.timestamp:
            point.time(datetime.fromtimestamp(payload.timestamp, timezone.utc))
        influx_manager.write_point(point)

        print(f"Updated status & InfluxDB for {device.device_id} (mac={mac}, Dist: {distance_m:.1f}m)")

    async def process_alert(self, db, mac, data):
        payload = AlertPayload(**data)

        device = await self._get_or_create_device_by_mac(db, mac)
        wearer_id = device.current_wearer_id if device else None

        if not wearer_id:
            print(f"Skipped Fall Alert for mac={mac}: no wearer mounted")
            return

        new_alert = Alert(
            device_id=device.device_id,
            wearer_id=wearer_id,
            alert_type="FALL_DETECTED",
            confidence=payload.confidence,
            is_resolved=False,
            created_at=datetime.fromtimestamp(payload.timestamp, timezone.utc) if payload.timestamp else datetime.now(timezone.utc)
        )
        db.add(new_alert)
        print(f"Recorded Fall Alert for {device.device_id} (mac={mac})")

    async def process_event(self, db, mac, data):
        payload = EventPayload(**data)

        device = await self._get_or_create_device_by_mac(db, mac)
        if not device:
            return
        wearer_id = device.current_wearer_id

        new_event = DeviceEvent(
            device_id=device.device_id,
            wearer_id=wearer_id,
            event_type=payload.event_type,
            description=payload.description,
            created_at=datetime.fromtimestamp(payload.timestamp, timezone.utc) if payload.timestamp else datetime.now(timezone.utc)
        )
        db.add(new_event)
        print(f"Recorded Event {payload.event_type} for {device.device_id} (mac={mac})")

mqtt_service = MQTTService()
