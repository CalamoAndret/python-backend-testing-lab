# Python Backend Testing Lab

[![CI and PostgreSQL tests](https://github.com/CalamoAndret/python-backend-testing-lab/actions/workflows/ci.yml/badge.svg?branch=main&label=CI%20%26%20PostgreSQL%20tests)](https://github.com/CalamoAndret/python-backend-testing-lab/actions/workflows/ci.yml)

A FastAPI and PostgreSQL task API built to make backend correctness observable.
It demonstrates what happens when valid requests **race, retry, or fail halfway
through a transaction**, with executable tests for each contract.

The core is small enough to review: atomic version predicates prevent lost updates,
durable idempotency keys preserve creation responses, and generated API sequences
are checked against an independent reference model. Saved traces turn failures into
replayable regressions. No performance benchmarks are claimed.

[Run the API](#run-with-docker) · [Request/response walkthrough](docs/api-walkthrough.md) · [Architecture](#architecture) · [Testing strategy](#testing-strategy) · [Security](SECURITY.md)

## Engineering highlights

| Concern | Implementation | Evidence to review |
| --- | --- | --- |
| Lost updates | Version condition inside PostgreSQL UPDATE/DELETE | [Repositories](src/testing_lab/repositories.py), [synchronized race tests](tests/integration/test_concurrency.py) |
| Retried creation | Key reservation, task, and saved response in one transaction | [Service](src/testing_lab/services.py), [idempotency race tests](tests/integration/test_concurrency.py) |
| Transaction failures | Commit before success, rollback on exceptions | [Fault-injection tests](tests/integration/test_transactions.py) |
| Stateful correctness | Generated operations compared with an independent model | [Oracle](tests/support/reference.py), [Hypothesis state machine](tests/property/test_state_machine.py) |
| Reproducible debugging | Logical-slot JSON traces and a replay harness | [Replay support](tests/support/replay.py), [saved regressions](tests/regression/sequences/) |
| Test effectiveness | Opt-in broken UPDATE must fail a specific race test | [Mutation demonstration](scripts/demonstrate_bug.py) |

## Features and stack

- Async task CRUD with UUIDs, validation, filtering, pagination, and OpenAPI docs.
- Explicit status transitions, timestamps, priority, and version numbers.
- Atomic optimistic concurrency on updates and deletes.
- Persistent idempotency keys, including concurrent retries and application restarts.
- Database constraints, transaction boundaries, rollback, and structured errors.
- Unit, API, PostgreSQL integration, property, state machine, race, and regression tests.
- Deterministic JSON replay and an isolated bug detection demonstration.
- Alembic migrations, a non-root runtime image, Docker Compose, and GitHub Actions.

**Technology:** Python 3.12+, FastAPI, PostgreSQL 17, SQLAlchemy 2.0 async, asyncpg,
Alembic, Pydantic v2, pytest, pytest-asyncio, Hypothesis, HTTPX, Ruff, coverage.py,
Docker, and GitHub Actions. `uv.lock` records runtime and development dependencies.
Python 3.12 is the verified baseline; newer interpreters are not claimed as tested.

## Architecture

```mermaid
flowchart TD
    C[HTTP client] --> A[FastAPI routes and Pydantic schemas]
    A --> S[Services: business rules and transactions]
    S --> R[Task and idempotency repositories]
    R --> D[(PostgreSQL: constraints and atomic writes)]
    M[Alembic migrations] --> D
    T[pytest + HTTPX + Hypothesis] --> A
    T --> O[Independent reference model]
    T --> L[Barriers, events, database lock observer]
    F[Saved operation sequences] --> T
```

Routes handle HTTP concerns; services own transactions and business decisions;
repositories issue SQLAlchemy 2 statements. Each request owns an `AsyncSession`.
Concurrent requests never share sessions. Schema creation happens through Alembic,
not application startup. Production code uses type hints and explicit contracts.

## Run with Docker

Install Docker with Compose v2, then run from the repository root:

```bash
docker compose up --build
```

Compose waits for PostgreSQL, runs migrations as a one-shot service, and starts
the API on port 8000.

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI: <http://localhost:8000/openapi.json>
- Liveness: <http://localhost:8000/health/live>
- Database/schema readiness: <http://localhost:8000/health/ready>

The defaults in `.env.example` are local development credentials. Copy it to `.env`
to customize them. Compose constructs its database URLs using hostname `db`;
host-side commands use `localhost`. The sample Compose interpolation requires
URL-safe usernames/passwords; use letters and digits for these disposable values.
In independently configured `DATABASE_URL` values, percent-encode reserved characters.
Both the API and PostgreSQL are published on loopback only. The database's named
volume persists across restarts. `testing_lab_test` is reserved for disposable test
data; do not configure it as the application database.

```bash
docker compose down
```

`docker compose down -v` also **deletes** the database volume. Initialization SQL
creates `testing_lab_test` only on a new volume. If your volume predates that file:

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" testing_lab_test'
```

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv sync --locked --python 3.12
docker compose up -d db
cp .env.example .env
uv run --no-sync alembic upgrade head
uv run --no-sync uvicorn testing_lab.main:app --reload
```

On PowerShell, `Copy-Item .env.example .env` also works. Alternatively use an existing
PostgreSQL instance: create an application database and a **separate disposable**
test database ending in `_test`, and configure the URLs. SQLite is not a substitute
for the PostgreSQL tests.

Settings read `.env` and environment variables: `DATABASE_URL`, `DB_POOL_SIZE`
(default 10), and `DB_MAX_OVERFLOW` (default 10). Statements have a 10-second timeout;
lock waits have a 5-second timeout. Migrations run separately from worker startup.

## API examples

See the [executed request/response walkthrough](docs/api-walkthrough.md) for creation,
replay, a successful update, a stale-version conflict, and deletion against a real
local PostgreSQL-backed API. UUIDs and timestamps in that capture are run-specific.

Examples use Bash and curl. On Windows use `curl.exe` with PowerShell JSON quoting,
or use Swagger UI. Replace `TASK_UUID` with the returned UUID and use its version.

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: interview-demo-001' \
  -d '{"title":"Review races","description":"Explain the invariant","priority":1}'

curl 'http://localhost:8000/tasks?status=pending&priority=1&limit=10&offset=0'
curl http://localhost:8000/tasks/TASK_UUID

curl -X PATCH http://localhost:8000/tasks/TASK_UUID \
  -H 'Content-Type: application/json' \
  -d '{"expected_version":1,"status":"in_progress"}'

curl -i -X DELETE 'http://localhost:8000/tasks/TASK_UUID?expected_version=2'
```

The following response was captured from a real synthetic `POST /tasks` using
`{"title":"Review transaction boundaries","description":"Synthetic documentation example","priority":1}`
and `Idempotency-Key: docs-demo-20261106-001`. Transport headers are omitted.
The [complete walkthrough](docs/api-walkthrough.md) includes the exact request and
the subsequent retry, update, conflict, and deletion responses.

```http
HTTP/1.1 201 Created
content-type: application/json
location: /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3
idempotency-replayed: false

{
  "id": "60adffc9-b2db-4bf7-8e85-e5656540f9d3",
  "title": "Review transaction boundaries",
  "description": "Synthetic documentation example",
  "status": "pending",
  "priority": 1,
  "created_at": "2026-11-06T13:35:55.789890Z",
  "updated_at": "2026-11-06T13:35:55.789890Z",
  "version": 1
}
```

| Endpoint | Success | Contract |
| --- | --- | --- |
| `POST /tasks` | 201 | Title required; optional `Idempotency-Key` |
| `GET /tasks` | 200 | Status/priority filters; limit 1–100, offset 0–1,000,000 |
| `GET /tasks/{uuid}` | 200 | Current task |
| `PATCH /tasks/{uuid}` | 200 | `expected_version` and at least one changed field |
| `DELETE /tasks/{uuid}` | 204 | Required `expected_version` query parameter |
| `GET /health/live` | 200 | Process responds without database access |
| `GET /health/ready` | 200 | Database reachable and both tables queryable |

Tasks contain `id`, `title`, `description`, `status`, `priority`, `created_at`,
`updated_at`, and `version`. Title whitespace is trimmed; titles are 1–200 characters,
descriptions at most 10,000 characters. NUL and unpaired Unicode surrogates are
rejected before persistence. Priority is a strict integer from 1 (highest) to 5.
Creation starts at `pending`, version 1. Timestamps are timezone-aware and serialized
in UTC. Unknown fields, explicit null changes, and empty PATCH requests are rejected.
Each accepted update increments the version, including a same-value update.
Version inputs range from 1 to 2,147,483,646.

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> in_progress
    pending --> cancelled
    in_progress --> completed
    in_progress --> cancelled
    completed --> [*]
    cancelled --> [*]
```

Keeping the same status is allowed. Terminal tasks cannot be reopened, but descriptive
fields remain editable with the current version. Errors use a stable envelope:

```json
{
  "error": {
    "code": "version_conflict",
    "message": "Task changed; fetch it and retry with its version.",
    "details": []
  }
}
```

Missing tasks return 404. Stale versions, invalid transitions, and key/payload
conflicts return 409. Input errors return 422 with field locations. Database
failures return sanitized 503 errors; unexpected failures return sanitized 500s.
Resolve version conflicts by fetching current state before deciding how to retry.

Pagination returns `items`, `limit`, `offset`, and `has_more`. Fetching one extra
row avoids a separate count query. Ordering is `(created_at, id)` to break timestamp
ties. Different offset pages do not form a snapshot across concurrent changes.

## Concurrency and idempotency

### Atomic version checks

The service validates the current version and transition. The decisive write
also checks the version **inside SQL**:

```sql
UPDATE tasks
SET title = :title, version = version + 1, updated_at = clock_timestamp()
WHERE id = :id AND version = :expected_version
RETURNING *;
```

Two requests may both read version 1. PostgreSQL serializes their writes and
reevaluates the predicate against the changed row. Exactly one succeeds; the other
affects zero rows and returns 409. A Python pre-check alone cannot prevent this race.
Deletes use the same version predicate. A resource absent at the initial read gets
404; a resource changed/deleted after that read causes the losing write to get 409.

### Durable creation retries

Keys contain 1–128 ASCII letters, digits, dots, underscores, colons, or hyphens.

1. Validate and normalize the payload; hash canonical JSON with SHA-256.
2. In a transaction, reserve the key using `INSERT ... ON CONFLICT DO NOTHING`.
3. The owner inserts the task and stores the serialized response, then commits.
4. A concurrent contender waits on the primary key's unique index. After commit,
   a separate SELECT at READ COMMITTED reads the saved response. After rollback,
   the contender can acquire the reservation and create the task itself.

The task, reservation, and response commit together. Coordination works across
application instances without a Python mutex. Lock timeouts return 503; a client
can retry with the same key. A different payload for an existing key returns 409.
Omitted defaults and explicit defaults have identical fingerprints.

Retries return **the original creation response**, 201, `Location`, and
`Idempotency-Replayed: true`. The initial response uses `false`. Updating/deleting
the resource does not change this history: replay after deletion may reference a
task that now returns 404. Keys never expire or get reused in this sample.
Without a key, repeated POST requests intentionally create separate tasks.

The algorithm relies on PostgreSQL READ COMMITTED isolation. References:
[PostgreSQL conflict semantics](https://www.postgresql.org/docs/current/sql-insert.html),
[SQLAlchemy PostgreSQL insert support](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert).
The application explicitly configures this isolation level on its connections.

## Testing strategy

**Property-based testing** generates many operation sequences instead of relying only
on handwritten examples. Hypothesis explores creates, reads, updates, deletes, stale
versions, and key reuse. The independent model predicts outcomes and collection state;
the harness checks these against the actual API after every operation. Stateful rules
also exercise complete lifecycles and verify invariants. Shrinking helps find smaller
counterexamples. These bounded tests provide evidence, not a proof of all executions.

| Suite | What it demonstrates |
| --- | --- |
| Unit | Transition policy, validation, fingerprints, sanitized errors |
| API | CRUD, filters/pages, status codes, stale writes, persistent replay |
| PostgreSQL integration | Constraints, isolation, rollback, session recovery |
| Property | Generated operation sequences compared with an independent oracle |
| Stateful | Hypothesis rules, lifecycle sequences, invariants after each rule |
| Concurrency | Synchronized two-writer races and observed unique-index blocking |
| Regression | Checked-in JSON traces and automatic failing sequence capture |
| Mutation demonstration | A real race test detects a missing atomic version predicate |

The model tracks identities, live fields, versions, and original idempotency
responses. Its transition table is independent of production logic. Each generated
operation checks the HTTP result and then the complete database-visible collection.
Hypothesis shrinks failing examples.

Database tests use real migrated PostgreSQL and independent request transactions.
Fixtures truncate both tables between tests, and property tests reset between
Hypothesis examples. The test URL must be explicitly exported, use
`postgresql+asyncpg`, and name a database ending in `_test`. Always choose a
disposable database. Run tests serially; parallel workers/invocations sharing one
database are unsupported.

Races use barriers and events, without arbitrary sleeps. The idempotency test holds
an owner's reservation and queries `pg_blocking_pids` to prove a second backend is
blocked before releasing the owner. Both commit and rollback paths are exercised.
Deadlines bound synchronization failures.

### Run the full suite in containers

```bash
docker compose --profile test run --build --rm test
```

This migrates the dedicated test database, checks schema drift, runs coverage,
and verifies detection of the deliberately broken implementation.

### Run locally against PostgreSQL

With the Compose database running, Bash:

```bash
export TEST_DATABASE_URL='postgresql+asyncpg://lab:lab@localhost:5432/testing_lab_test'
DATABASE_URL="$TEST_DATABASE_URL" uv run --no-sync alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run --no-sync alembic check
uv run --no-sync pytest --cov --cov-report=term-missing --cov-report=xml
```

PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://lab:lab@localhost:5432/testing_lab_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync pytest --cov --cov-report=term-missing --cov-report=xml
```

`.env` is read by application settings, not the destructive test URL guard; export
`TEST_DATABASE_URL` explicitly. Restore the application `DATABASE_URL` before
launching the API from the same shell.

```bash
uv run --no-sync pytest -m 'not postgres'    # database-free tests
uv run --no-sync pytest -m concurrency      # synchronized races
uv run --no-sync pytest tests/property      # generated and stateful API tests
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m scripts.smoke_http  # optional, with a running local API
```

Coverage includes production branches with a 90% gate. Its greenlet setting
accounts for SQLAlchemy's async bridge
([coverage.py concurrency configuration](https://coverage.readthedocs.io/en/latest/config.html#run-concurrency)).
Subset runs without `--cov` do not impose whole-application coverage.

### Deterministic replay

Failures save a trace to `artifacts/replay.json`, using logical slots rather than
machine-specific UUIDs. The harness uses assertions; run without Python's `-O` flag.

```bash
uv run --no-sync python -m scripts.replay artifacts/replay.json
uv run --no-sync python -m scripts.replay tests/regression/sequences/stale_write.json
uv run --no-sync pytest tests/regression
```

Replay truncates the guarded test database and drives the real API. It preserves
operation order and semantic inputs, not random UUIDs/timestamps. Hypothesis reruns
and shrinks examples; the artifact is a failing prefix and may be overwritten by
subsequent failures. Copy useful traces into `tests/regression/sequences/`.
Concurrency schedules are reproduced by synchronization tests, not sequential replay.

### Reproducible bug demonstration

With a migrated database and `TEST_DATABASE_URL` exported:

```bash
uv run --no-sync python -m scripts.demonstrate_bug
```

An opt-in pytest plugin removes `Task.version == expected_version` from the
repository UPDATE while leaving the service pre-check intact. A barrier forces both
requests to finish reading before either writes. The race test fails because it
observes `[200, 200]` instead of `[200, 409]`.

The wrapper exits 0 **only when that specific failure is detected**. Infrastructure
errors do not count as bug detection. To see the raw expected failure (exit 1):

```bash
uv run --no-sync pytest -q -p demos.lost_update_plugin \
  tests/integration/test_concurrency.py::test_atomic_update_allows_exactly_one_winner
```

The plugin is never loaded by the application or ordinary suite. No source file
is changed. See [AI code evaluation](docs/AI_EVALUATION.md) for reviewing generated patches.

## CI and engineering tradeoffs

GitHub Actions installs the locked Python 3.12 environment, runs Ruff, migrates
PostgreSQL 17, checks schema drift, runs tests and coverage, verifies mutation
detection and replay, and tests downgrade/upgrade. Coverage and failure traces are
uploaded. A separate job builds containers, starts the API, checks readiness, and
runs the container suite. No automatic production deployment is configured. Actions
are pinned to full commit hashes, with checkout credentials persistence disabled.
Dependabot is configured for uv, Actions, and Docker updates; it has not executed
in this local workspace. See [the security policy](SECURITY.md) and
[publication audit](docs/PUBLICATION_AUDIT.md) before publishing or deploying.

- **PostgreSQL-specific correctness:** native conflict handling, JSONB, and atomic
  predicates expose the semantics being tested rather than hiding them behind portability.
- **Transaction ownership:** commits precede success responses; context managers
  roll back exceptions. Fault tests verify rollback after reservation, task insertion,
  and a SQL update. Direct SQL writers must honor the service's version/transition rules.
- **Permanent response history:** retry behavior remains defined after update/deletion,
  at the cost of unbounded storage and retention of original task data.
- **Visible write conflicts:** clients decide how to reconcile concurrent edits.
- **Offset pagination:** simple consumption, with large-offset costs and shifting
  pages under concurrent changes; keyset pagination is a natural extension.
- **Focused infrastructure:** actual PostgreSQL, explicit race synchronization, and
  an independent oracle keep test evidence meaningful.

## Limitations and future improvements

This is a production-style portfolio sample, not a complete public deployment.

- Add authentication, authorization, tenant isolation, TLS termination, rate/body
  limits, and managed secrets before public exposure. Keys share a global namespace;
  a multi-tenant API must scope them to identity and operation.
- Design idempotency retention, expiry, cleanup, and privacy policies together.
- Failed database transactions return 503; the server does not automatically retry.
  Keyed creation is safe to retry, while edits require version/conflict resolution.
- A single PostgreSQL instance is assumed. Replica lag, failover, partitions, and
  multi-process network load tests remain future work.
- Model tests cover bounded sequences and a finite operation vocabulary, not every
  possible execution. Synchronized races provide additional evidence, not a formal proof.
- Versions use PostgreSQL INTEGER; extremely long-lived rows would require a BIGINT migration.
- Readiness checks tables/connectivity, not an exact migration revision. Deployment
  migration ordering and CI drift checks provide that discipline.
- JSON log formatting, request IDs, metrics, tracing, backups, and dashboards are
  operational extensions. The app currently uses standard Python logging. Database
  failure events omit raw exception messages and SQL parameters; protect server
  logs because unhandled exceptions can still produce diagnostic tracebacks.

See the [documentation refresh verification](docs/documentation-verification.md) for current
checks and [earlier verification evidence](docs/VERIFICATION.md) for implementation history.

## Project structure

```text
.
├── src/testing_lab/
│   ├── api/routes.py
│   ├── db/{models,session}.py
│   ├── config.py
│   ├── domain.py
│   ├── errors.py
│   ├── main.py
│   ├── repositories.py
│   ├── schemas.py
│   └── services.py
├── migrations/versions/0001_initial.py
├── tests/
│   ├── unit/
│   ├── api/
│   ├── integration/
│   ├── property/
│   ├── regression/sequences/
│   └── support/
├── demos/lost_update_plugin.py
├── scripts/{replay,demonstrate_bug}.py
├── docker/postgres-init/01-test-database.sql
├── docs/
├── .github/workflows/ci.yml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
└── uv.lock
```

Licensed under [MIT](LICENSE).
