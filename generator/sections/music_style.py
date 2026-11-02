"""🎼 每天 1 种音乐风格 + 1 首代表曲 + 1 种乐器。风格和乐器从列表里随机，避开最近用过的。"""
from common import BASE_SYSTEM, GEN, load_json, make_item, search_link
from sources.images import pick_images, wikimedia_images
from sources.museum import random_object

ID, NAME, EMOJI = "music_style", "音乐风格和乐器", "🎼"
DAYS = range(7)
AVOID_RECENT = 30

TASK = """今天的音乐风格是：{style}（{style_en}）；今天的乐器是：{inst}（{inst_en}）。
读者不懂乐理，想听懂音乐。请用听得见的描述（“鼓点像……”“听到……的声音就是它”），少用术语，用到就解释。

1. 风格的 analysis 写这几项：「一句话认出它」「起源」「节奏」（速度大概多少 BPM、律动感觉、鼓怎么打）「乐器构成」「和声和旋律」「制作特点」。
2. 推荐 1 首这个风格的代表曲（必须是非常有名、你确定真实存在的作品），说清楚听的时候注意什么乐器或段落。不要写具体的几分几秒，你没法确认时间点。
3. 乐器的 analysis 写这几项：「音色」「怎么发声」「常出现在哪些风格」。不要列具体的歌名或曲目，你很难确认某首歌里有没有这件乐器。
输出 JSON：{{"style": {{"summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["2–4 个"]}},
"song": {{"title": "歌名", "artist": "歌手", "listen_for": "听的时候注意什么"}},
"instrument": {{"summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["2–4 个"]}}}}"""


def _choose(ctx, items, key):
    recent = ctx.state.setdefault(key, [])
    pool = [i for i in items if i["en"] not in recent] or items
    choice = ctx.rng.choice(pool)
    recent.append(choice["en"])
    del recent[:-AVOID_RECENT]
    return choice


def run(ctx):
    style = _choose(ctx, load_json(GEN / "catalog" / "music_styles.json", []), "recent_music_styles")
    inst = _choose(ctx, load_json(GEN / "catalog" / "instruments.json", []), "recent_instruments")
    out = ctx.llm.json(BASE_SYSTEM, TASK.format(style=style["zh"], style_en=style["en"],
                                               inst=inst["zh"], inst_en=inst["en"]), fake={
        "style": {"summary": "dry-run 示例。", "analysis": [{"label": "节奏", "text": "示例。"}], "tags": ["示例"]},
        "song": {"title": "示例曲", "artist": "示例歌手", "listen_for": "示例。"},
        "instrument": {"summary": "示例。", "analysis": [{"label": "音色", "text": "示例。"}], "tags": ["示例"]}})
    so, song, io = out.get("style") or {}, out.get("song") or {}, out.get("instrument") or {}

    analysis = list(so.get("analysis") or [])
    links = []
    if song.get("title"):
        kw = f"{song['title']} {song.get('artist', '')}".strip()
        analysis.append({"label": f"代表曲：{song['title']} - {song.get('artist', '')}",
                         "text": song.get("listen_for", "")})
        links = [search_link("qqmusic", kw), search_link("netease", kw), search_link("bilibili", kw)]
    style_item = make_item(title=f"{style['zh']} {style['en']}", subtitle="音乐风格", summary=so.get("summary", ""),
                           analysis=analysis, links=links, tags=so.get("tags", []))

    cands = wikimedia_images(ctx, f"{inst['en']} musical instrument")
    met = random_object(ctx, "instrument", inst["en"])
    if met:
        cands.append({"url": met["primaryImageSmall"], "page": met.get("objectURL", ""),
                      "credit": "The Met · Public Domain"})
    images = pick_images(ctx, cands, f"乐器「{inst['zh']}（{inst['en']}）」的照片", want=2, name_hint="inst")
    inst_item = make_item(title=f"{inst['zh']} {inst['en']}", subtitle="乐器", summary=io.get("summary", ""),
                          analysis=io.get("analysis"), images=images, tags=io.get("tags", []),
                          links=[search_link("bilibili", f"{inst['zh']} 演奏"),
                                 search_link("youtube", f"{inst['en']} performance")])
    return [style_item, inst_item]
