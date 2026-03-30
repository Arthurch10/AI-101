"""微博数据抓取模块 - 支持移动端 API 和网页解析两种方式"""

import re
import time
import json
import random
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from . import database as db


# 微博移动端 API 基础 URL
MOBILE_API = "https://m.weibo.cn/api/container/getIndex"
MOBILE_DETAIL = "https://m.weibo.cn/statuses/show"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148 MicroMessenger/8.0.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://m.weibo.cn/",
}


class WeiboScraper:
    """微博数据采集器"""

    def __init__(self, cookie=""):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if cookie:
            self.session.headers["Cookie"] = cookie
        self._request_count = 0

    def _rate_limit(self):
        """简易限速，避免触发反爬"""
        self._request_count += 1
        if self._request_count % 5 == 0:
            time.sleep(random.uniform(3, 6))
        else:
            time.sleep(random.uniform(1, 2.5))

    def _get_json(self, url, params=None):
        self._rate_limit()
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"[请求失败] {url} - {e}")
            return None

    # ------------------------------------------------------------------
    # 博主信息
    # ------------------------------------------------------------------

    def fetch_blogger_info(self, uid):
        """获取博主基本资料"""
        params = {"type": "uid", "value": uid}
        data = self._get_json(MOBILE_API, params)
        if not data or data.get("ok") != 1:
            return None

        info = data.get("data", {}).get("userInfo", {})
        return {
            "uid": str(info.get("id", uid)),
            "screen_name": info.get("screen_name", ""),
            "description": info.get("description", ""),
            "followers_count": info.get("followers_count", 0),
            "statuses_count": info.get("statuses_count", 0),
            "verified": info.get("verified", False),
            "verified_reason": info.get("verified_reason", ""),
        }

    def search_bloggers(self, keyword, page=1):
        """搜索财经相关博主"""
        params = {
            "containerid": f"100103type=3&q={keyword}&t=0",
            "page_type": "searchall",
            "page": page,
        }
        data = self._get_json(MOBILE_API, params)
        if not data or data.get("ok") != 1:
            return []

        bloggers = []
        for card_group in data.get("data", {}).get("cards", []):
            if isinstance(card_group, dict) and card_group.get("card_group"):
                for card in card_group["card_group"]:
                    user = card.get("user")
                    if user:
                        bloggers.append({
                            "uid": str(user["id"]),
                            "screen_name": user.get("screen_name", ""),
                            "description": user.get("description", ""),
                            "followers_count": user.get("followers_count", 0),
                            "verified": user.get("verified", False),
                            "verified_reason": user.get("verified_reason", ""),
                        })
        return bloggers

    # ------------------------------------------------------------------
    # 帖子抓取
    # ------------------------------------------------------------------

    def _get_containerid(self, uid):
        """获取用户微博列表的 containerid"""
        params = {"type": "uid", "value": uid}
        data = self._get_json(MOBILE_API, params)
        if not data or data.get("ok") != 1:
            return None

        tabs = data.get("data", {}).get("tabsInfo", {}).get("tabs", [])
        for tab in tabs:
            if tab.get("tab_type") == "weibo":
                return tab.get("containerid")
        return f"107603{uid}"

    def fetch_posts(self, uid, pages=3):
        """抓取指定博主的最近微博"""
        containerid = self._get_containerid(uid)
        if not containerid:
            return []

        all_posts = []
        for page in range(1, pages + 1):
            params = {"type": "uid", "value": uid,
                      "containerid": containerid, "page": page}
            data = self._get_json(MOBILE_API, params)
            if not data or data.get("ok") != 1:
                break

            cards = data.get("data", {}).get("cards", [])
            for card in cards:
                if card.get("card_type") != 9:
                    continue
                mblog = card.get("mblog", {})
                if not mblog:
                    continue

                text = _clean_html(mblog.get("text", ""))
                if not text:
                    continue

                # 提取话题标签
                topics = re.findall(r"#(.+?)#", mblog.get("text", ""))

                post = {
                    "post_id": str(mblog.get("id", "")),
                    "blogger_uid": uid,
                    "content": text,
                    "created_at": _parse_weibo_time(mblog.get("created_at", "")),
                    "reposts_count": mblog.get("reposts_count", 0),
                    "comments_count": mblog.get("comments_count", 0),
                    "attitudes_count": mblog.get("attitudes_count", 0),
                    "topics": ",".join(topics),
                }
                all_posts.append(post)

        return all_posts

    def fetch_and_save(self, uid, pages=3):
        """抓取并存储博主微博"""
        posts = self.fetch_posts(uid, pages)
        if posts:
            db.save_posts(posts)
        return len(posts)

    def fetch_all_bloggers_posts(self, pages=3):
        """抓取所有已添加博主的最新微博"""
        bloggers = db.get_all_bloggers()
        results = {}
        for blogger in bloggers:
            uid = blogger["uid"]
            count = self.fetch_and_save(uid, pages)
            results[blogger["screen_name"]] = count
            print(f"  [{blogger['screen_name']}] 获取 {count} 条微博")
        return results


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _clean_html(html_text):
    """清理微博 HTML 标签，保留纯文本"""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "lxml")
    return soup.get_text(strip=True)


def _parse_weibo_time(time_str):
    """解析微博的时间格式为 ISO 格式"""
    if not time_str:
        return ""
    now = datetime.now()

    if "刚刚" in time_str:
        return now.strftime("%Y-%m-%d %H:%M:%S")
    if "分钟前" in time_str:
        minutes = int(re.search(r"(\d+)", time_str).group(1))
        dt = now - timedelta(minutes=minutes)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if "小时前" in time_str:
        hours = int(re.search(r"(\d+)", time_str).group(1))
        dt = now - timedelta(hours=hours)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if "昨天" in time_str:
        dt = now - timedelta(days=1)
        return dt.strftime("%Y-%m-%d") + " " + time_str.replace("昨天 ", "")

    # 标准格式尝试
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%d %H:%M:%S",
                "%m-%d", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return time_str
