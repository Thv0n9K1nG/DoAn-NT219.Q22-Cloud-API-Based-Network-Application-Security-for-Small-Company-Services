"""Logging bootstrap for Resource Service."""

from app.core.config import settings
from shared.logging_config import configure_logging


def configure_service_logging() -> None:
    configure_logging(service_name=settings.service_name, log_level=settings.log_level)

