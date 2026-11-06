# Documentation refresh verification

Date: **November 6, 2026**. Scope: documentation only; application code,
dependencies, migrations, and CI configuration are unchanged. Checks used the
locked dependencies, Python 3.12.16, and a separate local PostgreSQL 17 instance.
All API examples use synthetic task data and a disposable demo database.

## Executed checks

| Check | Observed result |
| --- | --- |
| Full PostgreSQL pytest suite | **74 passed**, including synchronized races, generated sequences, state machine, and regression tests |
| Measured production coverage | **100.00%**, 311 statements and 34 branches; existing 90% gate passed |
| Ruff lint and format | Passed; 43 Python files checked for formatting |
| Alembic upgrade and schema drift check | Passed |
| Alembic downgrade to base, upgrade to head, drift recheck | Passed on the disposable test database |
| Mutation demonstration | Wrapper succeeded after detecting the expected race assertion failure: `[200, 200]` instead of `[200, 409]` |
| Saved regression replay | Both traces passed: stale write (4 operations), retry after deletion (5 operations) |
| Real HTTP walkthrough | 8 exchanges through Uvicorn: create, retry, update, stale conflict, filtered list, delete, replay after delete, missing resource |
| actionlint | Passed; optional shellcheck and pyflakes integrations disabled because unavailable |
| Secret scan and file review | Gitleaks history and publication-candidate scans completed with no findings; tracked paths reviewed for sensitive/runtime files |
| Documentation integrity | Across both repositories: 15 Markdown files, 88 link occurrences, no missing local targets/anchors, 19 external URLs returned success; whitespace checked; localhost setup URLs are examples, not hosted links |

Coverage above is the output of this run, not a benchmark or an assumed badge
value. The separately executed mutant intentionally fails its race test; the
ordinary 74-test suite passes without the plugin. No production source was modified.

## Hosted CI evidence

The existing [Backend correctness workflow](../.github/workflows/ci.yml) was
verified on GitHub: [run 42050274954](https://github.com/CalamoAndret/python-backend-testing-lab/actions/runs/42050274954)
completed successfully for the inspected `main` commit `e8a4625b783d3e87df15fab4fb4af45395ba3615`.
Both verify and container jobs succeeded. The README badge targets that workflow
on `main`, whose verification job includes PostgreSQL tests, coverage, mutation
detection, replay, and migrations.

## Remaining limitations

- No local Docker image rebuild or performance benchmark was run for this
  documentation change. Container execution is supported by the separately linked
  hosted CI evidence.
- Request UUIDs and timestamps are actual run-specific values. To reproduce the
  [walkthrough](api-walkthrough.md), use a fresh key and your returned task UUID/version.
- Generated/stateful tests explore bounded sequences. Sequential replay preserves
  semantic operations, not wall-clock timing or concurrent schedules; race tests
  establish their schedules with explicit synchronization.
- No public deployment, authentication/tenant isolation, security certification,
  or exhaustive concurrency proof is claimed. See [security boundaries](../SECURITY.md).
