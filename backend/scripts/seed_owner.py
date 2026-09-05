import asyncio

from app.scripts.seed_owner import seed


if __name__ == "__main__":
    asyncio.run(seed())
