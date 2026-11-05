# Verification evidence

Executed during implementation on **November 5, 2026**, on Windows, using a
project-local CPython **3.12.16** and real PostgreSQL **17.11**. These are local
results, not claims about a hosted GitHub Actions run or Docker execution.

The isolated PostgreSQL instance listens on `127.0.0.1:55432`, with separate
`testing_lab` and `testing_lab_test` databases. Its binaries, data directory, logs,
Python runtime, and virtual environment are ignored local tooling, not project source.
This temporary loopback cluster uses trust authentication for local verification;
Docker uses the local development password configuration in `.env.example`.

| Check | Observed result |
| --- | --- |
| Locked dependency installation | Successful |
| Ruff lint and format check | Passed |
| Full suite against PostgreSQL | 74 passed after publication-audit fixes |
| Production line and branch coverage | 100.00%; configured gate remains 90% |
| Database-free suite | 34 passed, 40 deselected |
| Alembic upgrade | Passed for application and test databases |
| Alembic drift check | No new upgrade operations detected |
| Alembic downgrade to base, then upgrade | Passed on disposable test database |
| Missing-version-predicate demonstration | Expected race assertion failed; wrapper confirmed detection |
| Saved stale-write replay | 4 operations passed |
| Saved retry-after-deletion replay | 5 operations passed |
| Real TCP/Uvicorn smoke | Health, create, replay, update, conflict, read, delete passed |
| TOML and YAML parsing | Passed; syntax validation only |
| Workflow static validation | actionlint 1.7.12 passed; no hosted execution claimed |
| Python source archive and wheel | Built successfully; contents inspected |
| Installed dependency compatibility | `uv pip check` passed |
| OSV advisory lookup | No known advisories returned for 42 locked registry packages |
| Secret scan | Gitleaks 8.30.1 scanned 60 publication-candidate files; zero findings |
| Docker build/Compose execution | Not run: Docker executable unavailable |
| Hosted GitHub Actions | Not run: no remote repository/workflow execution in this session |

Coverage is measured with `greenlet` enabled for SQLAlchemy's async bridge. The
initial run without that setting undercounted executed paths; the reported final
result uses the corrected configuration. Coverage is evidence of exercised code,
not a proof of correctness or security.
The audit rerun covered **311/311 statements and 34/34 branches**, with no excluded
production lines. See [the publication audit](PUBLICATION_AUDIT.md) for fixes and
the scope of the security checks. OSV does not cover the interpreter, build backend,
container operating system, or vulnerabilities absent from its advisory data.

## Reproduce the primary checks

Use the README setup instructions and a dedicated migrated test database:

```bash
uv sync --locked --python 3.12
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync pytest --cov --cov-report=term-missing --cov-report=xml
uv run --no-sync python -m scripts.demonstrate_bug
uv run --no-sync python -m scripts.replay tests/regression/sequences/stale_write.json
uv run --no-sync python -m scripts.replay tests/regression/sequences/retry_after_delete.json
```

For these commands, export `TEST_DATABASE_URL` and set `DATABASE_URL` to the same
disposable database before migrations. Replay resets its tables. To verify the
migration reversal, on that disposable database only:

```bash
uv run --no-sync alembic downgrade base
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
```

Verify Docker on a host where it is installed:

```bash
docker compose config --quiet
docker compose up --build -d --wait api
curl --fail http://localhost:8000/health/ready
docker compose --profile test run --build --rm test
docker compose down
```

For a real HTTP smoke test against an already running API:

```bash
uv run --no-sync python -m scripts.smoke_http --base-url http://127.0.0.1:8000
```

That command creates and deletes one task; its idempotency record remains by design.

## This workspace's local runtime

The locally provisioned executables are `.venv/Scripts/python.exe`,
`.venv/Scripts/alembic.exe`, `.venv/Scripts/ruff.exe`, and `.tools/uv/uv.exe`.
They are not committed and are not prerequisites on another machine.

PowerShell commands for the existing local PostgreSQL instance:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://lab@127.0.0.1:55432/testing_lab_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing

$env:DATABASE_URL = 'postgresql+asyncpg://lab@127.0.0.1:55432/testing_lab'
.venv/Scripts/python.exe -m uvicorn testing_lab.main:app --host 127.0.0.1 --port 8000
```

If PostgreSQL has stopped, restart that existing cluster with:

```powershell
.tools/pgsql/bin/pg_ctl.exe -D .tools/pgdata -l .tools/postgres.log -o '-h 127.0.0.1 -p 55432' -w start
```
