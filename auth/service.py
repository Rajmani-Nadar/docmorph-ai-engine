from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from sqlalchemy.orm import Session

from auth.models import User, UserRole
from auth.schemas import LoginRequest, RegisterRequest, TokenPayload
from database.models import Job
from database.session import SessionLocal
from repositories.job_repository import JobRepository

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))


class AuthService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()

    def register(self, payload: RegisterRequest) -> dict[str, Any]:
        if self.session.query(User).filter(User.email == payload.email.lower()).first():
            raise ValueError("Email already registered")
        password_hash = self._hash_password(payload.password)
        user = User(name=payload.name.strip(), email=payload.email.lower(), password_hash=password_hash, role=UserRole.USER.value)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self._issue_tokens(user)

    def login(self, payload: LoginRequest) -> dict[str, Any]:
        user = self.session.query(User).filter(User.email == payload.email.lower()).first()
        if not user or not user.is_active or not self._verify_password(payload.password, user.password_hash):
            raise ValueError("Invalid credentials")
        user.last_login = datetime.utcnow()
        self.session.commit()
        return self._issue_tokens(user)

    def me(self, user_id: int) -> dict[str, Any]:
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise ValueError("User not found")
        return self._user_payload(user)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        payload = self._decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user = self.session.query(User).filter(User.id == int(payload["sub"])).first()
        if not user or not user.is_active or payload.get("token_version") != user.token_version:
            raise ValueError("Invalid refresh token")
        return self._issue_tokens(user)

    def create_access_token(self, user: User) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)
        return jwt.encode(
            {
                "sub": str(user.id),
                "role": user.role,
                "token_version": user.token_version,
                "exp": int(expires_at.timestamp()),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

    def create_refresh_token(self, user: User) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        return jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "token_version": user.token_version,
                "exp": int(expires_at.timestamp()),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

    def get_user_from_token(self, token: str) -> User | None:
        payload = self._decode_token(token)
        if payload.get("type") == "refresh":
            return None
        user = self.session.query(User).filter(User.id == int(payload["sub"])).first()
        if not user or not user.is_active or payload.get("token_version") != user.token_version:
            return None
        return user

    def logout(self, user_id: int) -> None:
        user = self.session.query(User).filter(User.id == user_id).first()
        if user:
            user.token_version += 1
            self.session.commit()

    def get_jobs_for_user(self, user_id: int) -> list[dict[str, Any]]:
        repository = JobRepository(self.session)
        rows = self.session.query(Job).filter(Job.user_id == user_id).all() if hasattr(Job, "user_id") else []
        return [{"job_id": row.job_id, "filename": row.filename, "status": getattr(row, "processing_status", "unknown"), "uploaded_at": str(getattr(row, "upload_time", ""))} for row in rows]

    def _issue_tokens(self, user: User) -> dict[str, Any]:
        return {
            "access_token": self.create_access_token(user),
            "refresh_token": self.create_refresh_token(user),
            "token_type": "bearer",
            "user": self._user_payload(user),
        }

    def _user_payload(self, user: User) -> dict[str, Any]:
        return {"id": str(user.uuid), "name": user.name, "email": user.email, "role": user.role}

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    def _decode_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
