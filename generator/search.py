"""Tavily 搜索。每天限制调用次数，免费额度是每月 1000 次。"""
import os

from common import log

TAVILY_URL = "https://api.tavily.com/search"


class Search:
    def __init__(self, http, dry=False, daily_limit=25):
        self.http = http
        self.dry = dry
        self.daily_limit = daily_limit
        self.used = 0
        self.cache = {}
        self.key = os.environ.get("TAVILY_API_KEY")
        if not dry and not self.key:
            raise RuntimeError("缺少环境变量 TAVILY_API_KEY")

    def __call__(self, query, *, topic="general", time_range=None, domains=None,
                 max_results=10, images=False):
        if self.dry:
            return _fake(query, max_results, images)
        cache_key = (query, topic, time_range, tuple(domains or ()), max_results, images)
        if cache_key in self.cache:  # 栏目失败重试时不重复花搜索次数
            return self.cache[cache_key]
        if self.used >= self.daily_limit:
            log(f"  今天的搜索次数已用完（{self.daily_limit}），跳过：{query}")
            return {"results": [], "images": []}
        body = {"query": query, "topic": topic, "max_results": max_results, "search_depth": "basic"}
        if time_range:
            body["time_range"] = time_range
        if domains:
            body["include_domains"] = domains
        if images:
            body["include_images"] = True
            body["include_image_descriptions"] = True
        self.used += 1
        log(f"  搜索 #{self.used}：{query}")
        r = self.http.post(TAVILY_URL, json=body, timeout=60,
                           headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        data = r.json()
        imgs = [i if isinstance(i, dict) else {"url": i, "description": ""} for i in data.get("images") or []]
        self.cache[cache_key] = {"results": data.get("results") or [], "images": imgs}
        return self.cache[cache_key]


def _fake(query, n, images):
    results = [{
        "title": f"【示例】{query} 第 {i + 1} 条",
        "url": f"https://www.bilibili.com/video/BV1xx411c7m{i}",
        "content": "这是 dry-run 模式下的假搜索结果，用来检查页面效果。",
    } for i in range(min(n, 5))]
    imgs = [{"url": "https://images.metmuseum.org/CRDImages/ep/web-large/DP-42549-001.jpg",
             "description": "示例图片"}] if images else []
    return {"results": results, "images": imgs}
