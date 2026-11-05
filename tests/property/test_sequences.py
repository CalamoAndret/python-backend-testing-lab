import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.support.database import reset_database
from tests.support.operations import operations
from tests.support.replay import replay

pytestmark = pytest.mark.postgres


@settings(
    max_examples=35, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.lists(operations, min_size=1, max_size=35))
async def test_generated_sequences_against_reference(client, database, sequence):
    # Pytest fixtures are per function, not per Hypothesis example: reset explicitly.
    await reset_database(database.engine)
    await replay(client, sequence)
