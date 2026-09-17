"""Create and cache grounded knowledge cards without slowing material ingestion."""

import hashlib
import json
from threading import Lock
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, select
from sqlalchemy.engine import Engine

from backend.app.core.config import get_settings
from backend.app.core.database import engine
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.knowledge import Chapter, KP, Material
from backend.app.models.learning import (
    KnowledgeCard,
    KnowledgeCardContent,
    KnowledgeCardData,
    KnowledgeCardFavorite,
    KnowledgeCardSection,
    KnowledgeCardSource,
)
from backend.app.services.deepseek_client import DeepSeekClient
from backend.app.services.kp_provider import SQLiteKnowledgePointProvider


CARD_KEYS = (
    "one_sentence",
    "why_it_matters",
    "core_points",
    "minimum_example",
    "misconceptions",
    "explanation_prompts",
)

_active_enhancements: set[str] = set()
_enhancement_guard = Lock()


def _owned_kp(db: Session, kp_id: str, user_id: str) -> tuple[KP, Chapter, Material]:
    kp = db.get(KP, kp_id)
    if kp is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    chapter = db.get(Chapter, kp.chapter_id)
    material = db.get(Material, chapter.material_id) if chapter else None
    if chapter is None or material is None or material.user_id != user_id:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if kp.status != "done":
        raise HTTPException(status_code=409, detail="知识点仍在生成中，请稍后再试")
    return kp, chapter, material


