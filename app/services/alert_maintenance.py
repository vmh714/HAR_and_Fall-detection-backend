import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import update
from app.db.session import AsyncSessionLocal
from app.models.domain import Alert
from app.core.config import settings

logger = logging.getLogger(__name__)

async def auto_resolve_stale_alerts_loop():
    """
    Vòng lặp background quét và tự động chuyển các alert chưa được xử lý (is_resolved = False)
    đã quá thời hạn (mặc định 24h) thành trạng thái is_resolved = True.
    """
    logger.info("Starting stale alert auto-resolve loop.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=settings.ALERT_AUTO_RESOLVE_HOURS)
            
            async with AsyncSessionLocal() as session:
                stmt = (
                    update(Alert)
                    .where(Alert.is_resolved == False)
                    .where(Alert.created_at < cutoff_time)
                    .values(is_resolved=True)
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Auto-resolved {result.rowcount} stale alerts older than {settings.ALERT_AUTO_RESOLVE_HOURS} hours.")
                
        except asyncio.CancelledError:
            logger.info("Stale alert auto-resolve loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in auto_resolve_stale_alerts_loop: {e}")
        
        # Ngủ một khoảng thời gian trước khi quét lại
        try:
            await asyncio.sleep(settings.ALERT_AUTO_RESOLVE_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Stale alert auto-resolve loop cancelled during sleep.")
            break
