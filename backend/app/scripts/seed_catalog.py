"""Compatibility entry point for the retired 15-product demo catalog seed.

The authoritative source is now ``data/anicraze_final_product_master.csv``.
"""

import asyncio

from app.scripts.import_final_catalog import import_catalog


async def seed() -> None:
    await import_catalog()


if __name__ == "__main__":
    asyncio.run(seed())
