"""Smoke-test an already running server over a real TCP connection."""

import argparse
from uuid import uuid4

import httpx


def run(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=10) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        headers = {"Idempotency-Key": f"smoke:{uuid4()}"}
        first = client.post("/tasks", json={"title": "TCP smoke test"}, headers=headers)
        assert first.status_code == 201
        path = first.headers["location"]
        try:
            replay = client.post("/tasks", json={"title": "TCP smoke test"}, headers=headers)
            assert replay.json() == first.json()
            assert replay.headers["idempotency-replayed"] == "true"
            updated = client.patch(path, json={"expected_version": 1, "status": "in_progress"})
            assert updated.status_code == 200
            assert updated.json()["version"] == 2
            assert (
                client.patch(path, json={"expected_version": 1, "title": "stale"}).status_code
                == 409
            )
            assert client.get(path).json() == updated.json()
        finally:
            current = client.get(path)
            if current.status_code == 200:
                deleted = client.delete(
                    path, params={"expected_version": current.json()["version"]}
                )
                assert deleted.status_code == 204
        assert client.get(path).status_code == 404
    print("TCP smoke passed: health, create, replay, update, conflict, read, delete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    run(parser.parse_args().base_url)
