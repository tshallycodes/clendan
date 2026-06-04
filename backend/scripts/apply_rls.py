import asyncio


async def main():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    sql = open("migrations/001_enable_rls.sql").read()
    statements = [
        s.strip()
        for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]

    for stmt in statements:
        try:
            await db.execute_raw(stmt)
            print("OK:", stmt[:80])
        except Exception as e:
            msg = str(e)
            if "already exists" in msg or "already enabled" in msg.lower():
                print("SKIP (already applied):", stmt[:60])
            else:
                print("ERR:", msg[:120])

    await db.disconnect()
    print("Done.")


asyncio.run(main())
