"""One-off script: mark all non-disconnected TrueLayer integrations as disconnected."""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def main():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    result = await db.integration.update_many(
        where={"type": "truelayer", "status": {"not": "disconnected"}},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    print(f"Marked {result} TrueLayer integration(s) as disconnected.")

    await db.disconnect()


asyncio.run(main())
