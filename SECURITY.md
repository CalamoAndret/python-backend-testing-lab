# Security policy

This repository is a local engineering laboratory. The API has no authentication
or authorization and must not be exposed as a public service without additional
controls. Publishing its source code is separate from deploying the API.

## Reporting

Use GitHub private vulnerability reporting if the repository owner has enabled it.
Otherwise, contact the owner through the contact information on their GitHub profile.
Do not post credentials, confidential payloads, or exploitable vulnerability details
in public issues. This portfolio repository does not promise a response SLA.

## Local defaults and data

- The checked-in `lab` database username/password are disposable examples, not
  production credentials. Both Compose ports bind to loopback. Do not reuse these
  credentials elsewhere or expose the services directly to the internet.
- Local `.env` files, tool caches, database dumps, private keys, and credentials
  directories are ignored. Review `git diff --cached` before each publication;
  ignore patterns cannot identify every possible secret.
- Test and replay commands truncate a database explicitly named by
  `TEST_DATABASE_URL`. The name must end in `_test`; always select disposable data.
- Idempotency history retains original task text even after task deletion. Define
  access control, tenant scoping, privacy requirements, and retention before deployment.
- Database error handling emits a sanitized event and error class without raw SQL
  or exception text. SQLAlchemy parameter display is disabled. Unhandled application
  exceptions can still reach server tracebacks; protect logs and review their contents.

## Dependencies and deployment

Install with `uv sync --locked`. Dependabot is configured for uv, Actions, and Docker;
its execution requires a published GitHub repository. CI Actions use full commit pins.
Review updates and rerun tests rather than merging dependency changes blindly.
OSV audit results are a point-in-time advisory lookup, not proof of vulnerability absence.

Before production deployment, use separate least-privilege application/migration
database roles, managed secrets, authentication, TLS, request size/rate limits,
appropriate network rules, a backup strategy, and an operational log policy.
The Compose PostgreSQL role is a development superuser. Python/PostgreSQL container
base images use maintained tags rather than immutable digests; rebuild and assess
the actual deployed images with your container vulnerability scanner.
