"""AI 视频和创意视频两个栏目共用：给模型看候选，选一条写解读，组装成卡片。"""
from common import BASE_SYSTEM, VIDEO_NOTE, as_int, make_item, search_link
from sources import video
from sources.images import save_image


def pick(ctx, seen_key, queries, task, fake_extra=None):
    cands = video.candidates(ctx, seen_key, queries)
    if not cands:
        raise RuntimeError("没有搜到可用的视频")
    fake = {"pick": 0, "title": "【示例】一条很有创意的视频", "summary": "dry-run 示例内容。",
            "analysis": [{"label": "创意点", "text": "示例解读文字。"}], "tags": ["示例"], **(fake_extra or {})}
    rule = ("重要：你看不到视频画面，只能看到下面的标题、简介和播放量。解读只能基于这些信息和常识推断，"
            "不要描写具体的画面细节、镜头和台词（比如“视频里切了水果”），推断的地方用“从标题看”“这类视频通常”这样的说法。"
            "播放量高的优先。")
    out = ctx.llm.json(BASE_SYSTEM, f"{task}\n\n{rule}\n\n候选视频：\n{video.describe(cands)}", fake=fake)
    c = cands[min(max(as_int(out.get("pick"), 0), 0), len(cands) - 1)]
    ctx.mark_seen(seen_key, c["url"])
    images = []
    if c.get("cover"):
        src = save_image(ctx, c["cover"], seen_key)
        if src:
            images.append({"src": src, "caption": "视频封面", "credit": c["platform"]})
    keyword = c.get("title") or out.get("title", "")
    links = [{"name": f"去{c['platform']}看", "url": c["url"]}]
    if c["platform"] != "B站":
        links.append(search_link("bilibili", keyword))
    item = make_item(
        title=out.get("title") or c["title"], subtitle=video.subtitle(c), summary=out.get("summary", ""),
        analysis=out.get("analysis"), links=links, images=images, tags=out.get("tags", []),
        source_note=VIDEO_NOTE,
    )
    item["original_title"] = c["title"]
    return item, out
