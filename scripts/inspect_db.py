import asyncio
import sys
import os
from sqlalchemy import text

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine

async def inspect():
    async with engine.connect() as conn:
        # Get tables
        tables = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        print("Tables in public schema:")
        for row in tables:
            print(f" - {row[0]}")
        
        # Get custom types (enums)
        enums = await conn.execute(text("SELECT n.nspname as schema, t.typname as type FROM pg_type t LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace WHERE (t.typrelid = 0 OR (SELECT c.relkind = 'c' FROM pg_catalog.pg_class c WHERE c.oid = t.typrelid)) AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el WHERE el.oid = t.typelem AND el.typarray = t.oid) AND n.nspname = 'public'"))
        print("\nCustom types in public schema:")
        for row in enums:
            print(f" - {row[1]}")

if __name__ == "__main__":
    asyncio.run(inspect())
