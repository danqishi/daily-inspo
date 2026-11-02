"""🎵 抖音热门音乐：周一到周五每天 2 首（每周 10 首），带台词的也可以。"""
from common import BASE_SYSTEM, grounded, log, make_item, search_link
from sources.hot import douyin_music

ID, NAME, EMOJI = "hot_music", "抖音热门音乐", "🎵"
DAYS = range(5)

QUERIES = ["抖音 热歌 本周 热门 BGM", "抖音 最火的歌 最近 爆火 神曲", "抖音 热门 BGM 台词 音频 最近"]

TASK = """今天要推荐 2 首最近在抖音上比较火的音乐（歌曲、BGM，带台词的音频也可以）。
**歌名必须原样出现在下面的热歌榜或搜索结果里**，不能自己编，不能凭记忆写老歌。这些推过了，不要重复：{seen}

热歌榜（网易云的网络热歌榜和飙升榜，多是短视频带火的歌；搜索结果里在抖音火的优先）：
{chart}

搜索结果（都是最近一周的）：
{results}

按热度从高到低给出最多 4 首候选，每首都完整写好。analysis 必须是这三项：「为什么火」「常配什么视频」「听点」（最抓耳的地方：副歌、某句台词、节奏等）。资料里没有的细节不要编。
song 只写歌名本身（不要带歌手、“抖音版”“DJ版”这类后缀）。
输出 JSON：{{"items": [{{"song": "歌名（和资料里写法一致）", "artist": "歌手（台词音频就写出处；不知道就留空）", "summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["2–4 个标签"]}}]}}"""


def run(ctx):
    chart = douyin_music(ctx)
    res = ctx.search(ctx.rotate(QUERIES), time_range="week", max_results=10)["results"]
    if not chart and not res:
        raise RuntimeError("热歌榜和搜索都没拿到数据")
    seen = ctx.seen(ID)
    texts = chart + [f"{r['title']} {r.get('content') or ''}" for r in res]
    out = ctx.llm.json(BASE_SYSTEM, TASK.format(
        seen="、".join(seen[-80:]) or "（暂无）",
        chart="\n".join(f"- {t}" for t in chart) or "（今天没拿到热歌榜）",
        results="\n".join(f"- {r['title']}：{(r.get('content') or '')[:400]}" for r in res),
    ), fake={"items": [{"song": "示例热歌", "artist": "示例歌手", "summary": "示例。",
                        "analysis": [{"label": "为什么火", "text": "示例。"}], "tags": ["示例"]}]})
    items = []
    for o in out.get("items") or []:
        if len(items) >= 2:
            break
        song = (o.get("song") or "").strip("《》 ")
        if not song or song in seen:
            continue
        if not grounded(song, texts):
            log(f"  《{song}》在资料里找不到，可能是编的，跳过")
            continue
        ctx.mark_seen(ID, song)
        kw = f"{song} {o.get('artist', '')}".strip()
        items.append(make_item(
            title=song, subtitle=o.get("artist", ""), summary=o.get("summary", ""), analysis=o.get("analysis"),
            links=[search_link("qqmusic", kw), search_link("netease", kw), search_link("douyin", song)],
            tags=o.get("tags", [])))
    if not items:
        raise RuntimeError("没有找到资料里确实存在的新歌")
    return items
