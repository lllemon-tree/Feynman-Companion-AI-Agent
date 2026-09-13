"""One source of truth for diagnostic mastery and spaced review rules."""

from datetime import datetime, timedelta


MASTERY_SCORE = 7
SRS_INTERVAL_DAYS = (1, 3, 7, 14, 30)


def is_mastered(score: int) -> bool:
    return score >= MASTERY_SCORE


def severity_for_score(score: int) -> int:
    if score <= 3:
        return 5
    if score <= 5:
        return 4
    return 3 if score < MASTERY_SCORE else 1


def next_review_at(review_count: int, completed_at: datetime) -> datetime:
    index = min(max(review_count, 1) - 1, len(SRS_INTERVAL_DAYS) - 1)
    return completed_at + timedelta(days=SRS_INTERVAL_DAYS[index])
