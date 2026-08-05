from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

# ==================== 复习计划相关模型 ====================

class ReviewPlanItem(BaseModel):
    # 优先级序号，必须为整数类型
    priority: int
    # 推荐复习的教材名称，字符串类型
    material_name: str
    # 具体的教材页码提示（如"第3章 第30-33页"），字符串类型
    page_hint: str
    # 本次复习需要重点关注的内容，字符串类型
    focus: str
    # 给出该项复习建议的原因（通常与评分较低相关），字符串类型
    reason: str

class RelatedKp(BaseModel):
    # 关联知识点的唯一标识符ID，字符串类型
    kp_id: str
    # 关联知识点的中文名称，字符串类型
    kp_name: str
    # 说明当前知识点与该推荐知识点之间的关系，字符串类型
    relation: str

class PriorityItem(BaseModel):
    # 建议的复习顺序排名，整数类型
    rank: int
    # 对应的评分维度名称（如"理解深度"），字符串类型
    dimension: str
    # 知识点名称，字符串类型
    kp_name: str
    # 针对该维度的具体复习行动建议，字符串类型
    suggestion: str

class ReviewPlan(BaseModel):
    # 教材重读指引列表。指定子元素必须是 ReviewPlanItem 结构。
    # 使用 default_factory=list 确保每次实例化未传值时，生成独立的空列表 []
    reread_guide: List[ReviewPlanItem] = Field(default_factory=list)
    
    # 同类知识点推荐列表。指定子元素必须是 RelatedKp 结构。
    # 使用 default_factory=list 防止列表数据在多实例间共享内存
    related_kps: List[RelatedKp] = Field(default_factory=list)
    
    # 学习优先级排序列表。指定子元素必须是 PriorityItem 结构。
    # 使用 default_factory=list 保证初始状态安全为空
    priority_order: List[PriorityItem] = Field(default_factory=list)
# ================================================================

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
    review_plan: Optional[ReviewPlan] = None


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



