# GitHub publication readiness audit

> Historical implementation record. For the November 6, 2026 documentation refresh, current checks, and hosted CI evidence, see [documentation verification](documentation-verification.md).

Audit date: **November 5, 2026**. Scope: all publication-candidate source files,
README and supporting documentation, lockfile, tests, migrations, Docker files,
workflow configuration, ignore rules, and Python distribution contents.

The source is suitable for a public portfolio repository with the limitations
below. Source publication does not make the unauthenticated API suitable for public
hosting. Nothing was pushed, no remote was configured, and no commit was created.

## Fixes made

- Bound the Compose API port to loopback, matching the local development scope.
- Disabled SQLAlchemy parameter display and removed raw database exception text
  and tracebacks from the application's handled-database-error logs. Regression
  assertions check that sensitive exception text does not enter these logs.
- Preserved HTTP exception headers, including the required `Allow` header for 405s.
- Enforced the disposable-database guard immediately before test/replay truncation,
  in addition to fixture configuration. New tests verify rejection before connection.
- Added explicit source-distribution inclusion rules and included the MIT license
  in the Docker build/runtime. Built and inspected both Python artifacts.
- Expanded Git/Docker ignores for local credentials, private keys, dumps, logs,
  and tool directories; added line-ending normalization.
- Made the development test-database initialization SQL safe to rerun, and tested
  it with PostgreSQL. Reserved `testing_lab_test` is documented as disposable.
- Corrected Compose credential customization guidance: its sample URL interpolation
  requires URL-safe values. Independent database URLs can use percent encoding.
- Pinned CI Actions to full commit hashes resolved from the official release tags,
  disabled checkout credential persistence, and configured dependency update PRs.
- Added a security policy, updated verification counts, and kept Docker/hosted CI
  execution explicitly unverified. The bug demonstration disables terminal colors
  so its expected assertion check is deterministic.

## Executed verification

Environment: Windows, CPython 3.12.16, PostgreSQL 17.11, database on loopback port
55432. Test and application databases are separate.

| Check | Result |
| --- | --- |
| Full PostgreSQL suite | **74 passed** |
| Coverage, including branches | **311/311 statements, 34/34 branches; 100.00%** |
| Coverage exclusions/gate | No excluded production lines; gate unchanged at 90% |
| Database-free suite | **34 passed**, 40 deselected |
| Ruff lint / format | Passed |
| actionlint 1.7.12 | Workflow static validation passed; optional shellcheck/pyflakes not available |
| Markdown links / TOML / YAML | Local links resolve; configuration syntax passed |
| Lockfile consistency / installed dependency compatibility | Passed |
| Alembic upgrade / drift / downgrade-upgrade | Passed |
| Regression replay | Both saved traces passed: 4 and 5 operations |
| Bug demonstration | Race test rejected two successful writes; wrapper exited successfully |
| Fresh Uvicorn TCP smoke | Passed; temporary server shut down after testing |
| Source archive / wheel | Built; no local tools, credentials, caches, or generated test output included |
| OSV lockfile lookup | 42 registry package/version pairs checked; no advisory findings |
| Gitleaks 8.30.1 | 60 publication-candidate files scanned; zero findings |
| Git ignore checks | Generated data and local secrets paths excluded; `.env.example` remains publishable |

The current Git publication candidate contains 60 files (under 0.5 MB); ignored
local runtimes, database files, generated coverage, and build outputs are excluded.
Actionlint and Gitleaks official release checksums were verified before execution.
The secret scan used Gitleaks' default rules on a copy of exactly the Git-eligible
candidate files, with redacted output and no custom allowlist. The disposable
`lab` credentials remain intentionally documented examples. A zero-finding scan
does not establish that every possible secret format is detectable. Actionlint's success
does not establish that the remote Actions jobs or container commands execute.

Coverage totals were read from the newly generated JSON report, not copied from
an earlier assertion. The ordinary test run succeeded; the separate mutation test
is intentionally expected to fail its race assertion.

The dependency check queried the official [OSV batch API](https://google.github.io/osv.dev/post-v1-querybatch/)
for every registry entry in `uv.lock`, including platform-specific dependencies
not installed on Windows. The local project is excluded from that advisory lookup.
The response contained 42 results with no vulnerabilities or pagination tokens.
This does not audit the Python runtime, build backend, OS packages, container image,
or previously undisclosed vulnerabilities.

## Unverified and remaining limitations

- **Docker is unavailable here.** Dockerfile and Compose review is static; no image
  build, Compose runtime, container smoke test, or container vulnerability scan is claimed.
- **GitHub Actions and Dependabot have not run.** Pins and configuration were inspected
  locally; hosted execution must be confirmed after publication. No hosted CI badge
  or successful remote run is claimed.
- No authentication, authorization, tenant isolation, or idempotency retention policy.
  These are documented deployment extensions, not publication blockers for source code.
- Compose uses disposable credentials and a development PostgreSQL superuser. Do not
  reuse that setup as a public production deployment.
- Python/PostgreSQL base images use maintained tags rather than immutable digests.
  Build-backend dependencies are outside the application lockfile.
- No prior Git history existed. The publication review covers the candidate tree,
  not unknown files elsewhere on the machine or a future remote history.

See [SECURITY.md](../SECURITY.md) for deployment boundaries and reporting guidance.

## Docker verification on a capable host

```bash
docker compose config --quiet
docker compose up --build -d --wait api
curl --fail http://localhost:8000/health/ready
docker compose --profile test run --build --rm test
docker compose down
```

## Publication commands

A local Git repository is initialized on `main`, with no remote or commits.
Create an **empty public** GitHub repository named `python-backend-testing-lab`
without a generated README, license, or `.gitignore`. Replace `YOUR_USERNAME` below.
Run these commands yourself when ready to publish:

```powershell
Set-Location C:\python-backend-testing-lab
git add .
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "Initial release: Python Backend Testing Lab"
git remote add origin https://github.com/YOUR_USERNAME/python-backend-testing-lab.git
git push -u origin main
```

If Git needs your identity, set it for this repository before committing:

```powershell
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED OR GITHUB NOREPLY EMAIL"
```

Authenticate using GitHub's credential manager or SSH; never put a personal access
token in the remote URL. After the first push, inspect both workflow jobs and enable
private vulnerability reporting, secret scanning/push protection, and branch
protection as appropriate for your GitHub account. These remote settings were not
changed during the local audit.
