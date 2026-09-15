import re
from difflib import SequenceMatcher
from typing import Sequence

from backend.app.models.feynman import FeynmanChatData, NextAction


_OPTIONAL_ENRICHMENT_PATTERNS = (
    "未举反例",
    "未举出反例",
    "未提供反例",
    "未进行反例",
    "未做反例",
    "未迁移应用",
    "未进行迁移",
    "未举出迁移",
    "未使用分点",
    "未分点",
    "未使用小标题",
    "未提供代码",
    "未给出代码",
    "未写代码",
)

_ABSENCE_PREFIX = re.compile(
    r"^(?:未|没有)(?:能够|能|清楚|明确|具体|完整)?"
    r"(?:提到|提及|说明|涉及|包含|覆盖|讲到)"
)


def sanitize_report_against_user_text(
    response: FeynmanChatData,
    user_texts: Sequence[str],
) -> FeynmanChatData:
    """Remove report deductions that contradict the learner's own words.

    LLM prompts are not a sufficient integrity boundary for a scored report. This
    post-processing layer only handles high-confidence cases: claims that a topic
    was never mentioned when it appears in the transcript, and optional enrichment
    forms (counterexamples, headings, code) presented as mandatory omissions.
    """
    if (
        response.next_action != NextAction.GENERATE_REPORT
        or response.final_report is None
        or response.card_preview is None
    ):
        return response

    combined_user_text = _normalize("\n".join(user_texts))
    removed_any = False
    for dimension in response.final_report.dimensions:
        kept_gaps: list[str] = []
        removed_gaps: list[str] = []
        for gap in dimension.gaps:
            sanitized_gap = _sanitize_gap(gap, combined_user_text)
            if sanitized_gap is None:
                removed_gaps.append(gap)
            else:
                kept_gaps.append(sanitized_gap)
                if sanitized_gap != gap:
                    removed_gaps.append(gap)

        if not removed_gaps:
            if kept_gaps and all(_is_minor_extension(gap) for gap in kept_gaps):
                removed_any = True
                dimension.score = max(dimension.score, 9)
                dimension.analysis = (
                    "用户已经完成该维度的核心要求；"
                    f"{kept_gaps[0].rstrip('。')}属于进一步深化，不构成基础理解错误。"
                )
                dimension.suggestion = (
                    f"可选拓展：{_positive_focus(kept_gaps[0])}；"
                    "它用于冲击满分，不是本轮必答项。"
                )
            continue
        removed_any = True
        dimension.gaps = kept_gaps
        if kept_gaps:
            if all(_is_minor_extension(gap) for gap in kept_gaps):
                dimension.score = max(dimension.score, 9)
                dimension.analysis = (
                    "用户已经完成该维度的核心要求；"
                    f"{kept_gaps[0].rstrip('。')}属于进一步深化，不构成基础理解错误。"
                )
                dimension.suggestion = (
                    f"可选拓展：{_positive_focus(kept_gaps[0])}；"
                    "它用于冲击满分，不是本轮必答项。"
                )
            else:
                dimension.analysis = (
                    "用户已经覆盖了该维度的主要要求；当前仍可补充："
                    f"{kept_gaps[0].rstrip('。')}。"
                )
                dimension.suggestion = _action_for_gap(kept_gaps[0])
        else:
            dimension.score = max(dimension.score, 9)
            dimension.analysis = _strong_dimension_analysis(dimension.name)
            dimension.suggestion = _strong_dimension_suggestion(dimension.name)

    if not removed_any:
        return response

    remaining_gaps = [
        gap
        for dimension in response.final_report.dimensions
        for gap in dimension.gaps
    ]
    response.card_preview.total_score = sum(
        dimension.score for dimension in response.final_report.dimensions
    )
    if remaining_gaps:
        focus = _positive_focus(remaining_gaps[0])
        response.card_preview.summary = f"核心已掌握，可补充{focus}"[:30]
        response.final_report.overall_comment = (
            "你已经覆盖了核心定义、机制和本轮验证内容。报告已排除与"
            "用户原话冲突或不属于必答项的扣分；当前主要可补强的是："
            f"{focus}。"
        )
    else:
        response.card_preview.summary = "核心理解完整，暂无明显盲区"
        response.final_report.overall_comment = (
            "你已经覆盖了本轮要求的核心内容，并完成了有效的理解验证。"
            "目前没有发现明确错误或关键遗漏；反例、代码和更多迁移场景"
            "可以作为后续拓展，但不应影响本轮基础讲解得分。"
        )
    return response


