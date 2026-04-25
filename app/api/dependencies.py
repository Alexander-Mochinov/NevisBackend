"""FastAPI dependency helpers."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session


def get_app_settings(request: Request) -> Settings:
    """Return settings attached to the FastAPI app, falling back to cached settings."""
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


SettingsDependency = Annotated[Settings, Depends(get_app_settings)]
DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_session)]

__all__ = ["DatabaseSessionDependency", "SettingsDependency", "get_app_settings"]