def _digest(kp: KP, chunks) -> str:
    payload = {
        "card_generation_revision": "v2-background-flash",
        "name": kp.name,
        "summary": kp.summary,
        "rubric": kp.rubric,
        "page_start": kp.page_start,
        "page_end": kp.page_end,
        "chunks": [(item.chunk_id, item.page_no, item.text) for item in chunks],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _rubric_content(rubric: dict, key: str):
    value = rubric.get(key, {})
    return value.get("content", "") if isinstance(value, dict) else value


def _fallback_content(point, generation_status: str = "ready") -> KnowledgeCardContent:
    chunk_ids = [item.chunk_id for item in point.source_chunks]
    concept = str(_rubric_content(point.rubric, "concept_prerequisite") or point.summary)
    mechanism = str(_rubric_content(point.rubric, "core_mechanism") or "")
    principle = str(_rubric_content(point.rubric, "principle_proof") or "")
    misunderstandings = _rubric_content(point.rubric, "common_misunderstandings")
    if not isinstance(misunderstandings, list):
        misunderstandings = [str(misunderstandings)] if misunderstandings else []
    core_points = [item for item in (concept, mechanism, principle) if item and item != "暂无说明"]
    text_size = sum(len(item.text) for item in point.source_chunks)
    coverage = "sufficient" if text_size >= 800 and len(core_points) >= 3 else (
        "partial" if point.source_chunks else "limited"
    )
    notice = {
        "sufficient": "教材已覆盖主要定义、机制与原理，卡片对内容进行了结构化整理。",
        "partial": "教材能够支撑部分核心内容；示例和讲解提示属于辅助理解，不作为必答项。",
        "limited": "当前教材依据较少，卡片只展示能够确认的内容，补充部分不作为评分依据。",
    }[coverage]
    excerpt = "\n".join(item.text.strip() for item in point.source_chunks[:2] if item.text.strip())[:500]
    sections = [
        KnowledgeCardSection(
            key="one_sentence", title="一句话理解", content=point.summary or concept,
            source_type="textbook_rewrite", source_chunk_ids=chunk_ids,
            required_for_evaluation=True,
        ),
        KnowledgeCardSection(
            key="why_it_matters", title="为什么需要", content=principle,
            source_type="textbook_rewrite", source_chunk_ids=chunk_ids,
            required_for_evaluation=bool(principle and principle != "暂无说明"),
        ),
        KnowledgeCardSection(
            key="core_points", title="核心内容", bullets=core_points,
            source_type="textbook_rewrite", source_chunk_ids=chunk_ids,
            required_for_evaluation=bool(core_points),
        ),
        KnowledgeCardSection(
            key="minimum_example", title="教材线索", content=excerpt or "当前教材没有提供可确认的示例。",
            source_type="textbook" if excerpt else "model_supplement",
            source_chunk_ids=chunk_ids if excerpt else [], required_for_evaluation=False,
        ),
        KnowledgeCardSection(
            key="misconceptions", title="容易混淆", bullets=[str(item) for item in misunderstandings[:3]],
            source_type="textbook_rewrite" if chunk_ids else "model_supplement",
            source_chunk_ids=chunk_ids, required_for_evaluation=False,
        ),
        KnowledgeCardSection(
            key="explanation_prompts", title="讲解提示",
            bullets=[
                f"{point.name}是什么？",
                "它主要解决什么问题？",
                "它是怎样起作用的？",
                "能否用一个最小例子说明？",
            ],
            source_type="model_supplement", source_chunk_ids=[],
            required_for_evaluation=False,
        ),
    ]
    return KnowledgeCardContent(
        generation_status=generation_status,
        coverage_level=coverage,
        coverage_notice=notice,
        estimated_minutes=max(3, min(8, 3 + len(core_points))),
        sections=sections,
    )


def _sanitize_content(raw: dict, point) -> KnowledgeCardContent:
    fallback = _fallback_content(point)
    try:
        generated = KnowledgeCardContent.model_validate(raw)
    except (ValidationError, TypeError):
        return fallback
    valid_ids = {item.chunk_id for item in point.source_chunks}
    by_key: dict[str, KnowledgeCardSection] = {}
    for section in generated.sections:
        if section.key not in CARD_KEYS or section.key in by_key:
            continue
        refs = [item for item in section.source_chunk_ids if item in valid_ids]
        if section.source_type in {"textbook", "textbook_rewrite"} and not refs:
            section.source_type = "model_supplement"
            section.required_for_evaluation = False
        if section.source_type == "model_supplement":
            refs = []
            section.required_for_evaluation = False
        section.source_chunk_ids = refs
        section.bullets = [item.strip() for item in section.bullets if item.strip()][:5]
        section.content = section.content.strip()
        by_key[section.key] = section
    fallback_by_key = {section.key: section for section in fallback.sections}
    generated.sections = [by_key.get(key, fallback_by_key[key]) for key in CARD_KEYS]
    generated.generation_status = "ready"
    return generated


def _claim_enhancement(kp_id: str) -> bool:
    with _enhancement_guard:
        if kp_id in _active_enhancements:
            return False
        _active_enhancements.add(kp_id)
        return True


def _release_enhancement(kp_id: str) -> None:
    with _enhancement_guard:
        _active_enhancements.discard(kp_id)


async def enhance_knowledge_card(
    kp_id: str,
    user_id: str,
    db_engine: Engine = engine,
) -> None:
    """Enhance an immediately available textbook card without blocking its response."""
    if not _claim_enhancement(kp_id):
        return
    source_digest = ""
    try:
        settings = get_settings()
        if settings.llm_provider != "deepseek" or not settings.deepseek_configured:
            return
        with Session(db_engine) as db:
            kp, _chapter, _material = _owned_kp(db, kp_id, user_id)
            point = SQLiteKnowledgePointProvider(db_engine).get(kp_id)
            if point is None:
                return
            source_digest = _digest(kp, point.source_chunks)
            card = db.exec(select(KnowledgeCard).where(KnowledgeCard.kp_id == kp_id)).first()
            if card is None or card.source_digest != source_digest:
                return
            current = KnowledgeCardContent.model_validate_json(card.content_json)
            if current.generation_status == "ready":
                return

        raw = await DeepSeekClient(settings).generate_knowledge_card(point)
        enhanced = _sanitize_content(raw, point)
        now = datetime.now(timezone.utc)
        with Session(db_engine) as db:
            card = db.exec(select(KnowledgeCard).where(KnowledgeCard.kp_id == kp_id)).first()
            if card is None or card.source_digest != source_digest:
                return
            card.content_json = enhanced.model_dump_json()
            card.version += 1
            card.updated_at = now
            db.add(card)
            db.commit()
    except Exception as exc:
        # Keep the grounded base card readable. A later card request may retry enhancement.
        with Session(db_engine) as db:
            card = db.exec(select(KnowledgeCard).where(KnowledgeCard.kp_id == kp_id)).first()
            if card is not None and (not source_digest or card.source_digest == source_digest):
                content = KnowledgeCardContent.model_validate_json(card.content_json)
                content.generation_status = "failed"
                card.content_json = content.model_dump_json()
                card.updated_at = datetime.now(timezone.utc)
                db.add(card)
                db.commit()
        print(f"Knowledge card enhancement failed for {kp_id}: {type(exc).__name__}: {exc}")
    finally:
        _release_enhancement(kp_id)


async def get_or_create_knowledge_card(
    db: Session, kp_id: str, user_id: str
) -> KnowledgeCardData:
    kp, _chapter, _material = _owned_kp(db, kp_id, user_id)
    point = SQLiteKnowledgePointProvider(db.get_bind()).get(kp_id)
    if point is None:
        raise HTTPException(status_code=409, detail="知识点内容尚未准备完成")
    source_digest = _digest(kp, point.source_chunks)
    card = db.exec(select(KnowledgeCard).where(KnowledgeCard.kp_id == kp_id)).first()
    settings = get_settings()
    enhancement_enabled = settings.llm_provider == "deepseek" and settings.deepseek_configured

    if card is None or card.source_digest != source_digest:
        content = _fallback_content(
            point,
            generation_status="generating" if enhancement_enabled else "ready",
        )
        now = datetime.now(timezone.utc)
        if card is None:
            card = KnowledgeCard(
                id=f"card-{uuid4().hex[:12]}", kp_id=kp_id,
                content_json=content.model_dump_json(), source_digest=source_digest,
            )
        else:
            card.content_json = content.model_dump_json()
            card.source_digest = source_digest
            card.version += 1
            card.updated_at = now
        db.add(card)
        db.commit()
        db.refresh(card)
    content = KnowledgeCardContent.model_validate_json(card.content_json)
    if content.generation_status == "failed" and enhancement_enabled:
        content.generation_status = "generating"
        card.content_json = content.model_dump_json()
        card.updated_at = datetime.now(timezone.utc)
        db.add(card)
        db.commit()
        db.refresh(card)
    learned = db.exec(select(DiagnosticReport.id).where(
        DiagnosticReport.user_id == user_id,
        DiagnosticReport.kp_id == kp_id,
    )).first() is not None
    favorite = db.exec(select(KnowledgeCardFavorite).where(
        KnowledgeCardFavorite.user_id == user_id,
        KnowledgeCardFavorite.card_id == card.id,
    )).first()
    sources = [
        KnowledgeCardSource(
            chunk_id=item.chunk_id,
            page=item.page_no,
            excerpt=item.text.strip()[:180],
        )
        for item in point.source_chunks
    ]
    return KnowledgeCardData(
        card_id=card.id,
        kp_id=kp.id,
        name=kp.name,
        summary=kp.summary or "暂无摘要",
        learning_status="learned" if learned else "unlearned",
        version=card.version,
        generation_status=content.generation_status,
        is_favorited=favorite is not None,
        favorite_id=favorite.id if favorite else None,
        coverage_level=content.coverage_level,
        coverage_notice=content.coverage_notice,
        estimated_minutes=content.estimated_minutes,
        sections=content.sections,
        sources=sources,
        updated_at=card.updated_at,
    )
