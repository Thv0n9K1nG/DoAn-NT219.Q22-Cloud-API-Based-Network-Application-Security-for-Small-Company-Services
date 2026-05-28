"""Admin Service settings with service-specific defaults."""

from shared.config import Settings


settings = Settings(
    SERVICE_NAME="admin-service",
    DATABASE_URL="postgresql+asyncpg://postgres:changeme-postgres@postgres:5432/admindb",
)

