"""🛠 AI 视频和图片制作资讯：周一到周五每天 2 条（每周 10 条），以视频工具为主。"""
import re

from common import BASE_SYSTEM, as_int, make_item

ID, NAME, EMOJI = "ai_news", "AI 视频和图片制作资讯", "🛠"
DAYS = range(5)

# 频道主页、列表页、标签页不是一篇具体的文章；后面几个是云服务优惠券站
NOT_ARTICLE = re.compile(r"youtube\.com/(@|channel/|c/|user/)|/(videos|tags?|search|category)/?(\?|$)|"
                         r"tengxunyun8\.com|aliyun888|yunfuwuqiba")

VIDEO_QUERIES = [
    "可灵 即梦 海螺 Vidu AI视频 新功能 更新",
    "Runway Veo Sora Kling AI video new feature update",
    "AI 视频 教程 运镜 首尾帧 角色一致性 技巧",
    "AI 视频 省积分 技巧 免费额度",
]
IMAGE_QUERIES = [
    "Midjourney 即梦 GPT 图像 Nano Banana Flux 新功能 更新",
    "AI 绘图 提示词 技巧 教程 LibLib Stable Diffusion",
    "AI image generator new model update Midjourney Flux Gemini",
]

TASK = """今天要推荐 2 条 AI 视频和图片制作相关的资讯，读者在学用 AI 做视频。
类型可以是：新模型、新功能、教程、场景制作方法、省积分技巧、提示词技巧。
规则：至少 1 条是**视频**工具相关的，另一条视频或图片工具都可以；优先选最新、最实用的；两条不要讲同一件事。
不要选：纯融资或八卦新闻；云服务器、API 的促销和优惠券广告；内容空洞、只有标题党的文章。
候选：
{cands}

每条的 analysis 写这几项：「讲了什么」「怎么用 / 适合做什么」「注意事项或省积分技巧」（没有就写“上手前先用免费额度试几次”这类具体建议）。
输出 JSON：{{"items": [{{"pick": 候选序号, "kind": "视频工具 或 图片工具", "title": "中文标题", "summary": "一句话", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["工具名等 2–4 个标签"]}}]}}"""


def run(ctx):
    seen = set(ctx.seen(ID))
    res, urls = [], set()
    for q in (ctx.rotate(VIDEO_QUERIES), ctx.rotate(VIDEO_QUERIES, 1), ctx.rotate(IMAGE_QUERIES)):
        for r in ctx.search(q, topic="news", time_range="week", max_results=8)["results"]:
            if NOT_ARTICLE.search(r["url"]):
                continue
            if r["url"] not in seen and r["url"] not in urls:
                urls.add(r["url"])
                res.append(r)
    if not res:
        raise RuntimeError("没有搜到资讯")
    cands = "\n".join(f"[{i}] {r['title']}：{(r.get('content') or '')[:350]}" for i, r in enumerate(res))
    out = ctx.llm.json(BASE_SYSTEM, TASK.format(cands=cands), fake={"items": [
        {"pick": 0, "kind": "视频工具", "title": "【示例】某视频模型上线新功能", "summary": "示例。",
         "analysis": [{"label": "讲了什么", "text": "示例。"}], "tags": ["示例"]},
        {"pick": 1, "kind": "图片工具", "title": "【示例】某绘图工具提示词技巧", "summary": "示例。",
         "analysis": [{"label": "讲了什么", "text": "示例。"}], "tags": ["示例"]}]})
    items, used = [], set()
    for o in (out.get("items") or [])[:2]:
        i = as_int(o.get("pick"), -1)
        if not 0 <= i < len(res) or i in used:
            continue
        used.add(i)
        r = res[i]
        ctx.mark_seen(ID, r["url"])
        item = make_item(title=o.get("title") or r["title"], summary=o.get("summary", ""),
                         analysis=o.get("analysis"), links=[{"name": "看原文", "url": r["url"]}],
                         tags=o.get("tags", []))
        item["badge"] = o.get("kind", "")
        items.append(item)
    if not items:
        raise RuntimeError("模型没有选出有效的资讯")
    return items
