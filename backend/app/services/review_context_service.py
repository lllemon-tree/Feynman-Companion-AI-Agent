import json
from typing import Optional, Protocol

from sqlalchemy import inspect
from sqlmodel import Session, select

from backend.app.models.auth import GUEST_USER_ID
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.models.review_attempt import ReviewAttempt
from backend.app.models.review_context import ReviewContext
from backend.app.models.review_context import TargetGap


class ReviewContextProvider(Protocol):
    """
    复习上下文 Provider 协议规范（岗位说明书）
    任何想给系统提供复习上下文的类，只要实现这个方法签名即可，无需显式继承本类。
    """
    def load_review_context(
        self, session_id: str, user_id: str
    ) -> Optional[ReviewContext]:
        ...


class DefaultReviewContextProvider:
    """Read only the current user's active review and its saved baseline."""

    def __init__(self, engine=None):
        self._engine = engine

    def load_review_context(
        self, session_id: str, user_id: str
    ) -> Optional[ReviewContext]:
        if self._engine is None or user_id == GUEST_USER_ID:
            return None
        if not inspect(self._engine).has_table("review_attempt"):
            return None
        with Session(self._engine) as db:
            attempt = db.exec(select(ReviewAttempt).where(
                ReviewAttempt.session_id == session_id,
                ReviewAttempt.user_id == user_id,
                ReviewAttempt.status == "active",
            )).first()
            if attempt is None:
                return None
            target_ids = json.loads(attempt.target_gap_ids or "[]")
            gaps = [db.get(KnowledgeGap, gap_id) for gap_id in target_ids]
            gaps = [
                gap for gap in gaps
                if gap is not None and gap.user_id == user_id and gap.kp_id == attempt.kp_id
            ]
            if not gaps:
                return None
            baseline = (
                db.get(DiagnosticReport, attempt.baseline_report_id)
                if attempt.baseline_report_id else None
            )
            if baseline is not None and (baseline.user_id != user_id or baseline.kp_id != attempt.kp_id):
                baseline = None
            scores = {
                item["name"]: item["score"]
                for item in json.loads(baseline.dimensions or "[]")
                if "name" in item and "score" in item
            } if baseline is not None else None
            focus = list(dict.fromkeys(gap.dimension for gap in gaps))
            first = gaps[0]
            return ReviewContext(
                gap_id=first.id,
                kp_id=attempt.kp_id,
                kp_name=first.kp_name,
                review_focus=focus,
                target_gap=TargetGap(
                    gap_id=first.id,
                    kp_id=attempt.kp_id,
                    kp_name=first.kp_name,
                    weak_dimensions=focus,
                    gap_desc="；".join(
                        gap.gap_description for gap in gaps if gap.gap_description
                    ),
                    previous_scores=scores,
                ),
                previous_report_summary=baseline.overall_comment if baseline else None,
            )


def safe_load_review_context(
    provider: Optional[ReviewContextProvider],
    session_id: str,
    user_id: str,
) -> Optional[ReviewContext]:
    """
    安全加载复习上下文的防护函数：
    1. provider 未注入时，返回 None。
    2. 正常执行时，返回对应的 ReviewContext 或 None。
    3. provider 执行发生任何异常时，打印提示并吞掉异常，强制返回 None。
    
    该设计保证外部数据库崩溃或接口报错时，主对话状态机绝不中断。
    """
    if provider is None:
        return None

    try:
        return provider.load_review_context(session_id=session_id, user_id=user_id)
    except Exception as e:
        print(f"⚠️ load_review_context failed, fallback to None: {type(e).__name__}: {e}")
        return None
