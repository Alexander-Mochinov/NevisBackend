"""Logging configuration."""

import logging


def configure_logging(app_env: str) -> None:
    """Configure baseline application logging."""
    level = logging.DEBUG if app_env == "local" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