def _is_optional_enrichment(gap: str) -> bool:
    compact = _normalize(gap)
    return any(_normalize(pattern) in compact for pattern in _OPTIONAL_ENRICHMENT_PATTERNS)


def _is_minor_extension(gap: str) -> bool:
    compact = _normalize(gap)
    prefixes = ("未进一步解释", "尚未进一步解释", "未展开", "尚未展开", "可补充")
    return any(compact.startswith(_normalize(prefix)) for prefix in prefixes)


def _sanitize_gap(gap: str, normalized_user_text: str) -> str | None:
    if _is_optional_enrichment(gap):
        return None
    stripped_gap = gap.strip()
    match = _ABSENCE_PREFIX.match(stripped_gap)
    if match is None:
        return gap
    claimed_missing = stripped_gap[match.end():]
    pieces = [
        piece.strip("：:，,。；; ")
        for piece in re.split(r"、|，|,|；|;|以及|或者|或|和|并且|同时", claimed_missing)
        if piece.strip("：:，,。；; ")
    ]
    remaining = [
        piece for piece in pieces
        if not _already_mentioned(_normalize(piece), normalized_user_text)
    ]
    if not remaining:
        return None
    if len(remaining) == len(pieces):
        return gap
    return f"未提到{'、'.join(remaining)}"


def _already_mentioned(claim: str, normalized_user_text: str) -> bool:
    cleaned = claim
    for filler in ("这一关键点", "这一点", "相关内容", "封装还", "封装还能", "还", "也"):
        cleaned = cleaned.replace(filler, "")
    if len(cleaned) < 4:
        return False
    if cleaned in normalized_user_text:
        return True
    longest = SequenceMatcher(None, cleaned, normalized_user_text).find_longest_match()
    return longest.size >= 4 and longest.size / len(cleaned) >= 0.5


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text).replace("了", "")


def _positive_focus(gap: str) -> str:
    focus = re.sub(
        r"^(?:未|没有)(?:能够|能|清楚|明确|具体|完整|进一步)?"
        r"(?:提到|提及|说明|解释|展开|论证|涉及|包含|覆盖|讲到)?",
        "",
        gap,
    )
    return focus.strip("：:，,。；; ") or "一个关键原因"


def _action_for_gap(gap: str) -> str:
    focus = _positive_focus(gap)
    return f"围绕“{focus}”补充一句因果解释，并检查它是否能由具体场景验证。"


def _strong_dimension_analysis(name: str) -> str:
    analyses = {
        "理解深度": "用户已准确说明核心概念和机制，并用具体情境完成了一次有效验证。",
        "表达完整性": "用户已覆盖本题必要信息，表述足以让不了解该概念的听众把握重点。",
        "逻辑连贯性": "用户能把做法、原因和结果连接起来，当前推理链没有明显断点。",
        "结构化能力": "用户按定义、机制和作用组织短讲解，层次清楚，无需为了形式强行分点。",
    }
    return analyses.get(
        name,
        "用户原话已经覆盖该维度的核心要求，没有发现足以继续扣分的明确错误。",
    )


def _strong_dimension_suggestion(name: str) -> str:
    suggestions = {
        "理解深度": "保持用具体场景验证概念；需要深入时再增加一个边界情况。",
        "表达完整性": "保持先讲核心再补例子的表达顺序，不必穷举所有教材细节。",
        "逻辑连贯性": "保持说明“怎样做—为什么—带来什么结果”的因果链。",
        "结构化能力": "短回答保持当前顺序即可；长讲解时再考虑分点。",
    }
    return suggestions.get(name, "保持当前讲解方式，后续按需要做迁移练习。")
