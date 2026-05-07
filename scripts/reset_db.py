import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine

async def reset():
    async with engine.begin() as conn:
        print("Dropping all tables and types...")
        # Drop all tables
        await conn.execute(text("DROP TABLE IF EXISTS devices CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS wearers CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS organizations CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        
        # Drop enums
        await conn.execute(text("DROP TYPE IF EXISTS user_role;"))
        await conn.execute(text("DROP TYPE IF EXISTS userrole;"))
        
        print("Reset complete.")

if __name__ == "__main__":
    asyncio.run(reset())
