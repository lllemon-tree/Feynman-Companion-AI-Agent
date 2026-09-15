from backend.app.services.feynman_service import build_study_greeting


def test_comparison_topic_has_natural_greeting():
    greeting = build_study_greeting("Git 和 GitHub 的区别")
    assert "比较它们" in greeting
    assert "区别的核心原理" not in greeting


def test_general_topic_asks_for_current_understanding():
    greeting = build_study_greeting("Dijkstra 算法")
    assert "你目前怎么理解它" in greeting
    assert "讲得越详细越好" not in greeting
