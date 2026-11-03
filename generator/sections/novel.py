"""📚 每天 1 本扫文小院的高分双男主小说。先按读者标签筛掉雷点，再让模型读书评复查一遍。"""
import re

from common import log, make_item
from sources import saowen

ID, NAME, EMOJI = "novel", "双男主小说", "📚"
DAYS = range(7)

MIN_SCORE = 7.5
MIN_RATERS = 30
MAX_PAGES = 15     # 每个标签最多往后翻几页
WANT = 3           # 凑够几本候选就停，交给模型逐本复查
PREFERRED = ["美攻强受", "美强", "追夫", "美人攻", "强受"]   # 读者偏好，优先推荐
GENERAL = ["he", "强强", "1v1"]                           # 其他类型，按高分 he 文找

# 读者的雷点：标签名命中就算。“追夫火葬场”是受追攻，不算追妻。
BAD_TAG = re.compile(r"(?i)(^|[^a-z])(be|oe)([^a-z]|$)|悲剧|开放.*结局|双性|追妻|弱强|弱攻强受|^弱攻$|坑|未完")
BAD_UNLESS = {"火葬场": "追夫"}
GOOD_TAG = re.compile(r"美攻强受|美强|追夫|美人攻|强受")

SYSTEM = ("你是一位读过大量耽美小说的编辑，在给一位读者每天推荐一本双男主小说。"
          "只根据给你的资料（读者标签和书评）写，不要编造资料里没有的剧情、人名和设定，拿不准就不写。只输出 JSON。")

TASK = """候选书：《{title}》，作者：{author}
扫文小院评分：{score}（{raters} 人评分）
作品信息：{info}
读者标签（括号里是打这个标签的人数）：{tags}

高赞书评（节选）：
{reviews}

读者的口味：
- 雷点（有任何一条就不推荐）：BE（包括 BE 支线、BE 番外、主角之一死亡、开放式偏悲的结局）、双性、追妻火葬场（攻追受）、弱攻强受、没完结或烂尾的坑。
- 喜欢：美攻强受（美人攻，受很强）、追夫（受追攻）。其他类型也可以推。
- 必须是两位男性主角谈恋爱的双男主文。

第一步：根据标签和书评判断这本书有没有踩雷、是不是双男主。标签人数很少（1 个人）而书评里没提到的，可以忽略。
第二步：如果可以推荐，写推荐语：
- summary：一句话说清这是个什么故事，让人想点开。
- analysis 写这几项：「讲什么」（故事背景和主线，不剧透结局）「两位主角」（各是什么样的人，谁攻谁受，书评里看得出来就写）「好看在哪」（读者最常夸的点）「读前须知」（文风、节奏、篇幅、可能劝退的地方；没有就写节奏和篇幅）。
- tags：3–5 个，挑最能说明类型和口味的。

输出 JSON：{{"ok": true 或 false, "reason": "不推荐的原因，或者为什么适合这位读者（一句话）",
"summary": "…", "analysis": [{{"label": "讲什么", "text": "…"}}], "tags": ["…"]}}"""


def _bad_tags(tags, min_count=1):
    bad = []
    for name, n in tags.items():
        if n < min_count:
            continue
        if BAD_TAG.search(name):
            bad.append(name)
        for word, unless in BAD_UNLESS.items():
            if word in name and unless not in name:
                bad.append(name)
    return bad


def _eligible(n, skip):
    info = n["info"]
    return (n["id"] not in skip and not n["marked"]
            and "耽美" in info and "原创" in info and "已完结" in info
            and n["score"] >= MIN_SCORE and n["raters"] >= MIN_RATERS
            and not _bad_tags(n["tags"], min_count=2))


def _candidates(ctx, skip):
    first = PREFERRED if ctx.rng.random() < 0.6 else GENERAL
    order = ctx.rng.sample(first, len(first)) + [t for t in PREFERRED + GENERAL if t not in first]
    for tag in order:
        found = []
        for page in range(1, MAX_PAGES + 1):
            items = saowen.fetch_list(ctx.http, saowen.tag_list_url(tag, page))
            found += [n for n in items if _eligible(n, skip) and n["id"] not in {f["id"] for f in found}]
            if len(found) >= WANT or len(items) < 20 or (items and items[-1]["score"] < MIN_SCORE):
                break
        if found:
            log(f"  标签「{tag}」找到 {len(found)} 本候选")
            # 偏好的类型排前面，同类按评分
            found.sort(key=lambda n: (-any(GOOD_TAG.search(t) for t in n["tags"]), -n["score"]))
            return found[:WANT]
    return []


def _site_name(url):
    for host, name in (("jjwxc", "晋江"), ("gongzicp", "长佩"), ("changpei", "长佩"), ("po18", "PO18"),
                       ("lofter", "LOFTER"), ("qidian", "起点"), ("ao3", "AO3"), ("archiveofourown", "AO3")):
        if host in url:
            return name
    return "首发网站"


def _fmt_tags(tags):
    return "、".join(f"{k}({v})" for k, v in tags.items())


def _fake():
    return [make_item(title="《示例小说》", subtitle="示例作者 · 扫文 8.5 分（100 人评分）",
                      summary="dry-run 示例。", analysis=[{"label": "讲什么", "text": "示例。"}],
                      links=[{"name": "扫文小院", "url": saowen.novel_url(1000)}], tags=["示例"])]


def run(ctx):
    if ctx.dry:
        return _fake()
    saowen.login(ctx.http)
    skip = set(ctx.seen("novel")) | set(ctx.seen("novel_rejected"))
    for n in _candidates(ctx, skip):
        detail = saowen.fetch_detail(ctx.http, n["id"])
        tags = detail["tags"] or n["tags"]
        bad = _bad_tags(tags, min_count=2)
        if bad:
            log(f"  《{n['title']}》标签踩雷：{'、'.join(bad)}")
            ctx.mark_seen("novel_rejected", n["id"])
            continue
        reviews = saowen.fetch_reviews(ctx.http, n["id"])
        info = detail["info"]
        out = ctx.llm.json(SYSTEM, TASK.format(
            title=n["title"], author=n["author"], score=n["score"], raters=n["raters"],
            info="；".join(f"{k}：{v}" for k, v in info.items() if v and v != "未知") or "/".join(n["info"]),
            tags=_fmt_tags(tags), reviews="\n".join(f"- {r}" for r in reviews) or "（没有书评）"))
        if not out.get("ok"):
            log(f"  《{n['title']}》模型判断不推荐：{out.get('reason', '')}")
            ctx.mark_seen("novel_rejected", n["id"])
            continue

        ctx.mark_seen("novel", n["id"])
        parts = [n["author"], f"扫文 {n['score']} 分（{n['raters']} 人评分）"]
        if info.get("篇幅"):
            parts.append(f"篇幅：{info['篇幅']}")
        analysis = list(out.get("analysis") or [])
        if out.get("reason"):
            analysis.append({"label": "为什么推荐给你", "text": out["reason"]})
        links = [{"name": "扫文小院（评分和书评）", "url": saowen.novel_url(n["id"])}]
        if detail["source_url"]:
            links.append({"name": f"去{_site_name(detail['source_url'])}看", "url": detail["source_url"]})
        return [make_item(
            title=f"《{n['title']}》", subtitle=" · ".join(parts), summary=out.get("summary", ""),
            analysis=analysis, links=links, tags=out.get("tags", []),
            source_note="评分和标签来自扫文小院；介绍根据读者标签和书评整理，AI 没有读过原文。")]
    raise RuntimeError("今天没找到符合口味的书")
