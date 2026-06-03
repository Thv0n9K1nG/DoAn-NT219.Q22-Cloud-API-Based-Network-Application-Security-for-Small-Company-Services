"""ML-DSA client assertion guard for upstream mTLS traffic."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from shared.config import Settings, get_settings
from shared.pqc_signing import MLDSASigner, PQCKeyError
from shared.s2s_token import S2STokenError, verify_s2s_token


class InternalMLDSAMTLSMiddleware(BaseHTTPMiddleware):
    """Require Kong's ML-DSA assertion on non-health upstream requests."""

    def __init__(self, app, settings: Settings | None = None):
        super().__init__(app)
        self.settings = settings or get_settings()
        self.logger = logging.getLogger(self.settings.service_name)
        self._signer: MLDSASigner | None = None

    async def dispatch(self, request: Request, call_next):
        if not self.settings.internal_mldsa_mtls_required or _is_health_path(request.url.path):
            return await call_next(request)

        token = request.headers.get(self.settings.internal_mldsa_token_header)
        if not token:
            self.logger.warning(
                "internal_mldsa_mtls.missing",
                extra={"event": "internal_mldsa_mtls.missing", "path": request.url.path},
            )
            return JSONResponse(status_code=401, content={"detail": "Missing ML-DSA upstream client assertion"})

        try:
            claims = verify_s2s_token(
                token,
                signer=self._get_signer(),
                expected_audience=self.settings.internal_mldsa_expected_audience,
                allowed_issuers=[self.settings.internal_mldsa_allowed_issuer],
            )
        except (PQCKeyError, S2STokenError) as exc:
            self.logger.warning(
                "internal_mldsa_mtls.invalid",
                extra={"event": "internal_mldsa_mtls.invalid", "path": request.url.path, "reason": str(exc)},
            )
            return JSONResponse(status_code=401, content={"detail": "Invalid ML-DSA upstream client assertion"})

        request.state.internal_mldsa_claims = claims
        return await call_next(request)

    def _get_signer(self) -> MLDSASigner:
        if self._signer is None:
            public_key_b64 = Path(self.settings.internal_mldsa_public_key_file).read_text(encoding="ascii").strip()
            public_key = base64.b64decode(public_key_b64, validate=True)
            self._signer = MLDSASigner(public_key=public_key)
        return self._signer


def _is_health_path(path: str) -> bool:
    return path.startswith("/health/")
