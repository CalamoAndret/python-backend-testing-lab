import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from testing_lab.config import Settings
from testing_lab.main import create_app
from tests.support.database import guarded_test_url, reset_database
from tests.support.operations import Operation, operations
from tests.support.reference import ReferenceModel
from tests.support.replay import record_failure, request_for


class TaskAPIStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.app = create_app(Settings(database_url=guarded_test_url()))
        self.runner = asyncio.Runner()
        self.lifespan = self.app.router.lifespan_context(self.app)
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://stateful")
        self.runner.run(self.start())
        self.model = ReferenceModel()
        self.history = []

    async def start(self):
        await self.lifespan.__aenter__()
        await self.client.__aenter__()
        await reset_database(self.app.state.database.engine)

    def execute(self, operation):
        self.history.append(operation)
        try:
            method, path, kwargs = request_for(self.model, operation)
            response = self.runner.run(self.client.request(method, path, **kwargs))
            self.model.accept(
                operation, response.status_code, response.json() if response.content else None
            )
        except Exception:
            record_failure(self.history)
            raise

    @rule(operation=operations)
    def arbitrary_operation(self, operation):
        self.execute(operation)

    @rule(slot=st.integers(0, 3))
    def lifecycle(self, slot):
        self.execute(Operation("create", slot))
        self.execute(Operation("update", slot, status="in_progress"))
        self.execute(Operation("update", slot, status="completed"))
        self.execute(Operation("update", slot, status="pending"))

    @invariant()
    def database_matches_model(self):
        try:
            snapshot = self.runner.run(self.client.get("/tasks", params={"limit": 100})).json()[
                "items"
            ]
            self.model.assert_snapshot(snapshot)
        except Exception:
            record_failure(self.history)
            raise

    def teardown(self):
        async def close():
            await self.client.__aexit__(None, None, None)
            await self.lifespan.__aexit__(None, None, None)

        self.runner.run(close())
        self.runner.close()


TestTaskAPI = TaskAPIStateMachine.TestCase
TestTaskAPI.settings = settings(max_examples=15, stateful_step_count=20, deadline=None)
TestTaskAPI = pytest.mark.postgres(TestTaskAPI)
