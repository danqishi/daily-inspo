"""抖音热榜、热歌榜：来自 GitHub Actions 里临时启动的 DailyHotApi（imsyy/DailyHotApi）。
拿不到就返回空列表，由栏目自己退回用搜索。"""
import os

from common import log

HOT_API = os.environ.get("HOT_API_BASE", "http://localhost:6688")


def _titles(ctx, route):
    try:
        r = ctx.http.get(f"{HOT_API}/{route}", timeout=30)
        r.raise_for_status()
        data = r.json().get("data") or []
        return [f"{d.get('title', '').strip()}（热度 {d['hot']}）" if d.get("hot") else d.get("title", "").strip()
                for d in data if d.get("title")]
    except Exception as e:
        log(f"  热榜 {route} 获取失败：{e}")
        return []


def douyin_hot(ctx):
    if ctx.dry:
        return ["示例热搜 A（热度 1000 万）", "示例热搜 B"]
    return _titles(ctx, "douyin")[:50]


def douyin_music(ctx):
    if ctx.dry:
        return ["示例热歌 - 示例歌手"]
    for route in ("douyin_music", "douyin-music"):
        titles = _titles(ctx, route)
        if titles:
            return titles[:50]
    return []
