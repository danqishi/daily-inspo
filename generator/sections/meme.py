"""🔥 抖音热梗：周一到周五每天 1 条（每周 5 条）。
分两步：先从热榜和搜索结果里挑出真实存在的梗名，再专门搜这个梗的解释，按搜到的资料写，避免编造。"""
from common import BASE_SYSTEM, grounded, log, make_item, search_link
from sources.hot import douyin_hot

ID, NAME, EMOJI = "meme", "抖音热梗", "🔥"
DAYS = range(5)

QUERIES = ["抖音 最近爆火的梗 是什么梗 出处", "最新网络热梗 抖音 什么意思 由来", "抖音 热梗 盘点 本周"]

PICK = """从下面的资料里，找出最近在抖音上很火的「梗」（类似“牛来”“许愿柳”“闪身步”“OMG 你吓到我了”“我画地为牢啊厉娜”这种：一句台词、一个动作、一个模板或一种玩法，被大量模仿和二创）。
普通新闻、明星八卦、节日促销话题不算梗。**梗的名字必须原样出现在资料里**，不能自己编、不能凭记忆写旧梗。
这些已经介绍过，不要重复：{seen}

抖音热榜：
{hot}

搜索结果（最近一周）：
{results}

按热度从高到低给出最多 3 个。输出 JSON：{{"names": ["梗的名字（和资料里写法一致）"]}}"""

WRITE = """今天要介绍的抖音热梗是：「{name}」。下面是专门搜到的关于它的资料：
{refs}

**只根据这些资料来写**，资料里没有的细节不要编。如果资料根本没解释这个梗是什么，把 explained 设为 false。
analysis 写这几项：「出处」「为什么火」「怎么用」（举 1–2 个用法）「热度依据」。资料不够的项可以写短一点或省略。
输出 JSON：{{"explained": true 或 false, "summary": "一句话解释意思", "analysis": [{{"label": "…", "text": "…"}}], "source_index": 主要参考的资料序号, "search_keyword": "在抖音搜索用的关键词", "tags": ["2–4 个标签"]}}"""


def _gather(ctx):
    res, urls = [], set()
    for q, kw in ((ctx.rotate(QUERIES), {}), ("抖音 新梗 爆火", {"topic": "news"})):
        for r in ctx.search(q, time_range="week", max_results=8, **kw)["results"]:
            if r["url"] not in urls:
                urls.add(r["url"])
                res.append(r)
    return res


def run(ctx):
    hot = douyin_hot(ctx)
    res = _gather(ctx)
    if not hot and not res:
        raise RuntimeError("热榜和搜索都没拿到数据")
    seen = ctx.seen(ID)
    texts = hot + [f"{r['title']} {r.get('content') or ''}" for r in res]
    picked = ctx.llm.json(BASE_SYSTEM, PICK.format(
        seen="、".join(seen[-60:]) or "（暂无）",
        hot="\n".join(f"- {t}" for t in hot) or "（今天没拿到热榜）",
        results="\n".join(f"- {r['title']}：{(r.get('content') or '')[:400]}" for r in res),
    ), fake={"names": ["示例热搜 A"]})

    tried = 0
    for name in picked.get("names") or []:
        name = str(name).strip()
        if not name or name in seen:
            continue
        if not grounded(name, texts):
            log(f"  「{name}」在资料里找不到，可能是编的，跳过")
            continue
        if tried >= 2:
            break
        tried += 1
        refs = ctx.search(f"{name} 是什么梗 出处", time_range="month", max_results=6)["results"]
        if not refs:
            continue
        out = ctx.llm.json(BASE_SYSTEM, WRITE.format(
            name=name, refs="\n".join(f"[{i}] {r['title']}：{(r.get('content') or '')[:500]}" for i, r in enumerate(refs))),
            fake={"explained": True, "summary": "dry-run 示例。", "analysis": [{"label": "出处", "text": "示例。"}],
                  "source_index": 0, "search_keyword": name, "tags": ["示例"]})
        if not out.get("explained", True):
            log(f"  「{name}」搜不到解释，换下一个")
            continue
        ctx.mark_seen(ID, name)
        kw = out.get("search_keyword") or name
        links = [search_link("douyin", kw), search_link("bilibili", kw)]
        idx = out.get("source_index")
        if isinstance(idx, int) and 0 <= idx < len(refs):
            links.append({"name": "参考来源", "url": refs[idx]["url"]})
        return [make_item(title=name, summary=out.get("summary", ""), analysis=out.get("analysis"),
                          links=links, tags=out.get("tags", []))]
    raise RuntimeError("没有找到能核实的新梗")
