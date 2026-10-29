from fastapi import APIRouter

from ephoros_api.api.auth import CurrentUserDep, Principal

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me")
def me(user: CurrentUserDep) -> Principal:
    return user
