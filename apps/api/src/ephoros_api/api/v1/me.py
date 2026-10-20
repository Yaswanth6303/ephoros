from typing import Annotated

from fastapi import APIRouter, Depends

from ephoros_api.api.auth import Principal, current_user

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me")
def me(user: Annotated[Principal, Depends(current_user)]) -> Principal:
    return user
