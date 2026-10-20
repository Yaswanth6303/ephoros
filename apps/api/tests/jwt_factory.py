"""Test helpers: sign Better-Auth-shaped EdDSA tokens and stand in for PyJWKClient."""

import time
from types import SimpleNamespace
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ISSUER = "https://issuer.test"
AUDIENCE = "ephoros-api"


def make_token(key: Ed25519PrivateKey, **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "sub": "user-1",
        "email": "ana@ephoros.test",
        "name": "Ana",
        "role": "analyst",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 900,
    } | overrides
    return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": "k1"})


class FakeJWKClient:
    def __init__(
        self,
        key: Ed25519PrivateKey | None = None,  # gitleaks:allow (test key, generated per run)
        error: Exception | None = None,
    ):
        self.key, self.error = key, error

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        if self.error:
            raise self.error
        assert self.key is not None
        return SimpleNamespace(key=self.key.public_key())
