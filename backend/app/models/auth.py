from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


GUEST_USER_ID = "guest"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = SQLField(primary_key=True)
    username: str = SQLField(index=True, unique=True)
    password_hash: str
    created_at: datetime = SQLField(default_factory=utc_now)


class CurrentActor(BaseModel):
    user_id: str
    username: Optional[str] = None
    is_guest: bool = False


class AuthCredentialsRequest(BaseModel):
    username: str = Field(min_length=4, max_length=16)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not 4 <= len(normalized) <= 16:
            raise ValueError("用户名长度必须为 4 到 16 个字符")
        return normalized

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("密码不能为空")
        return value


class RegisterData(BaseModel):
    user_id: str


class LoginData(BaseModel):
    token: str
    user_id: str
    username: str


class CurrentUserData(BaseModel):
    user_id: str
    username: str


class RegisterResponse(BaseModel):
    code: int
    msg: str
    data: Optional[RegisterData] = None


class LoginResponse(BaseModel):
    code: int
    msg: str
    data: Optional[LoginData] = None


class CurrentUserResponse(BaseModel):
    code: int
    msg: str
    data: Optional[CurrentUserData] = None
