import asyncio
import sys
import os

# Ensure the parent directory is in the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.base import Organization
from app.models.domain import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def main():
    async with AsyncSessionLocal() as session:
        # Check if organization exists
        org_result = await session.execute(select(Organization).filter_by(name="Default Org"))
        org = org_result.scalar_one_or_none()

        if not org:
            print("Creating Default Organization...")
            org = Organization(name="Default Org", address="123 Admin St")
            session.add(org)
            await session.commit()
            await session.refresh(org)
            print(f"Created Org: {org.id}")

        # Check if admin user exists
        user_result = await session.execute(select(User).filter_by(username="admin"))
        user = user_result.scalar_one_or_none()

        if not user:
            print("Creating Admin User...")
            user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                org_id=org.id
            )
            session.add(user)
            await session.commit()
            print("Admin User created successfully!")
        else:
            print("Admin User already exists.")
            # Optionally update password
            user.password_hash = get_password_hash("admin123")
            session.add(user)
            await session.commit()
            print("Admin User password updated to 'admin123'.")

if __name__ == "__main__":
    asyncio.run(main())
