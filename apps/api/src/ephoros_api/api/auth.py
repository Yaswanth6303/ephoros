"""FastAPI as a resource server: verify Better Auth JWTs against its JWKS (spec §9.3)."""

from collections.abc import Callable
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

from ephoros_api.config import Settings

Role = Literal["analyst", "admin"]


class Principal(BaseModel):
    sub: str
    email: str
    name: str
    role: Role


_bearer = HTTPBearer(auto_error=False)


def get_jwk_client(request: Request) -> jwt.PyJWKClient:
    client: jwt.PyJWKClient = request.app.state.jwk_client
    return client


JWKClientDep = Annotated[jwt.PyJWKClient, Depends(get_jwk_client)]


def _unauthorized() -> HTTPException:
    return HTTPException(401, "Invalid or missing token", headers={"WWW-Authenticate": "Bearer"})


# sync on purpose: PyJWKClient fetches the JWKS with blocking I/O, so FastAPI runs this in a thread
def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    jwk_client: JWKClientDep,
) -> Principal:
    if credentials is None:
        raise _unauthorized()
    settings: Settings = request.app.state.settings
    try:
        key = jwk_client.get_signing_key_from_jwt(credentials.credentials).key
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["EdDSA"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        return Principal.model_validate(claims)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise _unauthorized() from exc


CurrentUserDep = Annotated[Principal, Depends(current_user)]


def require_role(role: Role) -> Callable[..., Principal]:
    def check(user: CurrentUserDep) -> Principal:
        if user.role != role:
            raise HTTPException(403, f"Requires role {role}")
        return user

    return check
