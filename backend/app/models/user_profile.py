# coding: utf-8
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, Text
import json

class UserProfileBase(SQLModel):
    """学情画像基础字段定义，用于Pydantic请求体验证与数据传输"""
    nickname: Optional[str] = Field(default=None, description="用户昵称")
    exam_subject: Optional[str] = Field(default=None, description="报考学科：计算机/政治/数学/英语/其他")
    exam_sub_category: Optional[str] = Field(default=None, description="专业方向：如计算机->408统考/自命题")
    preparation_stage: Optional[str] = Field(default=None, description="备考阶段：基础/强化/冲刺")
    exam_type: Optional[str] = Field(default=None, description="备考类型：应届/二战/在职")
    target_school: Optional[str] = Field(default=None, description="目标院校")
    target_major: Optional[str] = Field(default=None, description="目标专业")

class UserProfile(UserProfileBase, table=True):
    """用户学情画像数据库表模型（对应 user_profile 表）"""
    __tablename__ = "user_profile"

    # 主键兼用户外键，关联 user 表的 id 字段，级联删除
    user_id: str = Field(
        primary_key=True,
        foreign_key="user.id",
        ondelete="CASCADE",
        description="用户ID"
    )
    
    # 核心痛点使用 TEXT 存储 JSON 序列化后的字符串数组
    pain_points_json: Optional[str] = Field(
        default=None, 
        sa_column=Column(Text), 
        description="核心痛点 JSON 数组字符串"
    )
    
    # 记录创建时间与更新时间
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="更新时间")

class UserProfileCreate(UserProfileBase):
    """创建或全量提交学情请求体验证模型"""
    pain_points: Optional[List[str]] = Field(default=None, description="核心痛点列表")

class UserProfileUpdate(SQLModel):
    """局部更新学情请求体验证模型（PATCH 方法使用）"""
    nickname: Optional[str] = None
    exam_subject: Optional[str] = None
    exam_sub_category: Optional[str] = None
    preparation_stage: Optional[str] = None
    exam_type: Optional[str] = None
    pain_points: Optional[List[str]] = None
    target_school: Optional[str] = None
    target_major: Optional[str] = None

class UserProfileResponse(UserProfileBase):
    """学情信息标准响应模型"""
    user_id: str
    pain_points: Optional[List[str]] = None
    created_at: str
    updated_at: str