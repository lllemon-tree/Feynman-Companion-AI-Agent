"""Unrestricted learning conversations, separate from legacy KP-bound sessions."""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversation"

    id: str = SQLField(primary_key=True)
    user_id: str = SQLField(foreign_key="user.id", index=True)
    title: str = SQLField(default="新对话")
    created_at: datetime = SQLField(default_factory=utc_now)
    updated_at: datetime = SQLField(default_factory=utc_now)


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_message"

    id: str = SQLField(primary_key=True)
    conversation_id: str = SQLField(foreign_key="conversation.id", index=True)
    role: str
    mode: str
    model: Optional[str] = None
    content: str
    assessment_json: Optional[str] = None
    created_at: datetime = SQLField(default_factory=utc_now)


Mode = Literal["expert", "beginner"]


class QuoteEvidence(BaseModel):
    quote: str = Field(min_length=1)
    observation: str = Field(min_length=1)


class FreeAssessment(BaseModel):
    topic: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence: list[QuoteEvidence] = Field(default_factory=list)
    next_step: str = Field(min_length=1)
    basis: str = "无指定教材；根据用户讲解与通用知识评估"


class MessageData(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    mode: Mode
    model: Optional[str] = None
    content: str
    assessment: Optional[FreeAssessment] = None
    created_at: datetime


class ConversationData(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageData] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    mode: Mode
    model: Optional[str] = None


class SendMessageData(BaseModel):
    user_message: MessageData
    assistant_message: MessageData


class FinishExplanationRequest(BaseModel):
    mode: Literal["beginner"] = "beginner"
    model: Optional[str] = None


class ApiResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: object
