"""Client schemas."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ClientCreate(BaseModel):
    """Client creation payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "first_name": "Sample",
                    "last_name": "Client",
                    "email": "sample.client@neviswealth.test",
                    "description": "Wealth management client",
                    "social_links": ["https://example.test/profiles/sample-client"],
                }
            ]
        }
    )

    first_name: NonEmptyText
    last_name: NonEmptyText
    email: NonEmptyText
    description: str | None = None
    social_links: list[str] | None = None

    @field_validator("email", mode="after")
    @classmethod
    def validate_and_normalize_email(cls, email: str) -> str:
        normalized_email = email.strip().lower()
        local_part, separator, domain = normalized_email.partition("@")

        if (
            separator != "@"
            or not local_part
            or not domain
            or "." not in domain
            or any(character.isspace() for character in normalized_email)
        ):
            raise ValueError("Invalid email address.")

        return normalized_email


class ClientRead(BaseModel):
    """Client response payload."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "6b8ed0b3-6635-4901-9cb2-ec65893f51f1",
                    "first_name": "Sample",
                    "last_name": "Client",
                    "email": "sample.client@neviswealth.test",
                    "description": "Wealth management client",
                    "social_links": ["https://example.test/profiles/sample-client"],
                    "created_at": "2026-04-25T10:00:00Z",
                    "updated_at": "2026-04-25T10:00:00Z",
                }
            ]
        },
    )

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    description: str | None
    social_links: list[str] | None
    created_at: datetime
    updated_at: datetime
