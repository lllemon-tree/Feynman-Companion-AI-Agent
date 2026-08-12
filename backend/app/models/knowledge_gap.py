# coding: utf-8
# 导入 uuid 模块用于生成唯一的漏洞 ID
import uuid
# 从 datetime 模块导入 datetime 用于处理时间戳
from datetime import datetime
# 从 typing 模块导入 Optional 类型注解声明可空字段
from typing import Literal, Optional
# 从 sqlmodel 库导入 SQLModel 模型基类与 Field 字段配置函数
from sqlmodel import SQLModel, Field


KnowledgeGapStatus = Literal["open", "reviewing", "resolved"]


def generate_gap_id() -> str:
    """生成带有 gap- 前缀的唯一主键 ID（如 gap-3f8a92b1）"""
    return f"gap-{uuid.uuid4().hex[:8]}"


class KnowledgeGapBase(SQLModel):
    """知识漏洞基础字段定义：抽离公共属性供模型与响应结构复用"""

    # 关联的知识点 ID，必须存在
    kp_id: str = Field(description="知识点ID")
    # 知识点名称（如：冒泡排序），用于前端显示
    kp_name: str = Field(description="知识点名称")
    # 关联的教材 ID（可选）
    material_id: Optional[str] = Field(default=None, description="教材ID")
    # 教材名称（可选）
    material_name: Optional[str] = Field(default=None, description="教材名称")
    # 诊断出的薄弱维度（理解深度/表达完整性/逻辑连贯性/结构化能力）
    dimension: str = Field(description="诊断维度")
    # 漏洞的具体分析描述文本
    gap_description: Optional[str] = Field(
        default=None, description="漏洞具体描述文本"
    )
    # 严重程度 1-5（由得分映射决定）
    severity: int = Field(default=3, description="严重程度1-5")
    # 用户在该维度的具体得分（0-10分）
    score: int = Field(description="当时维度得分0-10")
    # 漏洞状态：open(待复习)、reviewing(复习中)、resolved(已掌握)
    status: str = Field(default="open", description="漏洞状态: open/reviewing/resolved")
    # 产生该漏洞的来源会话 ID
    source_session_id: Optional[str] = Field(
        default=None, description="来源 LearnSession ID"
    )


class KnowledgeGap(KnowledgeGapBase, table=True):
    """知识漏洞数据库表模型（对应 SQLite 的 knowledge_gap 表）"""

    # 指定数据库中的真实表名为 knowledge_gap
    __tablename__ = "knowledge_gap"

    # 主键字段：自增前缀 ID，默认调用 generate_gap_id 函数生成
    id: str = Field(
        default_factory=generate_gap_id,
        primary_key=True,
        description="漏洞唯一ID(gap-xxx)",
    )

    # 关联的用户 ID，创建索引以便快速按用户检索漏洞[cite: 1, 3]
    user_id: str = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,  # 相当于对应 SQL 中的 idx_gap_user 索引[cite: 1, 3]
        description="用户ID",
    )

    # 状态字段增加索引，加速按 user_id + status 联合查询[cite: 1, 3]
    # 在查询或去重场景中，结合 user_id 和 kp_id 进行快速定位[cite: 1, 3]
    kp_id: str = Field(index=True, description="知识点ID")
    status: str = Field(default="open", index=True, description="漏洞状态")

    # 复习次数统计，默认为 0
    review_count: int = Field(default=0, description="复习次数")
    # 上次复习时间
    last_reviewed_at: Optional[str] = Field(
        default=None, description="上次复习时间"
    )
    # 下次推荐复习时间（预留 SRS 逻辑使用）
    next_review_at: Optional[str] = Field(
        default=None, description="下次推荐复习时间"
    )

    # 记录漏洞创建与更新时间
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="创建时间"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="更新时间"
    )


class KnowledgeGapUpdate(SQLModel):
    """漏洞状态更新请求体模型（PATCH /api/v1/gaps/{gap_id} 使用）[cite: 1, 3]"""

    # 仅允许更新漏洞的状态[cite: 1, 3]
    status: KnowledgeGapStatus = Field(
        description="更新后的状态: open/reviewing/resolved"
    )


class KnowledgeGapResponse(KnowledgeGapBase):
    """漏洞标准单条响应数据模型"""

    # 漏洞唯一标识 ID
    gap_id: str
    # 归属的用户 ID
    user_id: str
    # 创建与更新时间
    created_at: str
    updated_at: str
