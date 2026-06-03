"""Environment-backed service settings shared by the microservices."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = Field(default="service", alias="SERVICE_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    keycloak_url: str = Field(default="http://localhost:18080", alias="KEYCLOAK_URL")
    keycloak_realm: str = Field(default="saas-platform", alias="KEYCLOAK_REALM")
    jwt_audience: str = Field(default="saas-api", alias="JWT_AUDIENCE")
    jwt_issuer: str | None = Field(default=None, alias="JWT_ISSUER")
    oidc_issuer: str | None = Field(default=None, alias="OIDC_ISSUER")

    vault_addr: str = Field(default="http://vault:8200", alias="VAULT_ADDR")
    vault_role_id: str | None = Field(default=None, alias="VAULT_ROLE_ID")
    vault_secret_id: str | None = Field(default=None, alias="VAULT_SECRET_ID")
    vault_pki_role: str = Field(default="internal-services", alias="VAULT_PKI_ROLE")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    request_id_header: str = Field(default="X-Request-ID", alias="REQUEST_ID_HEADER")
    tenant_id_header: str = Field(default="X-Tenant-ID", alias="TENANT_ID_HEADER")
    user_id_header: str = Field(default="X-User-ID", alias="USER_ID_HEADER")
    jwks_cache_ttl_seconds: int = Field(default=300, alias="JWKS_CACHE_TTL_SECONDS")
    internal_mldsa_mtls_required: bool = Field(default=False, alias="INTERNAL_MLDSA_MTLS_REQUIRED")
    internal_mldsa_token_header: str = Field(default="X-Internal-MLDSA-Token", alias="INTERNAL_MLDSA_TOKEN_HEADER")
    internal_mldsa_public_key_file: str = Field(
        default="/certs/mldsa-upstream-client.pub",
        alias="INTERNAL_MLDSA_PUBLIC_KEY_FILE",
    )
    internal_mldsa_expected_audience: str = Field(
        default="internal-upstream",
        alias="INTERNAL_MLDSA_EXPECTED_AUDIENCE",
    )
    internal_mldsa_allowed_issuer: str = Field(default="kong-gateway", alias="INTERNAL_MLDSA_ALLOWED_ISSUER")

    @model_validator(mode="after")
    def derive_issuer(self) -> "Settings":
        if not self.jwt_issuer:
            self.jwt_issuer = self.oidc_issuer or f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"
        return self

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
