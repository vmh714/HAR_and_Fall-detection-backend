import asyncio
import uuid
from app.db.session import async_session
from app.models.domain import Organization

async def create_org():
    async with async_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Test Hospital",
            address="123 Street"
        )
        session.add(org)
        await session.commit()
        print(f"Created Org: {org.id}")
        return org.id

if __name__ == "__main__":
    asyncio.run(create_org())
