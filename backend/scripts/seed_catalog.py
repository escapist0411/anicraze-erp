from app.scripts.seed_catalog import seed
import asyncio

if __name__ == "__main__":
    asyncio.run(seed())
