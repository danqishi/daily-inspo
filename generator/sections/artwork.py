"""🖼 每天 1 幅画或摄影作品（交替），来自大都会博物馆公有领域馆藏，看图写构图和色彩分析。"""
from common import BASE_SYSTEM, log, make_item
from sources.images import fetch_image, write_image
from sources.museum import random_object

ID, NAME, EMOJI = "artwork", "摄影和画作", "🖼"
DAYS = range(7)

TASK = """今天赏析的作品：
- 名称：{title}
- 作者：{artist}
- 年代：{date}
- 材质：{medium}
- 类别：{kind}

关于这件作品的资料（背景故事以这里为准，资料里没有的就不要写具体事实）：
{refs}

读者没有美术基础，想提升审美。请带着读者“怎么看”这幅作品，并且能把方法用到自己拍照、做视频画面上。
analysis 写这几项：「第一眼看哪里」「构图」（主体位置、线条、留白、视角）「色彩」（主色、冷暖、对比）「光线」「细节和看点」「背景故事」「可以学到什么」。每项 2–3 句，要具体到这幅作品，不要写放在哪幅作品上都成立的套话。
「背景故事」只写资料里有的内容；资料里没有，就省略这一项。
{see_note}
输出 JSON：{{"title_zh": "中文作品名", "summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["3–5 个标签"]}}"""


def run(ctx):
    toggle = ctx.state.get("artwork_toggle", 0)
    kind = "painting" if toggle % 2 == 0 else "photo"
    o = random_object(ctx, kind) or random_object(ctx, "photo" if kind == "painting" else "painting")
    if not o:
        raise RuntimeError("大都会博物馆没取到作品")
    fields = dict(title=o.get("title", ""), artist=o.get("artistDisplayName") or "佚名",
                  date=o.get("objectDate", ""), medium=o.get("medium", ""),
                  kind="画作" if kind == "painting" else "摄影")
    res = ctx.search(f"{fields['title']} {fields['artist']} {fields['date']} Met museum", max_results=4)["results"]
    refs = "\n".join(f"- {r['title']}：{(r.get('content') or '')[:500]}" for r in res) or "（没找到资料）"
    image = None if ctx.dry else fetch_image(ctx, o["primaryImageSmall"])
    fake = {"title_zh": "【示例】作品", "summary": "dry-run 示例。",
            "analysis": [{"label": "构图", "text": "示例。"}], "tags": ["示例"]}
    note = ""
    try:
        if not (image or ctx.dry):
            raise RuntimeError("图片下载失败")
        out = ctx.llm.json(BASE_SYSTEM, TASK.format(**fields, refs=refs, see_note="请仔细看图，分析要对得上图里真实的内容。"),
                           fake=fake, image=image)
    except Exception as e:
        log(f"  看图分析失败，改用文字资料：{type(e).__name__}: {e}")
        out = ctx.llm.json(BASE_SYSTEM, TASK.format(**fields, refs=refs, see_note="你看不到图片，只根据资料写，不确定的画面细节不要写。"),
                           fake=fake)
        note = "今天的分析没有看图，是根据作品资料写的，画面细节以图片为准。"
    if ctx.dry:
        src = o["primaryImageSmall"]
    else:
        src = write_image(ctx, image, o["primaryImageSmall"], "art") if image else None
    ctx.state["artwork_toggle"] = toggle + 1
    ctx.mark_seen(ID, o["objectID"])
    images = [{"src": src, "caption": fields["title"], "credit": "The Met · Public Domain",
               "page": o.get("objectURL", ""), "full": o.get("primaryImage") or o["primaryImageSmall"]}] if src else []
    item = make_item(
        title=out.get("title_zh") or fields["title"],
        subtitle=" · ".join(p for p in (fields["artist"], fields["date"], fields["medium"]) if p),
        summary=out.get("summary", ""), analysis=out.get("analysis"), images=images,
        links=[{"name": "大都会博物馆页面", "url": o.get("objectURL", "")}], tags=out.get("tags", []),
        source_note=note)
    item["badge"] = fields["kind"]
    return [item]
