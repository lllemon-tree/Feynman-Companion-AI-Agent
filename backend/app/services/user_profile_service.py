# coding: utf-8
import json
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from backend.app.models.user_profile import (
    UserProfile,
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
)


class UserProfileService:
    """学情画像业务逻辑服务类"""

    @staticmethod
    def get_profile_by_user_id(session: Session, user_id: str) -> UserProfileResponse:
        """根据 user_id 查询学情，若无记录则返回全部字段为 None 的空结构（不报错 404）[cite: 1, 3]"""
        statement = select(UserProfile).where(UserProfile.user_id == user_id)
        profile = session.exec(statement).first()

        # 首次注册无学情记录时，返回默认空字段响应对象[cite: 1, 3]
        if not profile:
            return UserProfileResponse(
                user_id=user_id,
                nickname=None,
                exam_subject=None,
                exam_sub_category=None,
                preparation_stage=None,
                exam_type=None,
                pain_points=None,
                target_school=None,
                target_major=None,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

        # 解析数据库中的 JSON 痛点数组[cite: 1, 3]
        pain_points_list = None
        if profile.pain_points_json:
            try:
                pain_points_list = json.loads(profile.pain_points_json)
            except Exception:
                pain_points_list = []

        return UserProfileResponse(
            user_id=profile.user_id,
            nickname=profile.nickname,
            exam_subject=profile.exam_subject,
            exam_sub_category=profile.exam_sub_category,
            preparation_stage=profile.preparation_stage,
            exam_type=profile.exam_type,
            pain_points=pain_points_list,
            target_school=profile.target_school,
            target_major=profile.target_major,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def create_or_update_profile(
        session: Session, user_id: str, profile_in: UserProfileCreate
    ) -> UserProfileResponse:
        """首次提交或覆盖提交学情信息"""
        now_iso = datetime.now().isoformat()
        
        # 处理痛点数组的 JSON 序列化[cite: 1, 3]
        pain_points_str = (
            json.dumps(profile_in.pain_points, ensure_ascii=False)
            if profile_in.pain_points is not None # 三元表达式，若传入 None 则存储为 None，否则存储 JSON 字符串
            else None
        )

        statement = select(UserProfile).where(UserProfile.user_id == user_id)
        existing_profile = session.exec(statement).first()

        if existing_profile:
            # 存在记录时做全量更新
            existing_profile.nickname = profile_in.nickname
            existing_profile.exam_subject = profile_in.exam_subject
            existing_profile.exam_sub_category = profile_in.exam_sub_category
            existing_profile.preparation_stage = profile_in.preparation_stage
            existing_profile.exam_type = profile_in.exam_type
            existing_profile.pain_points_json = pain_points_str
            existing_profile.target_school = profile_in.target_school
            existing_profile.target_major = profile_in.target_major
            existing_profile.updated_at = now_iso
            session.add(existing_profile) # 重新添加到 session 中，确保 SQLAlchemy 追踪到对象的变化
            session.commit()
            session.refresh(existing_profile) # 重新加载对象，确保返回最新数据
        else:
            # 不存在记录时创建新记录
            new_profile = UserProfile(
                user_id=user_id,
                nickname=profile_in.nickname,
                exam_subject=profile_in.exam_subject,
                exam_sub_category=profile_in.exam_sub_category,
                preparation_stage=profile_in.preparation_stage,
                exam_type=profile_in.exam_type,
                pain_points_json=pain_points_str,
                target_school=profile_in.target_school,
                target_major=profile_in.target_major,
                created_at=now_iso,
                updated_at=now_iso,
            )
            session.add(new_profile) # 重新添加到 session 中，确保 SQLAlchemy 追踪到对象的变化
            session.commit()

        return UserProfileService.get_profile_by_user_id(session, user_id)

    @staticmethod
    def update_profile_partial(
        session: Session, user_id: str, profile_in: UserProfileUpdate
    ) -> UserProfileResponse:
        """增量更新（PATCH）学情信息"""
        statement = select(UserProfile).where(UserProfile.user_id == user_id)
        profile = session.exec(statement).first()

        # 若无记录，先初始化一条
        if not profile:
            empty_create = UserProfileCreate()
            UserProfileService.create_or_update_profile(session, user_id, empty_create)
            profile = session.exec(statement).first()

        # 仅更新前端传入的非 None 字段
        update_data = profile_in.model_dump(exclude_unset=True)

        # 由于前端传参字段为列表类型的 pain_points，而数据库映射字段为 JSON 字符串类型的 pain_points_json，
        # 此处先将 pain_points 从更新字典中 pop 弹出，既完成了从 List 到 JSON 字符串的数据类型转换并赋值给 pain_points_json，
        # 又避免了后续循环执行 setattr 时因属性名不匹配而报错。
        if "pain_points" in update_data:
            pain_points_val = update_data.pop("pain_points") # 使用 pop 方法从字典中移除 pain_points 字段，避免后续 setattr 时重复设置
            if pain_points_val is not None:
                profile.pain_points_json = json.dumps(pain_points_val, ensure_ascii=False)
            else:
                profile.pain_points_json = None

        for key, value in update_data.items():
            setattr(profile, key, value) # 使用 setattr 动态设置对象属性，避免手动逐个赋值，提高代码可维护性

        profile.updated_at = datetime.now().isoformat()
        session.add(profile)
        session.commit()

        return UserProfileService.get_profile_by_user_id(session, user_id)