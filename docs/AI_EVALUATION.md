# Evaluating AI-generated backend changes

Treat a generated patch as a candidate implementation with a public contract.
Review its diff and execute it in an isolated checkout/database before accepting it.

| Plausible mistake | Evidence that rejects it |
| --- | --- |
| Python version check without an UPDATE predicate | Synchronized two-writer test observes two successes |
| In-memory idempotency | A new application instance must replay the persisted response |
| Check-then-insert key without uniqueness | Concurrent key tests expose duplicates or failed requests |
| Commit task before storing response | Injected failure must roll back both rows |
| Shared production/oracle transition helper | Review catches coupled logic; this model has an independent table |
| Allow terminal tasks to reopen | Stateful lifecycle rules and explicit transition tests |
| Accept nulls and unknown input fields | API/schema contract tests |
| Timing-based race tests | Review requires barriers/events and an observed database lock dependency |

Run the baseline:

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest --cov --cov-report=term-missing
uv run --no-sync python -m scripts.demonstrate_bug
```

The last command demonstrates that the suite distinguishes a broken atomic write
from the baseline. Only repository SQL changes in the mutant; the service pre-check
remains. Happy-path CRUD tests would miss the defect.

For a real patch, inspect SQL and transaction scope as well as test results. Passing
tests do not establish security, scalability, or correctness for untested schedules.
Reject changes that disable the oracle, weaken expected outcomes, remove constraints,
skip PostgreSQL, or lower the coverage gate to pass.

When Hypothesis finds a failure, preserve/replay its JSON trace, fix the implementation,
and check the useful trace into `tests/regression/sequences/` with PR context.
Do not record confidential production payloads in fixtures.

Interview discussion prompts:

1. Why use a separate SELECT after `ON CONFLICT DO NOTHING` at READ COMMITTED?
2. Where is the decisive concurrency check, and when does commit happen?
3. What happens when the reservation owner rolls back or the client disconnects?
4. Why does replay return the original creation response after deletion?
5. Which failures need a synchronized schedule rather than sequential replay?
6. How would tenant scoping and retention change the key schema?
