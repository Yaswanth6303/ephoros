from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: Literal["dev", "e2e", "prod"] = "dev"
    database_url: str
    redis_url: str
    readiness_timeout_s: float = 2.0
    jwks_url: str
    jwt_issuer: str
    jwt_audience: str = "ephoros-api"
