"""🎨 设计风格栏目里的第二条：每天 1 张好看的海报或封面（电影海报、专辑封面、书籍封面……按日期轮换），
分析它的设计，以及属于什么设计风格。作品要在英文维基百科上查得到、类型对得上、有海报/封面图，避免模型编造。"""
from common import BASE_SYSTEM, log, make_item, search_link
from sections.film import _poster, _squash, _wiki

ATTEMPTS = 3

# 按日期轮换：类型、维基百科摘要里至少要出现的一个词
KINDS = [
    ("电影海报", ("film",)),
    ("专辑封面", ("album", "EP")),
    ("电影海报", ("film",)),
    ("书籍封面", ("novel", "book")),
    ("电影海报", ("film",)),
    ("专辑封面", ("album", "EP")),
    ("动画电影海报", ("film", "anime")),
]

TASK = """今天请推荐一张设计得特别好看的「{kind}」。要求：
- 海报或封面本身有很强的设计感或鲜明的风格（比如大胆的排版、标志性的插画、极简构图、某种设计运动的代表），出名的经典也可以；
- 作品要在英文维基百科上有条目，而且条目里的主图就是这张海报/封面（电影选当年原版海报，专辑选原版封面，书选初版或最经典的封面）；
- 不要选最近推荐过的：{recent}。
{retry_note}
输出 JSON：{{"title_zh": "中文名", "title_en": "英文维基百科上的条目名", "year": 年份数字, "creator": "导演/乐队/作者",
 "designer": "海报或封面的设计师（确定才写，否则空字符串）", "style": "它最接近的设计风格（中文 + 英文，比如 瑞士国际主义 Swiss Style）"}}"""

DESCRIBE = """请客观、具体地描述这张图，不做评价：
先判断它是不是一张海报、专辑封面或书籍封面（不是剧照、人物照片、网页截图）。
再描述：画面里有什么、各在什么位置，主要颜色和明暗，文字（写了什么、字体粗细、衬线还是无衬线、大小和摆放位置），
图形和留白，整体构图（对称、居中、对角线……），容易被忽略的小细节。
输出 JSON：{"is_cover": true 或 false, "description": "200–400 字的描述"}"""

ANALYZE = """今天赏析的{kind}：{title_zh}（{title_en}，{year}，{creator}）。{designer_note}
它可能属于的设计风格：{style}

维基百科上的介绍（事实以这里为准，没有的就不要写具体事实）：
{extract}

{see_note}

读者没有设计基础，想提升审美，并且想把方法用到自己的视频封面、海报或 AI 生图上。
analysis 写这几项：「第一眼看哪里」「构图」「色彩」「字体和排版」「设计风格」（属于什么风格、这张图哪些地方体现了它、这种风格一般有什么特点）
「为什么好看」「可以学到什么」（做封面、海报时能直接用的方法）。每项 2–3 句，要具体到这张图，不要写套话。
另外给一段模仿这种设计风格的 AI 生图英文提示词（只模仿风格，不要照搬作品名和人物）。
输出 JSON：{{"summary": "一句话", "style_name": "设计风格的简短中文名", "analysis": [{{"label": "…", "text": "…"}}], "prompt": "英文提示词", "tags": ["3–5 个标签"]}}"""


def _wiki_work(ctx, title_en, year, words):
    """在英文维基百科找这部作品，类型要对得上、要有主图。返回 {title, url, extract, image} 或 None。"""
    r = _wiki(ctx, "/w/api.php", {"action": "query", "list": "search", "format": "json", "srlimit": 5,
                                   "srsearch": f"{title_en} {year}"})
    for hit in (r.get("query") or {}).get("search", []):
        if _squash(title_en)[:6] not in _squash(hit["title"]):
            continue
        s = _wiki(ctx, f"/api/rest_v1/page/summary/{hit['title'].replace(' ', '_')}")
        extract = s.get("extract", "")
        image = (s.get("originalimage") or {}).get("source", "")
        if image and any(w.lower() in extract.lower() for w in words):
            return {"title": hit["title"], "url": (s.get("content_urls") or {}).get("desktop", {}).get("page", ""),
                    "extract": extract, "image": image}
    return None


