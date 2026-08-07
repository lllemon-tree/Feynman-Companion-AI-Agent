# coding: utf-8
"""
后端 A —— prompt_builder 单元测试
================================
测试目标（先想行为，再写测试）：
  1. 画像有痛点 → build_system_prompt 返回的 Prompt 里包含对应教学指令
  2. 画像为 None（游客/未填写）→ 使用默认 Prompt，不报错、不含个性化策略段
  3. 画像有备考阶段 → Prompt 里包含对应阶段指令
"""
import pytest

from backend.app.models.user_profile import UserProfileResponse
from backend.app.services.prompt_builder import build_system_prompt


def _make_profile(pain_points=None, stage=None):
    """测试辅助函数：快速构造一个学情画像对象。

    UserProfileResponse 必填字段只有 user_id / created_at / updated_at，
    其余画像字段（痛点、阶段等）默认为 None。
    """
    return UserProfileResponse(
        user_id="user-001",
        pain_points=pain_points,      # None 或 ["输出薄弱", ...]
        preparation_stage=stage,      # None 或 "基础"/"强化"/"冲刺"
        created_at="2026-08-03T00:00:00",
        updated_at="2026-08-03T00:00:00",
    )


def test_pain_point_injects_instruction():
    """画像含「输出薄弱」→ Prompt 里必须出现对应的教学指令。"""
    # Arrange（准备）：造一个只有痛点的画像
    profile = _make_profile(pain_points=["输出薄弱"])
    # Act（执行）：调用被测函数
    prompt = build_system_prompt(kp_name="冒泡排序", rubric={}, profile=profile)
    # Assert（断言）：输出里应该包含痛点和指令关键词
    assert "输出薄弱" in prompt
    assert "先简后详" in prompt        # 「输出薄弱」策略里的具体内容


def test_no_profile_falls_back_to_default():
    """没有画像（游客/未填写）→ 不包含个性化策略段，且不报错。"""
    # Arrange + Act
    prompt = build_system_prompt(kp_name="冒泡排序", rubric={}, profile=None)
    # Assert
    assert "【个性化教学策略" not in prompt


def test_stage_injects_stage_instruction():
    """画像含「冲刺」阶段 → Prompt 里出现阶段指令。"""
    profile = _make_profile(pain_points=None, stage="冲刺")
    prompt = build_system_prompt(kp_name="冒泡排序", rubric={}, profile=profile)
    assert "冲刺阶段" in prompt


def test_unknown_pain_point_is_ignored():
    """画像含字典里没有的痛点 → 不报错，正常返回 Prompt。"""
    profile = _make_profile(pain_points=["不存在的痛点XYZ"])
    prompt = build_system_prompt(kp_name="冒泡排序", rubric={}, profile=profile)
    # 未知痛点不生成指令，所以没有个性化策略段
    assert "【个性化教学策略" not in prompt
