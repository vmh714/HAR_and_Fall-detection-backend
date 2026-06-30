from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings


def create_session_factory():
    """Tạo một cặp (engine, sessionmaker) ĐỘC LẬP với pool riêng.

    Dùng cho MQTT bridge chạy trên event loop của THREAD RIÊNG: asyncpg gắn
    connection vào đúng loop đã tạo nó, nên KHÔNG được dùng chung engine với HTTP
    (chạy trên main loop của uvicorn) — cross-loop sẽ ném "attached to a different
    loop". Mỗi loop → một engine riêng.
    """
    eng = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return eng, factory


# Engine + Session Factory mặc định cho HTTP (main loop).
engine, AsyncSessionLocal = create_session_factory()

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
