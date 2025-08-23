import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import app, lifespan


async def run_startup():
    async with lifespan(app):
        print('startup ok')


if __name__ == '__main__':
    asyncio.run(run_startup())
