"""Application error types and response schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    """Base application error that can be mapped to an HTTP response."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def build_error_response(error: AppError) -> ErrorResponse:
    """Convert an application error into the public error response schema."""
    return ErrorResponse(code=error.code, message=error.message, details=error.details)
