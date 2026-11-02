"""🤖 每天 1 条 AI 创意视频或 AI 剧情片。"""
from sections._video_pick import pick

ID, NAME, EMOJI = "ai_video", "AI 创意视频", "🤖"
DAYS = range(7)

QUERIES_ZH = [
    "AI 短片 创意 脑洞 可灵 即梦 海螺 生成",
    "AI 短剧 剧情 微电影 AI 生成 好看",
    "AI 生成视频 爆款 创意 运镜 特效",
    "AI 动画短片 画风 惊艳",
]
QUERIES_EN = [
    "AI generated short film creative Sora Veo Kling",
    "AI film festival short film winner",
    "AI music video creative generated",
]

TASK = """今天要推荐 1 条很有创意的 AI 生成视频（AI 创意短片，或者有剧情的 AI 短剧、微电影）。
要求：
1. 从候选里选一条最有创意、完成度最高、确实是 AI 生成的视频。播放量高是加分项，但创意优先。
2. 判断类型：「创意短片」还是「剧情片」。
3. 创意短片：analysis 写这几项：「创意点」「为什么让人眼前一亮」「可以借鉴的做法」。
   剧情片：analysis 写这几项：「剧本结构」（开头钩子、冲突、转折、结尾）「画面风格」（色调、镜头语言、角色和场景一致性）「可以借鉴的做法」。
   每项 2–4 句，尽量具体地指向这条视频；拿不准的细节不要编。
输出 JSON：{"pick": 候选序号, "type": "创意短片 或 剧情片", "title": "中文标题（可以意译）", "summary": "一句话介绍这条视频", "analysis": [{"label": "…", "text": "…"}], "tags": ["3–5 个标签"]}"""


def run(ctx):
    queries = [
        (ctx.rotate(QUERIES_ZH), {"time_range": "week"}),
        (ctx.rotate(QUERIES_EN), {"time_range": "month"}),
    ]
    item, out = pick(ctx, ID, queries, TASK, fake_extra={"type": "创意短片"})
    item["badge"] = out.get("type", "")
    return [item]
