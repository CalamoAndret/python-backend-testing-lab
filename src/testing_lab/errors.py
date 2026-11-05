class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found() -> DomainError:
    return DomainError(404, "task_not_found", "Task does not exist.")


def stale_version() -> DomainError:
    return DomainError(
        409, "version_conflict", "Task changed; fetch it and retry with its version."
    )
