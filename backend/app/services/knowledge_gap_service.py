import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import Session, func, select

from backend.app.models.knowledge_gap import (
    KnowledgeGap,
    KnowledgeGapUpdate,
)
from backend.app.models.review_attempt import ReviewAttempt
from backend.app.services.review_rules import (
    SRS_INTERVAL_DAYS,
    is_mastered,
    next_review_at,
    severity_for_score,
)


class ActiveReviewConflict(Exception):
    pass


class KnowledgeGapService:
    """知识漏洞库业务逻辑服务类"""

    @staticmethod
    def calculate_severity(score: int) -> int:
        return severity_for_score(score)

    @staticmethod
    def srs_interval_days(review_count: int) -> int:
        """Return the PRD interval for the completed review number."""
        normalized_count = max(review_count, 1)
        index = min(normalized_count - 1, len(SRS_INTERVAL_DAYS) - 1)
        return SRS_INTERVAL_DAYS[index]

    @staticmethod
    def calculate_next_review_at(
        review_count: int,
        reviewed_at: datetime,
    ) -> datetime:
        """Calculate the next review time using the 1/3/7/14/30-day schedule."""
        return next_review_at(review_count, reviewed_at)

    @staticmethod
    def upsert_gap_from_report(
        session: Session,
        user_id: str,
        kp_id: str,
        kp_name: str,
        material_id: Optional[str],
        material_name: Optional[str],
        dimension: str,
        score: int,
        gap_description: Optional[str],
        source_session_id: Optional[str] = None,
    ) -> Optional[KnowledgeGap]:
        """对话报告后置钩子调用的自动入库/去重更新方法（后端 B 集成使用）[cite: 1, 2]"""
        # 1. 游客用户跳过漏洞入库[cite: 1, 3]
        if user_id == "guest":
            return None

        now_iso = datetime.now().isoformat()
        severity_val = KnowledgeGapService.calculate_severity(score)

        # 2. 查询是否存在相同 user_id + kp_id + dimension 且 status='open' 的记录（去重判断）[cite: 1, 3]
        statement = select(KnowledgeGap).where(
            KnowledgeGap.user_id == user_id,
            KnowledgeGap.kp_id == kp_id,
            KnowledgeGap.dimension == dimension,
        )
        existing_gap = session.exec(statement).first()

        if is_mastered(score):
            if existing_gap is None:
                return None
            existing_gap.score = score
            existing_gap.severity = severity_val
            existing_gap.status = "resolved"
            existing_gap.resolved_at = now_iso
            existing_gap.resolution_source = "assessment"
            existing_gap.next_review_at = None
            existing_gap.updated_at = now_iso
            session.add(existing_gap)
            session.commit()
            session.refresh(existing_gap)
            return existing_gap

        if existing_gap:
            # 3. 存在 open 漏洞则仅更新分数、严重程度、描述和更新时间[cite: 1, 3]
            existing_gap.score = score
            existing_gap.severity = severity_val
            if gap_description:
                existing_gap.gap_description = gap_description
            existing_gap.updated_at = now_iso
            if existing_gap.status == "resolved" and not is_mastered(score):
                existing_gap.status = "open"
                existing_gap.resolved_at = None
                existing_gap.resolution_source = None
                existing_gap.next_review_at = next_review_at(0, datetime.now()).isoformat()
            session.add(existing_gap)
            session.commit()
            session.refresh(existing_gap)
            return existing_gap
        else:
            # 4. 不存在则创建新的漏洞记录
            new_gap = KnowledgeGap(
                user_id=user_id,
                kp_id=kp_id,
                kp_name=kp_name,
                material_id=material_id,
                material_name=material_name,
                dimension=dimension,
                gap_description=gap_description,
                severity=severity_val,
                score=score,
                status="open",
                next_review_at=next_review_at(0, datetime.now()).isoformat(),
                source_session_id=source_session_id,
                created_at=now_iso,
                updated_at=now_iso,
            )
            session.add(new_gap)
            session.commit()
            session.refresh(new_gap)
            return new_gap

    @staticmethod
    def get_user_gaps(
        session: Session,
        user_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询用户的漏洞列表，支持按状态过滤[cite: 1, 3]"""
        # 构建基础查询语句
        query = select(KnowledgeGap).where(KnowledgeGap.user_id == user_id)
        
        # 若指定了状态过滤条件（如 open/reviewing/resolved），添加状态过滤[cite: 1, 3]
        if status:
            query = query.where(KnowledgeGap.status == status)

        # 查询符合条件的总数
        total_statement = select(func.count()).select_from(query.subquery())
        total = session.exec(total_statement).one()

        # 增加排序（按创建时间倒序）与分页切片（offset + limit）
        offset = (page - 1) * page_size
        items_query = query.order_by(KnowledgeGap.created_at.desc()).offset(offset).limit(page_size)
        gaps = session.exec(items_query).all()

        # 转换为前端契约要求的格式
        items = [KnowledgeGapService._gap_to_dict(gap) for gap in gaps]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def update_gap_status(
        session: Session,
        user_id: str,
        gap_id: str,
        gap_in: KnowledgeGapUpdate,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Only manual open/resolved transitions; review start uses /reviews/start."""
        if gap_in.status == "reviewing":
            raise ValueError("cannot patch to reviewing directly, use /reviews/start")
        statement = select(KnowledgeGap).where(
            KnowledgeGap.id == gap_id, KnowledgeGap.user_id == user_id
        )
        gap = session.exec(statement).first()

        if not gap:
            return None

        active = session.exec(select(ReviewAttempt).where(
            ReviewAttempt.user_id == user_id,
            ReviewAttempt.kp_id == gap.kp_id,
            ReviewAttempt.status == "active",
        )).all()
        if any(gap_id in json.loads(item.target_gap_ids or "[]") for item in active for gap_id in [gap.id]):
            raise ActiveReviewConflict("gap is in an active review, complete the review first")

        reviewed_at = now or datetime.now()

        # 更新状态与修改时间
        gap.status = gap_in.status
        gap.updated_at = reviewed_at.isoformat()

        gap.next_review_at = None
        gap.resolved_at = reviewed_at.isoformat() if gap_in.status == "resolved" else None
        gap.resolution_source = "manual" if gap_in.status == "resolved" else None

        session.add(gap)
        session.commit()
        session.refresh(gap)

        return {
            "gap_id": gap.id,
            "status": gap.status,
            "review_count": gap.review_count,
            "last_reviewed_at": gap.last_reviewed_at,
            "next_review_at": gap.next_review_at,
            "resolved_at": gap.resolved_at,
            "resolution_source": gap.resolution_source,
        }

    @staticmethod
    def get_review_due_gaps(
        session: Session,
        user_id: str,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return gaps due by local calendar day, including legacy naive timestamps."""
        local_timezone = datetime.now().astimezone().tzinfo
        current = now or datetime.now().astimezone()
        today = current.astimezone(local_timezone).date() if current.tzinfo else current.date()
        query = (
            select(KnowledgeGap)
            .where(
                KnowledgeGap.user_id == user_id,
                KnowledgeGap.status.in_(["open", "reviewing"]),
                KnowledgeGap.next_review_at.is_not(None),
            )
        )
        gaps = []
        for gap in session.exec(query).all():
            try:
                scheduled = datetime.fromisoformat(gap.next_review_at)
            except (TypeError, ValueError):
                continue
            due_date = (
                scheduled.astimezone(local_timezone).date()
                if scheduled.tzinfo else scheduled.date()
            )
            if due_date <= today:
                gaps.append(gap)
        grouped: dict[str, list[KnowledgeGap]] = {}
        for gap in gaps:
            grouped.setdefault(gap.kp_id, []).append(gap)

        active = session.exec(select(ReviewAttempt).where(
            ReviewAttempt.user_id == user_id,
            ReviewAttempt.status == "active",
        )).all()
        active_by_gap = {
            gap_id: attempt.id
            for attempt in active
            for gap_id in json.loads(attempt.target_gap_ids or "[]")
        }
        items = []
        for kp_gaps in grouped.values():
            focus = min(
                kp_gaps,
                key=lambda gap: (gap.score, -gap.severity, gap.next_review_at or ""),
            )
            item = KnowledgeGapService._gap_to_dict(focus)
            item["dimension_count"] = len(kp_gaps)
            item["target_dimensions"] = [gap.dimension for gap in kp_gaps]
            item["active_review_id"] = next(
                (active_by_gap[gap.id] for gap in kp_gaps if gap.id in active_by_gap),
                None,
            )
            item["action"] = "continue" if item["active_review_id"] else "start"
            items.append(item)
        items.sort(key=lambda item: (-item["severity"], item["next_review_at"] or ""))
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": max(len(items), 20),
        }

    @staticmethod
    def get_gap_stats(session: Session, user_id: str) -> Dict[str, Any]:
        """Count knowledge points per status while retaining dimension totals."""
        # 查询该用户的所有漏洞
        statement = select(KnowledgeGap).where(KnowledgeGap.user_id == user_id)
        gaps = session.exec(statement).all()

        by_status = {"open": 0, "reviewing": 0, "resolved": 0}
        by_dimension = {
            "理解深度": 0,
            "表达完整性": 0,
            "逻辑连贯性": 0,
            "结构化能力": 0,
        }

        kp_ids = set()
        kp_ids_by_status = {status: set() for status in by_status}
        for gap in gaps:
            kp_ids.add(gap.kp_id)
            if gap.status in by_status:
                kp_ids_by_status[gap.status].add(gap.kp_id)
            # 统计按维度分布
            if gap.dimension in by_dimension:
                by_dimension[gap.dimension] += 1
            else:
                by_dimension[gap.dimension] = 1

        return {
            "total": len(kp_ids),
            "by_status": {
                status: len(status_kp_ids)
                for status, status_kp_ids in kp_ids_by_status.items()
            },
            "by_dimension": by_dimension,
        }

    @staticmethod
    def _gap_to_dict(gap: KnowledgeGap) -> Dict[str, Any]:
        return {
            "gap_id": gap.id,
            "kp_id": gap.kp_id,
            "kp_name": gap.kp_name,
            "material_id": gap.material_id,
            "material_name": gap.material_name,
            "dimension": gap.dimension,
            "score": gap.score,
            "severity": gap.severity,
            "status": gap.status,
            "gap_description": gap.gap_description,
            "review_count": gap.review_count,
            "last_reviewed_at": gap.last_reviewed_at,
            "next_review_at": gap.next_review_at,
            "resolved_at": gap.resolved_at,
            "resolution_source": gap.resolution_source,
            "created_at": gap.created_at,
            "updated_at": gap.updated_at,
        }
