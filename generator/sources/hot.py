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
        log(f"  热榜 {route}：{len(data)} 条")
        return [f"{d.get('title', '').strip()}（热度 {d['hot']}）" if d.get("hot") else d.get("title", "").strip()
                for d in data if d.get("title")]
    except Exception as e:
        log(f"  热榜 {route} 获取失败：{e}")
        return []


def douyin_hot(ctx):
    if ctx.dry:
        return ["示例热搜 A（热度 1000 万）", "示例热搜 B"]
    return _titles(ctx, "douyin")[:50]


# 网易云的“抖音排行榜”2026 年 6 月后不再更新，改用网络热歌榜（每周五更新，多是短视频带火的歌）和飙升榜（每天更新）
NETEASE_CHARTS = {6723173524: "网易云网络热歌榜", 19723756: "网易云飙升榜"}


def douyin_music(ctx):
    """返回 ['歌名 / 歌手（榜单名）']。"""
    if ctx.dry:
        return ["示例热歌 / 示例歌手（网易云网络热歌榜）"]
    out = []
    for pid, chart in NETEASE_CHARTS.items():
        try:
            j = ctx.http.get("https://music.163.com/api/playlist/detail", params={"id": pid}, timeout=20,
                             headers={"Referer": "https://music.163.com/"}).json()
            tracks = (j.get("result") or j.get("playlist") or {}).get("tracks") or []
            log(f"  {chart}：{len(tracks)} 首")
            out += [f"{t['name']} / {'、'.join(a['name'] for a in t.get('artists') or t.get('ar') or [])}（{chart}）"
                    for t in tracks[:30]]
        except Exception as e:
            log(f"  {chart} 获取失败：{e}")
    return out
