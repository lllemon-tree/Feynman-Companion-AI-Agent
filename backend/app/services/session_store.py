import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Protocol

from sqlalchemy import func
from sqlmodel import Session, select

from backend.app.models.auth import GUEST_USER_ID
from backend.app.models.feynman import ChatMessage, FeynmanChatData
from backend.app.models.knowledge import LearnSession, Material


@dataclass
class SessionState:
    session_id: str
    user_id: str = GUEST_USER_ID
    kp_id: Optional[str] = None
    kp_name: Optional[str] = None
    material_id: Optional[str] = None
    chapter_id: Optional[str] = None
    follow_up_count: int = 0
    invalid_answer_count: int = 0
    off_topic_count: int = 0
    ended: bool = False
    last_provider: str = "none"
    fallback_used: bool = False
    messages: list[ChatMessage] = field(default_factory=list)
    final_response: Optional[FeynmanChatData] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionAccessDeniedError(Exception):
    pass


@dataclass
class SessionSummary:
    session_id: str
    kp_name: Optional[str]
    material_title: str
    created_at: datetime


class SessionStore(Protocol):
    def get_or_create(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> SessionState: ...

    def get(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> Optional[SessionState]: ...

    def save(self, state: SessionState) -> None: ...

    def reset(self, session_id: str, user_id: str = GUEST_USER_ID) -> bool: ...

    def list_by_user(self, user_id: str = GUEST_USER_ID) -> list[SessionSummary]: ...

    def count(self) -> int: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                user_id=user_id,
            )
        self._check_owner(self._sessions[session_id], user_id)
        return self._sessions[session_id]

    def get(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> Optional[SessionState]:
        state = self._sessions.get(session_id)
        if state is not None:
            self._check_owner(state, user_id)
        return state

    def save(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state

    def reset(self, session_id: str, user_id: str = GUEST_USER_ID) -> bool:
        existed = session_id in self._sessions
        if existed:
            self._check_owner(self._sessions[session_id], user_id)
        self._sessions[session_id] = SessionState(
            session_id=session_id,
            user_id=user_id,
        )
        return existed

    def count(self) -> int:
        return len(self._sessions)

    def list_by_user(
        self, user_id: str = GUEST_USER_ID
    ) -> list[SessionSummary]:
        states = sorted(
            (
                state
                for state in self._sessions.values()
                if state.user_id == user_id
            ),
            key=lambda state: state.updated_at,
            reverse=True,
        )
        return [
            SessionSummary(
                session_id=state.session_id,
                kp_name=state.kp_name,
                material_title=state.material_id or "未知教材",
                created_at=state.created_at,
            )
            for state in states
        ]

    @staticmethod
    def _check_owner(state: SessionState, user_id: str) -> None:
        if state.user_id != user_id:
            raise SessionAccessDeniedError("session not found")


class SQLSessionStore:
    def __init__(self, engine) -> None:
        self._engine = engine

    def get_or_create(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> SessionState:
        state = self.get(session_id, user_id)
        if state is not None:
            return state
        return SessionState(session_id=session_id, user_id=user_id)

    def get(
        self, session_id: str, user_id: str = GUEST_USER_ID
    ) -> Optional[SessionState]:
        with Session(self._engine) as db:
            record = db.get(LearnSession, session_id)
            if record is None:
                return None
            if record.user_id != user_id:
                raise SessionAccessDeniedError("session not found")
            return self._to_state(record)

    def save(self, state: SessionState) -> None:
        with Session(self._engine) as db:
            record = db.get(LearnSession, state.session_id)
            if record is not None and record.user_id != state.user_id:
                raise SessionAccessDeniedError("session not found")
            if record is None:
                record = LearnSession(id=state.session_id, user_id=state.user_id)
            self._apply_state(record, state)
            db.add(record)
            db.commit()

    def reset(self, session_id: str, user_id: str = GUEST_USER_ID) -> bool:
        with Session(self._engine) as db:
            record = db.get(LearnSession, session_id)
            if record is None:
                return False
            if record.user_id != user_id:
                raise SessionAccessDeniedError("session not found")
            db.delete(record)
            db.commit()
            return True

    def count(self) -> int:
        with Session(self._engine) as db:
            return int(db.exec(select(func.count()).select_from(LearnSession)).one())

    def list_by_user(
        self, user_id: str = GUEST_USER_ID
    ) -> list[SessionSummary]:
        with Session(self._engine) as db:
            records = db.exec(
                select(LearnSession)
                .where(LearnSession.user_id == user_id)
                .order_by(LearnSession.updated_at.desc())
            ).all()
            summaries = []
            for record in records:
                material = (
                    db.get(Material, record.material_id)
                    if record.material_id
                    else None
                )
                material_title = (
                    (material.name or material.filename)
                    if material is not None
                    else (record.material_id or "未知教材")
                )
                summaries.append(
                    SessionSummary(
                        session_id=record.id,
                        kp_name=record.kp_name,
                        material_title=material_title,
                        created_at=record.created_at,
                    )
                )
            return summaries

    @staticmethod
    def _to_state(record: LearnSession) -> SessionState:
        messages_data = json.loads(record.messages_json or "[]")
        final_response = (
            FeynmanChatData.model_validate_json(record.final_response_json)
            if record.final_response_json
            else None
        )
        return SessionState(
            session_id=record.id,
            user_id=record.user_id,
            kp_id=record.kp_id,
            kp_name=record.kp_name,
            material_id=record.material_id,
            chapter_id=record.chapter_id,
            follow_up_count=record.current_turn,
            invalid_answer_count=record.invalid_answer_count,
            off_topic_count=record.off_topic_count,
            ended=record.status == "completed",
            last_provider=record.last_provider,
            fallback_used=record.fallback_used,
            messages=[ChatMessage.model_validate(item) for item in messages_data],
            final_response=final_response,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _apply_state(record: LearnSession, state: SessionState) -> None:
        record.user_id = state.user_id
        record.kp_id = state.kp_id
        record.kp_name = state.kp_name
        record.material_id = state.material_id
        record.chapter_id = state.chapter_id
        record.status = "completed" if state.ended else "ongoing"
        record.current_turn = state.follow_up_count
        record.invalid_answer_count = state.invalid_answer_count
        record.off_topic_count = state.off_topic_count
        record.last_provider = state.last_provider
        record.fallback_used = state.fallback_used
        record.messages_json = json.dumps(
            [message.model_dump(mode="json") for message in state.messages],
            ensure_ascii=False,
        )
        record.final_response_json = (
            state.final_response.model_dump_json() if state.final_response else None
        )
        record.created_at = state.created_at
        state.updated_at = datetime.now(timezone.utc)
        record.updated_at = state.updated_at
