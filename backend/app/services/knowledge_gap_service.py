from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select, func
from backend.app.models.knowledge_gap import (
    KnowledgeGap,
    KnowledgeGapUpdate,
    KnowledgeGapResponse,
)


class KnowledgeGapService:
    """知识漏洞库业务逻辑服务类"""

    @staticmethod
    def calculate_severity(score: int) -> int:
        """依据 PRD 规则，根据维度得分计算严重程度 severity (1-5)[cite: 1, 3]"""
        if score <= 3:
            return 5  # 0-3分映射为 severity 5（最严重）[cite: 1, 3]
        elif score <= 5:
            return 4  # 4-5分映射为 severity 4[cite: 1, 3]
        elif score == 6:
            return 3  # 6分映射为 severity 3[cite: 1, 3]
        else:
            return 1  # 预留：更高分默认为较低严重程度

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
    ) -> KnowledgeGap:
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
            KnowledgeGap.status == "open",
        )
        existing_gap = session.exec(statement).first()

        if existing_gap:
            # 3. 存在 open 漏洞则仅更新分数、严重程度、描述和更新时间[cite: 1, 3]
            existing_gap.score = score
            existing_gap.severity = severity_val
            if gap_description:
                existing_gap.gap_description = gap_description
            existing_gap.updated_at = now_iso
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
        items = [
            {
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
                "created_at": gap.created_at,
            }
            for gap in gaps
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def update_gap_status(
        session: Session, user_id: str, gap_id: str, gap_in: KnowledgeGapUpdate
    ) -> Optional[Dict[str, Any]]:
        """更新漏洞状态（例如标记为 reviewing 或 resolved）[cite: 1, 3]"""
        statement = select(KnowledgeGap).where(
            KnowledgeGap.id == gap_id, KnowledgeGap.user_id == user_id
        )
        gap = session.exec(statement).first()

        if not gap:
            return None

        # 更新状态与修改时间
        gap.status = gap_in.status
        gap.updated_at = datetime.now().isoformat()
        
        # 若标记为复习中，可递增复习次数
        if gap_in.status == "reviewing":
            gap.review_count += 1
            gap.last_reviewed_at = datetime.now().isoformat()

        session.add(gap)
        session.commit()
        session.refresh(gap)

        return {
            "gap_id": gap.id,
            "status": gap.status,
        }

    @staticmethod
    def get_gap_stats(session: Session, user_id: str) -> Dict[str, Any]:
        """按状态和维度统计用户的漏洞数量[cite: 1, 3]"""
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

        total = len(gaps)
        for gap in gaps:
            # 统计按状态分布
            if gap.status in by_status:
                by_status[gap.status] += 1
            # 统计按维度分布
            if gap.dimension in by_dimension:
                by_dimension[gap.dimension] += 1
            else:
                by_dimension[gap.dimension] = 1

        return {
            "total": total,
            "by_status": by_status,
            "by_dimension": by_dimension,
        }