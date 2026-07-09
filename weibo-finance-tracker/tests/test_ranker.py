"""博主排名测试"""

from src import database as db
from src.ranker import BloggerRanker, WEIGHTS


def _add(uid, name, followers=100000, manual=False):
    db.add_blogger(uid=uid, screen_name=name, followers_count=followers,
                   verified=True, manual_selected=manual)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_scores_in_range():
    _add("1", "A")
    ranker = BloggerRanker()
    r = ranker.rank_blogger(db.get_blogger("1"))
    for key in ("score", "accuracy_score", "influence_score",
                "activity_score", "consistency_score"):
        assert 0.0 <= r[key] <= 1.0


def test_rank_all_sorted_desc():
    _add("1", "A", followers=100)
    _add("2", "B", followers=5000000)
    ranker = BloggerRanker()
    rankings = ranker.rank_all()
    scores = [r["score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


def test_accuracy_uses_backtest_when_enough_samples():
    _add("1", "A")
    db.save_backtest("1", accuracy=0.9, evaluated=10, correct=9)
    ranker = BloggerRanker()
    assert ranker.compute_accuracy_score(db.get_blogger("1")) == 0.9


def test_accuracy_falls_back_when_few_samples():
    _add("1", "A")
    db.save_backtest("1", accuracy=0.9, evaluated=2, correct=2)  # <3 样本
    ranker = BloggerRanker()
    # 无观点 → 回退默认 0.5，而非回测的 0.9
    assert ranker.compute_accuracy_score(db.get_blogger("1")) == 0.5


def test_top3_manual_first():
    _add("1", "手动", manual=True)
    _add("2", "算法B", followers=9000000)
    _add("3", "算法C", followers=8000000)
    _add("4", "算法D", followers=7000000)
    ranker = BloggerRanker()
    top3 = ranker.get_selected_top3()
    assert len(top3) == 3
    # 手动优选的博主必须在结果中
    assert any(r["blogger_uid"] == "1" for r in top3)
