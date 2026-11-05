import json
from pathlib import Path

import pytest

from tests.support.operations import Operation
from tests.support.replay import replay

pytestmark = pytest.mark.postgres
SEQUENCES = Path(__file__).parent / "sequences"


@pytest.mark.parametrize("path", sorted(SEQUENCES.glob("*.json")), ids=lambda p: p.stem)
async def test_saved_sequence(client, path):
    await replay(
        client, [Operation(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
    )
