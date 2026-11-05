"""Run an opt-in mutant in a subprocess and verify that the race test rejects it."""

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "--color=no",
            "-p",
            "demos.lost_update_plugin",
            "tests/integration/test_concurrency.py::test_atomic_update_allows_exactly_one_winner",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode == 1 and "[200, 200] == [200, 409]" in result.stdout:
        print("BUG DETECTED: both writers succeeded after the version predicate was removed.")
        return 0
    print("Unexpected result: expected the lost-update assertion to fail.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
