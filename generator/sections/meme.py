"""🔥 抖音热梗：周一到周五每天 1 条（每周 5 条）。"""
from common import BASE_SYSTEM, as_int, make_item, search_link
from sources.hot import douyin_hot

ID, NAME, EMOJI = "meme", "抖音热梗", "🔥"
DAYS = range(5)

QUERIES = ["抖音 最近爆火的梗 是什么梗 出处", "最新网络热梗 抖音 什么意思 由来", "抖音 热梗 盘点 本周"]

TASK = """今天要介绍 1 个最近在抖音上很火的「梗」（类似“牛来”“许愿柳”“闪身步”“OMG 你吓到我了”“我画地为牢啊厉娜”这种：一句台词、一个动作、一个模板或一种玩法，被大量模仿和二创）。
**必须是真的有热度的梗**，依据是下面的热榜和搜索结果。普通新闻、明星八卦不算梗。
这些已经介绍过，不要重复：{seen}

抖音热榜：
{hot}

搜索结果：
{results}

analysis 写这几项：「出处」（最早从哪来）「为什么火」「怎么用」（举 1–2 个评论区或视频里的用法）「热度依据」（来自热榜还是哪篇报道）。
输出 JSON：{{"name": "梗的名字", "summary": "一句话解释意思", "analysis": [{{"label": "…", "text": "…"}}], "source_index": 参考的搜索结果序号（没有就填 -1）, "search_keyword": "在抖音搜索用的关键词", "tags": ["2–4 个标签"]}}"""


def run(ctx):
    hot = douyin_hot(ctx)
    res = ctx.search(ctx.rotate(QUERIES), time_range="week", max_results=8)["results"]
    if not hot and not res:
        raise RuntimeError("热榜和搜索都没拿到数据")
    seen = ctx.seen(ID)
    prompt = TASK.format(
        seen="、".join(seen[-60:]) or "（暂无）",
        hot="\n".join(f"- {t}" for t in hot) or "（今天没拿到热榜）",
        results="\n".join(f"[{i}] {r['title']}：{(r.get('content') or '')[:300]}" for i, r in enumerate(res)),
    )
    out = ctx.llm.json(BASE_SYSTEM, prompt, fake={
        "name": "示例热梗", "summary": "dry-run 示例。", "analysis": [{"label": "出处", "text": "示例。"}],
        "source_index": 0, "search_keyword": "示例热梗", "tags": ["示例"]})
    name = out.get("name") or "热梗"
    ctx.mark_seen(ID, name)
    kw = out.get("search_keyword") or name
    links = [search_link("douyin", kw), search_link("bilibili", kw)]
    idx = as_int(out.get("source_index"), -1)
    if 0 <= idx < len(res):
        links.append({"name": "参考来源", "url": res[idx]["url"]})
    return [make_item(title=name, summary=out.get("summary", ""), analysis=out.get("analysis"),
                      links=links, tags=out.get("tags", []))]
