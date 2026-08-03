from __future__ import annotations

from hmac import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


def bearer_auth(expected_token: str):
    scheme = HTTPBearer(auto_error=False)

    def verify(
        credentials: HTTPAuthorizationCredentials | None = Depends(scheme),
    ) -> None:
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not compare_digest(credentials.credentials, expected_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": "A valid helper token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )

    return verify
