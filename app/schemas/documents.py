"""Document schemas."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DocumentCreate(BaseModel):
    """Document creation payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Utility Bill",
                    "content": (
                        "The client uploaded a recent utility bill as proof of residence "
                        "and address verification."
                    ),
                }
            ]
        }
    )

    title: NonEmptyText
    content: NonEmptyText


class DocumentRead(BaseModel):
    """Document response payload."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "85a2202e-a0ae-4087-b73d-250dc04b812f",
                    "client_id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
                    "title": "Utility Bill",
                    "content": (
                        "The client uploaded a recent utility bill as proof of residence "
                        "and address verification."
                    ),
                    "summary": (
                        "The client uploaded a recent utility bill as proof of residence "
                        "and address verification."
                    ),
                    "created_at": "2026-04-25T10:01:00Z",
                }
            ]
        },
    )

    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    content: str
    summary: str | None
    created_at: datetime
