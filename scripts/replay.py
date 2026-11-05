"""Replay a saved sequence against the real API and a fresh dedicated test database."""

import argparse
import asyncio
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from testing_lab.config import Settings
from testing_lab.main import create_app
from tests.support.database import guarded_test_url, reset_database
from tests.support.operations import Operation
from tests.support.replay import replay


async def run(path: Path) -> None:
    contents = await asyncio.to_thread(path.read_text, encoding="utf-8")
    sequence = [Operation(**item) for item in json.loads(contents)]
    app = create_app(Settings(database_url=guarded_test_url()))
    async with app.router.lifespan_context(app):
        await reset_database(app.state.database.engine)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://replay"
        ) as client:
            await replay(client, sequence)
    print(f"Replayed {len(sequence)} operations successfully from {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sequence", type=Path)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.sequence))
