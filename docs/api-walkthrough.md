# Executed API request/response walkthrough

Captured on **November 6, 2026** from the unchanged FastAPI application running
under Uvicorn with a separate, migrated PostgreSQL 17 database. Every value is
synthetic. The requests used loopback port 8016 to avoid existing services; `Host`
below is normalized to the documented Compose endpoint `localhost:8000`. UUIDs,
timestamps, response bodies, status codes, and application headers are the actual
observed values. Transport headers such as Date, Server, and Content-Length are
omitted for readability. This is a local execution record, not a hosted demo.

Start the API using the [README setup](../README.md#run-with-docker). For an
interactive reproduction, use Swagger at `http://localhost:8000/docs` or the
[curl examples](../README.md#api-examples). Generate a new idempotency key for each
fresh walkthrough, and substitute your returned UUID and version.

## 1. Create a task

Creation starts at `pending`, version 1. The response is committed before HTTP success.

```http
POST /tasks HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Idempotency-Key: docs-demo-20261106-001

{
  "title": "Review transaction boundaries",
  "description": "Synthetic documentation example",
  "priority": 1
}
```

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

## 2. Retry the same creation

The same normalized payload and key return the original response, not a second task.

```http
POST /tasks HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Idempotency-Key: docs-demo-20261106-001

{
  "title": "Review transaction boundaries",
  "description": "Synthetic documentation example",
  "priority": 1
}
```

```http
HTTP/1.1 201 Created
content-type: application/json
location: /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3
idempotency-replayed: true

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

## 3. Update with the current version

The atomic write increments the version to 2.

```http
PATCH /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3 HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "expected_version": 1,
  "status": "in_progress"
}
```

```http
HTTP/1.1 200 OK
content-type: application/json

{
  "id": "60adffc9-b2db-4bf7-8e85-e5656540f9d3",
  "title": "Review transaction boundaries",
  "description": "Synthetic documentation example",
  "status": "in_progress",
  "priority": 1,
  "created_at": "2026-11-06T13:35:55.789890Z",
  "updated_at": "2026-11-06T13:35:55.825561Z",
  "version": 2
}
```

## 4. Reject a stale write

A client holding version 1 cannot overwrite version 2. Fetch the current task before deciding how to retry.

```http
PATCH /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3 HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "expected_version": 1,
  "title": "Stale edit"
}
```

```http
HTTP/1.1 409 Conflict
content-type: application/json

{
  "error": {
    "code": "version_conflict",
    "message": "Task changed; fetch it and retry with its version.",
    "details": []
  }
}
```

## 5. List filtered tasks

Pagination returns a collection envelope and `has_more`, without a separate count query.

```http
GET /tasks?status=in_progress&priority=1&limit=10&offset=0 HTTP/1.1
Host: localhost:8000
```

```http
HTTP/1.1 200 OK
content-type: application/json

{
  "items": [
    {
      "id": "60adffc9-b2db-4bf7-8e85-e5656540f9d3",
      "title": "Review transaction boundaries",
      "description": "Synthetic documentation example",
      "status": "in_progress",
      "priority": 1,
      "created_at": "2026-11-06T13:35:55.789890Z",
      "updated_at": "2026-11-06T13:35:55.825561Z",
      "version": 2
    }
  ],
  "limit": 10,
  "offset": 0,
  "has_more": false
}
```

## 6. Delete with the current version

Successful deletion returns no response body.

```http
DELETE /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3?expected_version=2 HTTP/1.1
Host: localhost:8000
```

```http
HTTP/1.1 204 No Content
```

## 7. Replay after deletion

The key retains the original creation response even after deletion. Its version remains 1; this is response history, not current task state.

```http
POST /tasks HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Idempotency-Key: docs-demo-20261106-001

{
  "title": "Review transaction boundaries",
  "description": "Synthetic documentation example",
  "priority": 1
}
```

```http
HTTP/1.1 201 Created
content-type: application/json
location: /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3
idempotency-replayed: true

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

## 8. Confirm the resource is gone

The replayed Location can refer to a resource that no longer exists.

```http
GET /tasks/60adffc9-b2db-4bf7-8e85-e5656540f9d3 HTTP/1.1
Host: localhost:8000
```

```http
HTTP/1.1 404 Not Found
content-type: application/json

{
  "error": {
    "code": "task_not_found",
    "message": "Task does not exist.",
    "details": []
  }
}
```
