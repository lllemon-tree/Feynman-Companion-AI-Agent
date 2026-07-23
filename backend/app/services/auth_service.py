from uuid import uuid4

from sqlmodel import Session, select

from backend.app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from backend.app.models.auth import LoginData, RegisterData, User


class UsernameAlreadyExistsError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def register_user(
    session: Session,
    *,
    username: str,
    password: str,
) -> RegisterData:
    normalized_username = username.strip()
    existing = session.exec(
        select(User).where(User.username == normalized_username)
    ).first()
    if existing is not None:
        raise UsernameAlreadyExistsError("该用户名已被注册")

    user = User(
        id=f"user-{uuid4().hex}",
        username=normalized_username,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return RegisterData(user_id=user.id)


def login_user(
    session: Session,
    *,
    username: str,
    password: str,
) -> LoginData:
    normalized_username = username.strip()
    user = session.exec(
        select(User).where(User.username == normalized_username)
    ).first()
    encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, encoded_hash)
    if user is None or not password_matches:
        raise InvalidCredentialsError("用户名或密码错误")

    return LoginData(
        token=create_access_token(user.id, user.username),
        user_id=user.id,
        username=user.username,
    )
