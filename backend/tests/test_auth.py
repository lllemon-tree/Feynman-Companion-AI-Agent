import unittest
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.core.database import get_session
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.auth import User


class AuthApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_register_hashes_password_and_rejects_duplicate_username(self) -> None:
        payload = {"username": "student01", "password": "123456abc"}

        response = self.client.post("/api/v1/auth/register", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["user_id"].startswith("user-"))
        with Session(self.engine) as session:
            user = session.exec(
                select(User).where(User.username == "student01")
            ).one()
            self.assertNotEqual(user.password_hash, payload["password"])
            self.assertTrue(user.password_hash.startswith("$argon2"))

        duplicate = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["msg"], "该用户名已被注册")

    def test_login_and_current_user(self) -> None:
        payload = {"username": "student02", "password": "123456abc"}
        self.client.post("/api/v1/auth/register", json=payload)

        login = self.client.post("/api/v1/auth/login", json=payload)

        self.assertEqual(login.status_code, 200)
        data = login.json()["data"]
        self.assertTrue(data["token"])
        current = self.client.get(
            "/api/v1/auth/current",
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["data"]["username"], "student02")

    def test_bad_password_and_missing_token_return_401(self) -> None:
        self.client.post(
            "/api/v1/auth/register",
            json={"username": "student03", "password": "123456abc"},
        )

        bad_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "student03", "password": "wrong-password"},
        )
        self.assertEqual(bad_login.status_code, 401)

        current = self.client.get("/api/v1/auth/current")
        self.assertEqual(current.status_code, 401)

    def test_blank_credentials_and_guest_login_are_rejected(self) -> None:
        with Session(self.engine) as session:
            session.add(
                User(
                    id="guest",
                    username="guest",
                    password_hash="!",
                )
            )
            session.commit()
        blank = self.client.post(
            "/api/v1/auth/register",
            json={"username": "    ", "password": "      "},
        )
        guest = self.client.post(
            "/api/v1/auth/login",
            json={"username": "guest", "password": "123456"},
        )

        self.assertEqual(blank.status_code, 400)
        self.assertEqual(guest.status_code, 401)

    def test_expired_token_returns_401(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="user-expired",
                username="expired-user",
                password_hash="!",
            )
            session.add(user)
            session.commit()
        token = create_access_token(
            "user-expired",
            "expired-user",
            expires_delta=timedelta(seconds=-1),
        )

        response = self.client.get(
            "/api/v1/auth/current",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
