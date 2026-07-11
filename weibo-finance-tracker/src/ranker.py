"""博主排名算法模块 - 多维度评分与 TOP-N 筛选"""

import math
from datetime import datetime, timedelta

from . import database as db


# 各维度权重 (总和 = 1.0)
WEIGHTS = {
    "accuracy":    0.35,   # 观点准确率（历史验证）
    "influence":   0.25,   # 影响力（粉丝数、互动率）
    "activity":    0.20,   # 活跃度（发帖频率）
    "consistency": 0.20,   # 观点一致性（不频繁翻转）
}


class BloggerRanker:
    """博主多维度评分排名器"""

    def __init__(self):
        self.bloggers = db.get_all_bloggers()

    def compute_influence_score(self, blogger):
        """影响力评分: 综合粉丝数和互动率"""
        followers = blogger.get("followers_count", 0)
        # 对数缩放，避免大 V 过度碾压
        follower_score = min(math.log10(max(followers, 1)) / 7.0, 1.0)

        # 互动率: 近期帖子的平均（转发+评论+点赞）/ 粉丝数
        posts = db.get_posts(blogger["uid"], limit=20)
        if posts and followers > 0:
            total_engagement = sum(
                p["reposts_count"] + p["comments_count"] + p["attitudes_count"]
                for p in posts
            )
            avg_engagement = total_engagement / len(posts)
            engagement_rate = min(avg_engagement / max(followers, 1) * 100, 1.0)
        else:
            engagement_rate = 0.0

        verified_bonus = 0.1 if blogger.get("verified") else 0.0

        return min(follower_score * 0.5 + engagement_rate * 0.4 + verified_bonus, 1.0)

    def compute_activity_score(self, blogger):
        """活跃度评分: 近 30 天发帖频率"""
        posts = db.get_posts(blogger["uid"], limit=200)
        if not posts:
            return 0.0

        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        recent_posts = [p for p in posts if p.get("created_at", "") >= cutoff]
        count = len(recent_posts)

        # 理想频率: 每天 1-3 条 → 30-90 条/月 满分
        if count >= 30:
            return min(count / 90.0, 1.0)
        return count / 30.0

    def compute_consistency_score(self, blogger):
        """观点一致性评分: 分析情感变化幅度"""
        opinions = db.get_opinions(blogger["uid"], limit=50)
        if len(opinions) < 3:
            return 0.5  # 数据不足给中间分

        sentiments = [o["sentiment"] for o in opinions if o["sentiment"] is not None]
        if len(sentiments) < 3:
            return 0.5

        # 计算相邻观点的情感波动
        changes = []
        for i in range(1, len(sentiments)):
            changes.append(abs(sentiments[i] - sentiments[i - 1]))

        avg_change = sum(changes) / len(changes)
        # 波动越小分数越高 (avg_change 范围 0~2, 映射到 1~0)
        return max(1.0 - avg_change / 2.0, 0.0)

    def compute_accuracy_score(self, blogger):
        """
        观点准确率评分

        优先使用真实行情回测结果 (wft backtest)；
        无回测数据时回退到观点置信度代理指标。
        """
        bt = db.get_backtest(blogger["uid"])
        if bt and bt.get("accuracy") is not None and bt.get("evaluated", 0) >= 3:
            # 有足够样本的真实回测准确率
            return bt["accuracy"]

        opinions = db.get_opinions(blogger["uid"], limit=50)
        if not opinions:
            return 0.5

        # 回退: 使用分析时的 confidence 作为代理指标
        confidences = [o["confidence"] for o in opinions if o["confidence"]]
        if not confidences:
            return 0.5

        return sum(confidences) / len(confidences)

    def rank_blogger(self, blogger):
        """计算单个博主的综合评分"""
        scores = {
            "accuracy_score":    self.compute_accuracy_score(blogger),
            "influence_score":   self.compute_influence_score(blogger),
            "activity_score":    self.compute_activity_score(blogger),
            "consistency_score": self.compute_consistency_score(blogger),
        }

        total = (
            scores["accuracy_score"]    * WEIGHTS["accuracy"] +
            scores["influence_score"]   * WEIGHTS["influence"] +
            scores["activity_score"]    * WEIGHTS["activity"] +
            scores["consistency_score"] * WEIGHTS["consistency"]
        )

        return {
            "blogger_uid": blogger["uid"],
            "score": round(total, 4),
            **{k: round(v, 4) for k, v in scores.items()},
        }

    def rank_all(self):
        """对所有博主进行排名并存储"""
        rankings = []
        for blogger in self.bloggers:
            ranking = self.rank_blogger(blogger)
            rankings.append(ranking)
            db.save_ranking(ranking)

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings

    def get_top_n(self, n=10):
        """获取 TOP-N 博主"""
        rankings = self.rank_all()
        return rankings[:n]

    def get_selected_top3(self):
        """
        获取优选 TOP3 博主
        优先返回用户手动筛选的，不足则用算法排名补齐
        """
        manual = [b for b in self.bloggers if b.get("manual_selected")]
        if len(manual) >= 3:
            # 对手动筛选的也进行排名，返回前 3
            ranked = [self.rank_blogger(b) for b in manual]
            ranked.sort(key=lambda x: x["score"], reverse=True)
            return ranked[:3]

        # 手动筛选不足 3 个，用算法排名补齐
        all_ranked = self.rank_all()
        manual_uids = {b["uid"] for b in manual}
        manual_ranked = [r for r in all_ranked if r["blogger_uid"] in manual_uids]
        algo_ranked = [r for r in all_ranked if r["blogger_uid"] not in manual_uids]

        result = manual_ranked + algo_ranked
        return result[:3]
