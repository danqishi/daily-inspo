"""🎵 抖音热门音乐：周一到周五每天 2 首（每周 10 首），带台词的也可以。"""
from common import BASE_SYSTEM, make_item, search_link
from sources.hot import douyin_music

ID, NAME, EMOJI = "hot_music", "抖音热门音乐", "🎵"
DAYS = range(5)

QUERIES = ["抖音 热歌 本周 热门 BGM", "抖音 最火的歌 最近 爆火 神曲", "抖音 热门 BGM 台词 音频 最近"]

TASK = """今天要推荐 2 首最近在抖音上比较火的音乐（歌曲、BGM，带台词的音频也可以）。
**必须是真的火的**，依据是下面的热歌榜和搜索结果。这些推过了，不要重复：{seen}

抖音热歌榜：
{chart}

搜索结果：
{results}

每首的 analysis 写这几项：「为什么火」「常配什么视频」「听点」（这首歌最抓耳的地方：副歌、某句台词、节奏等）。
输出 JSON：{{"items": [{{"song": "歌名", "artist": "歌手（台词音频就写出处）", "summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["2–4 个标签"]}}]}}"""


def run(ctx):
    chart = douyin_music(ctx)
    res = ctx.search(ctx.rotate(QUERIES), time_range="week", max_results=8)["results"]
    if not chart and not res:
        raise RuntimeError("热歌榜和搜索都没拿到数据")
    seen = ctx.seen(ID)
    out = ctx.llm.json(BASE_SYSTEM, TASK.format(
        seen="、".join(seen[-80:]) or "（暂无）",
        chart="\n".join(f"- {t}" for t in chart) or "（今天没拿到热歌榜）",
        results="\n".join(f"- {r['title']}：{(r.get('content') or '')[:300]}" for r in res),
    ), fake={"items": [{"song": "示例歌曲", "artist": "示例歌手", "summary": "示例。",
                        "analysis": [{"label": "为什么火", "text": "示例。"}], "tags": ["示例"]}] * 2})
    items = []
    for o in (out.get("items") or [])[:2]:
        song = (o.get("song") or "").strip()
        if not song or song in seen:
            continue
        ctx.mark_seen(ID, song)
        kw = f"{song} {o.get('artist', '')}".strip()
        items.append(make_item(
            title=song, subtitle=o.get("artist", ""), summary=o.get("summary", ""), analysis=o.get("analysis"),
            links=[search_link("qqmusic", kw), search_link("netease", kw), search_link("douyin", song)],
            tags=o.get("tags", [])))
    if not items:
        raise RuntimeError("模型没有选出新的歌")
    return items
