from backend.app.core.database import engine
from sqlmodel import Session
from backend.app.models.auth import User
from backend.app.services.knowledge_gap_service import KnowledgeGapService

with Session(engine) as session:
    # 模拟首次写入低分漏洞 (得分 4 -> 严重程度 severity 4)
    KnowledgeGapService.upsert_gap_from_report(
        session=session,
        user_id="user-b517b44fed204ac2ac857bc7fc427ac9",  # 从当前登录 token 对应的 user_id
        kp_id="kp-demo-1",
        kp_name="冒泡排序",
        material_id="mat-01",
        material_name="数据结构与算法",
        dimension="理解深度",
        score=4,
        gap_description="对冒泡排序的时间复杂度推导不清楚"
    )