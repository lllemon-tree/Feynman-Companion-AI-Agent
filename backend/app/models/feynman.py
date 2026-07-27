from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NextAction(str, Enum):
    FOLLOW_UP = "follow_up"
    GENERATE_REPORT = "generate_report"
    GUIDE_TOPIC = "guide_topic"


class FeynmanChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    kp_id: Optional[str] = Field(default=None, min_length=1)
    user_input: str = Field(..., min_length=1, max_length=500)


class ResetSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class CardPreview(BaseModel):
    total_score: int = Field(..., ge=0, le=40)
    summary: str = Field(..., min_length=1, max_length=30)


class DimensionReport(BaseModel):
    name: str
    score: int = Field(..., ge=0, le=10)
    analysis: str = Field(..., min_length=1)
    suggestion: str = Field(..., min_length=1)


class FinalReport(BaseModel):
    dimensions: List[DimensionReport] = Field(..., min_length=4, max_length=4)
    overall_comment: str = Field(..., min_length=1, max_length=200)


class FeynmanChatData(BaseModel):
    next_action: NextAction
    reply_text: str = Field(..., min_length=1)
    card_preview: Optional[CardPreview] = None
    final_report: Optional[FinalReport] = None


class ApiResponse(BaseModel):
    code: int
    msg: str
    data: Optional[FeynmanChatData] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ResetSessionData(BaseModel):
    session_id: str
    reset: bool


class GreetingData(BaseModel):
    reply_text: str = Field(..., min_length=1)
    kp_id: str
    kp_name: str


class GreetingResponse(BaseModel):
    code: int
    msg: str
    data: GreetingData


class ResetSessionResponse(BaseModel):
    code: int
    msg: str
    data: Optional[ResetSessionData] = None


class SessionDebugData(BaseModel):
    session_id: str
    exists: bool
    follow_up_count: int = 0
    invalid_answer_count: int = 0
    off_topic_count: int = 0
    ended: bool = False
    message_count: int = 0
    last_provider: str = "none"
    fallback_used: bool = False
    kp_id: Optional[str] = None
    kp_name: Optional[str] = None
    material_id: Optional[str] = None
    chapter_id: Optional[str] = None
    recent_messages: List[ChatMessage] = Field(default_factory=list)


class SessionDebugResponse(BaseModel):
    code: int
    msg: str
    data: SessionDebugData


class SessionDetailData(BaseModel):
    session_id: str
    kp_id: Optional[str] = None
    kp_name: Optional[str] = None
    material_id: Optional[str] = None
    chapter_id: Optional[str] = None
    chat_history: List[ChatMessage] = Field(default_factory=list)
    report_data: Optional[FeynmanChatData] = None
    created_at: str
    updated_at: str


class SessionDetailResponse(BaseModel):
    code: int
    msg: str
    data: SessionDetailData


class SessionSummaryData(BaseModel):
    session_id: str
    kp_name: Optional[str] = None
    material_title: str
    created_at: str


class SessionListResponse(BaseModel):
    code: int
    msg: str
    data: List[SessionSummaryData] = Field(default_factory=list)
