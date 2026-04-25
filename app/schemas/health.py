"""Health-check schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health-check response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
