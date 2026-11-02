"""🎨 每天 1 种设计风格，配 3–4 张经过看图检查的例图。按 catalog/design_styles.json 顺序轮换。"""
from common import BASE_SYSTEM, GEN, load_json, make_item, search_link
from sources.images import pick_images, wikimedia_images

ID, NAME, EMOJI = "design_style", "设计风格", "🎨"
DAYS = range(7)

TASK = """今天介绍的设计风格是：{zh}（{en}），类别：{cat}。
读者没有设计基础，想提升审美。请写得让外行也能看懂，并且能马上用到自己的视频封面、海报或 AI 生图里。
analysis 写这几项：「一句话认出它」「起源」「色彩」「字体和排版」「构图和图形」「代表作品或设计师」「和相近风格的区别」「怎么用」（比如做视频封面、写 AI 生图提示词时可以怎么用）。每项 2–3 句。
另外给一段可以直接用的 AI 生图英文提示词。
输出 JSON：{{"summary": "一句话介绍", "analysis": [{{"label": "…", "text": "…"}}], "prompt": "英文提示词", "tags": ["3–5 个标签"]}}"""


def run(ctx):
    styles = load_json(GEN / "catalog" / "design_styles.json", [])
    idx = ctx.state.get("design_index", 0) % len(styles)
    s = styles[idx]
    out = ctx.llm.json(BASE_SYSTEM, TASK.format(**s), fake={
        "summary": "dry-run 示例。", "analysis": [{"label": "一句话认出它", "text": "示例。"}],
        "prompt": "example prompt", "tags": ["示例"]})
    cands = [{**i, "credit": "网络图片"} for i in
             ctx.search(f"{s['en']} {s.get('query', 'design')} examples", images=True, max_results=5)["images"]]
    cands += wikimedia_images(ctx, f"{s['en']} {s.get('query', 'design')}")
    images = pick_images(ctx, cands, f"{s['zh']}（{s['en']}）风格", want=4, name_hint="design")
    analysis = list(out.get("analysis") or [])
    if out.get("prompt"):
        analysis.append({"label": "AI 生图提示词", "text": out["prompt"]})
    kw = s["en"]
    ctx.state["design_index"] = idx + 1
    return [make_item(
        title=f"{s['zh']} {s['en']}", subtitle=s["cat"], summary=out.get("summary", ""), analysis=analysis,
        images=images, tags=out.get("tags", []),
        links=[search_link("pinterest", kw), search_link("huaban", s["zh"]), search_link("behance", kw)],
        source_note="" if images else "今天没找到合格的例图，可以点下面的链接看更多例子。",
    )]