def run(ctx):
    if ctx.dry:
        return [make_item(title="《示例海报》", subtitle="每日海报 · 电影海报", summary="dry-run 示例。")]
    kind, words = ctx.rotate(KINDS)
    recent = ctx.seen("posters")
    notes = []
    for _ in range(ATTEMPTS):
        w = ctx.llm.json(BASE_SYSTEM, TASK.format(
            kind=kind, recent="、".join(recent[-80:]) or "无",
            retry_note=("注意：" + "；".join(notes) + "。请换一个。\n") if notes else ""))
        name = w.get("title_en", "")
        if _squash(w.get("title_zh", "")) in {_squash(x) for x in recent}:
            notes.append(f"《{w.get('title_zh')}》最近推荐过了")
            continue
        wiki = _wiki_work(ctx, name, w.get("year", ""), words)
        if not wiki:
            notes.append(f"《{w.get('title_zh')}》({name}) 在维基百科上没查到、类型不对或没有海报图")
            log(f"  海报没核实到：{name}")
            continue
        src = _poster(ctx, wiki["image"], name_hint="poster")
        if not src:
            notes.append(f"《{w.get('title_zh')}》的图片下载失败")
            continue
        seen_desc = ""
        if ctx.llm.can_see:
            try:
                d = ctx.llm.json(BASE_SYSTEM, DESCRIBE, image=(ctx.site / src).read_bytes())
                if d.get("is_cover") is False:
                    (ctx.site / src).unlink(missing_ok=True)
                    notes.append(f"《{w.get('title_zh')}》维基百科上的主图不是海报或封面")
                    log(f"  主图不是海报/封面：{name}")
                    continue
                seen_desc = str(d.get("description", "")).strip()
            except Exception as e:
                log(f"  看图描述失败，改用文字资料：{type(e).__name__}: {e}")
        break
    else:
        raise RuntimeError("今天的海报没核实成功：" + "；".join(notes))

    see_note = (f"下面是看过这张图的人对画面的客观描述，画面细节以它为准：\n{seen_desc}" if seen_desc
                else "你看不到图片，只根据资料和你确定知道的写，不确定的画面细节不要写。")
    designer = w.get("designer") or ""
    out = ctx.llm.json(BASE_SYSTEM, ANALYZE.format(
        kind=kind, title_zh=w.get("title_zh", ""), title_en=name, year=w.get("year", ""), creator=w.get("creator", ""),
        designer_note=f"设计师：{designer}（如果你不确定，就不要提设计师）。" if designer else "",
        style=w.get("style", ""), extract=wiki["extract"][:1500], see_note=see_note))
    analysis = list(out.get("analysis") or [])
    if out.get("prompt"):
        analysis.append({"label": "AI 生图提示词（模仿这种风格）", "text": out["prompt"]})
    ctx.mark_seen("posters", w.get("title_zh", ""))
    title_zh = w.get("title_zh", "")
    item = make_item(
        title=f"《{title_zh}》{name}",
        subtitle=" · ".join(str(p) for p in ("每日海报", kind, w.get("creator"), w.get("year")) if p),
        summary=out.get("summary", ""), analysis=analysis, tags=out.get("tags", []),
        images=[{"src": src, "caption": f"《{title_zh}》{kind.removeprefix('动画')}", "credit": "Wikipedia", "page": wiki["url"]}],
        links=[{"name": "维基百科", "url": wiki["url"]},
               search_link("pinterest", f"{out.get('style_name') or w.get('style', '')} poster".strip()),
               search_link("huaban", f"{title_zh} 海报")],
        source_note=("作品已在维基百科核实；" if seen_desc else "今天的分析没有看图，画面细节以图片为准；")
                    + "海报图片版权归原作者，只用于个人学习。")
    item["badge"] = f"每日海报 · {out.get('style_name')}" if out.get("style_name") else "每日海报"
    return [item]
