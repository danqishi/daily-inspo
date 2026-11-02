"""✨ 每天 1 条有创意的视频（不是 AI 做的）。财经、访谈、纪录片、播客类每月最多 10 次。"""
from sections._video_pick import pick

ID, NAME, EMOJI = "creative_video", "创意视频", "✨"
DAYS = range(7)
FINANCE_MONTHLY_MAX = 10

THEMES = [
    ("创意广告 短片 视觉 惊艳", "creative commercial ad short film"),
    ("定格动画 创意 短片", "stop motion animation creative"),
    ("一镜到底 创意 视频", "one take creative video"),
    ("剧情反转 短片 创意", "short film plot twist award"),
    ("MV 创意 拍摄 视觉", "music video creative cinematography"),
    ("转场 剪辑 创意 视频", "creative editing transitions video"),
    ("实验短片 视觉艺术", "experimental short film visual art"),
]
FINANCE_THEMES = ["财经 深度 访谈 视频", "深度访谈 对话 人物", "纪录片 推荐 深度", "播客 视频版 深度对话"]

TASK = """今天要推荐 1 条很有创意的视频（**不要 AI 生成的**）。视觉上的创意（画面、剪辑、特效、摄影）或者剧情上的创意（结构、反转、叙事方式）都可以。
{finance_rule}
要求：
1. 从候选里选一条最有创意的作品本身，教程、“教你做”类视频不要选。
2. analysis 写这几项：「创意在哪」「为什么有效」「可以借鉴的做法」；如果是剧情类，再加一项「剧本结构」。每项 2–4 句，具体，拿不准的细节不要编。
输出 JSON：{{"pick": 候选序号, "is_finance_interview": true 或 false（是不是财经、访谈、纪录片、播客类）, "title": "中文标题", "summary": "一句话介绍", "analysis": [{{"label": "…", "text": "…"}}], "tags": ["3–5 个标签"]}}"""


def run(ctx):
    month = ctx.date_str[:7]
    counts = ctx.state.setdefault("finance_count", {})
    allow = counts.get(month, 0) < FINANCE_MONTHLY_MAX and ctx.date.day % 3 == 0
    zh, en = ctx.rotate(THEMES)
    queries = [(zh, {"time_range": "month"}), (en, {"time_range": "month"})]
    if allow:
        queries.append((ctx.rotate(FINANCE_THEMES), {"time_range": "month"}))
        rule = "今天可以选财经、访谈、纪录片、播客类的视频，也可以选别的，哪个更有创意选哪个。"
    else:
        rule = "今天**不要**选财经、访谈、纪录片、播客类的视频。"
    item, out = pick(ctx, ID, queries, TASK.format(finance_rule=rule))
    if out.get("is_finance_interview") is True:
        counts[month] = counts.get(month, 0) + 1
        item["badge"] = "财经 / 访谈"
    return [item]
