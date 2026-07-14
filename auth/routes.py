from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, get_db
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        return TokenResponse(**service.register(payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        return TokenResponse(**service.login(payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout")
async def logout(current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    service = AuthService(db)
    service.logout(int(current_user["id"]))
    return {"success": True, "message": "Logged out"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        return TokenResponse(**service.refresh(refresh_token))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict[str, object] = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=str(current_user["uuid"]), name=str(current_user["name"]), email=str(current_user["email"]), role=str(current_user["role"]))
