class AppError(Exception):
    def __init__(self, status: int = 400, code: str = "bad_request", message: str = ""):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def not_found(what="Resource"):
    return AppError(404, "not_found", f"{what} not found")


class RunCancelled(Exception): ...
class ApprovalRequired(Exception): ...
class PolicyViolation(Exception): ...
class ToolError(Exception): ...
