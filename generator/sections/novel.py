"""📚 每天 2 本双男主小说：1 本扫文小院高分文，1 本长佩或晋江的完结文（隔天轮换）。
先按标签筛掉雷点，再让模型读书评或文案复查一遍。"""
import re

from common import log, make_item
from sources import platforms, saowen

ID, NAME, EMOJI = "novel", "双男主小说", "📚"
DAYS = range(7)

MIN_SCORE = 7.5
MIN_RATERS = 30
MAX_PAGES = 15     # 每个标签最多往后翻几页
WANT = 3           # 凑够几本候选就停，交给模型逐本复查
PREFERRED = ["美攻强受", "美强", "追夫", "美人攻", "强受"]   # 读者偏好，优先推荐
GENERAL = ["he", "强强", "1v1"]                           # 其他类型，按高分 he 文找

MIN_CLICKS = 5000  # 长佩“人阅读”、晋江“章均点击”的下限
PLATFORM_DETAILS = 30  # 长佩/晋江每天最多查几本书的详情
MIN_SAOWEN_SCORE = 6.5  # 长佩/晋江的书如果扫文有评分（10 人以上），低于这个分就不推

# 读者的雷点：标签名命中就算。“追夫火葬场”是受追攻，不算追妻。
BAD_TAG = re.compile(r"(?i)(^|[^a-z])(be|oe|bg)([^a-z]|$)|悲剧|开放.*结局|双性|追妻|攻追受|弱强|弱攻强受|^弱攻$|坑|未完|腰斩|烂尾|非耽美|无cp|百合")
BAD_UNLESS = {"火葬场": "追夫"}
# 系列的续作、番外单独推没头没尾，跳过
SEQUEL = re.compile(r"[2-9２-９二三四五六七八九]\s*$|[2-9二三四五六七八九][(（]|续|番外|第[二三四五六七八九]部")
GOOD_TAG = re.compile(r"美攻强受|美强|追夫|受追攻|美人攻|强受")

SYSTEM = ("你是一位读过大量耽美小说的编辑，在给一位读者每天推荐双男主小说。"
          "只根据给你的资料写，不要编造资料里没有的剧情、人名和设定，拿不准就不写。只输出 JSON。")

TASTE = """读者的口味：
- 雷点（有任何一条就不推荐）：BE（包括 BE 支线、BE 番外、主角之一死亡、开放式偏悲的结局）、双性、追妻火葬场（攻追受）、弱攻强受、没完结或烂尾的坑。
- 喜欢：美攻强受（美人攻，受很强）、追夫（受追攻）。其他类型也可以推。
- 必须是两位男性主角谈恋爱的双男主文。"""

WRITE = """第二步：如果可以推荐，写推荐语：
- summary：一句话说清这是个什么故事，让人想点开。
- analysis 写这几项：「讲什么」（故事背景和主线，不剧透结局）「两位主角」（各是什么样的人，谁攻谁受，资料里看得出来就写）「好看在哪」{good_hint}「读前须知」（文风、节奏、篇幅、可能劝退的地方；没有就写节奏和篇幅）。
- tags：3–5 个，挑最能说明类型和口味的。

输出 JSON：{{"ok": true 或 false, "reason": "不推荐的原因，或者为什么适合这位读者（一句话）",
"summary": "…", "analysis": [{{"label": "讲什么", "text": "…"}}], "tags": ["…"]}}"""

TASK = """候选书：《{title}》，作者：{author}
扫文小院评分：{score}（{raters} 人评分）
作品信息：{info}
读者标签（括号里是打这个标签的人数）：{tags}

高赞书评（节选）：
{reviews}

""" + TASTE + """

第一步：根据标签和书评判断这本书有没有踩雷、是不是双男主。标签人数很少（1 个人）而书评里没提到的，可以忽略。
""" + WRITE.replace("{good_hint}", "（读者最常夸的点）")

PLATFORM_TASK = """候选书：《{title}》，作者：{author}，{platform}文学城/网站首发，已完结
分类：{category}
作者标的标签：{tags}
数据：{clicks} {clicks_label}；{extra}；字数约 {words} 万
{protagonists}

文案：
{intro}

{saowen}
""" + TASTE + """

第一步：根据文案、标签{saowen_hint}判断这本书有没有踩雷、是不是双男主。文案里写明是 HE、或者标签有 HE 的更放心；
文案里出现“BE”“刀”“开放式结局”“追妻”“火葬场（攻追受）”等字样要仔细判断。拿不准是不是 HE 就不推荐。
""" + WRITE.replace("{good_hint}", "（从文案和设定看，这本书的看点）")


def _bad_tags(tags, min_count=1):
    """tags 可以是 {标签: 人数}（扫文）或标签列表（长佩、晋江，人数当作足够）。"""
    if not isinstance(tags, dict):
        tags = {t: min_count for t in tags}
    bad = []
    for name, n in tags.items():
        if n < min_count:
            continue
        if BAD_TAG.search(name):
            bad.append(name)
        for word, unless in BAD_UNLESS.items():
            if word in name and unless not in name and "受追攻" not in name:
                bad.append(name)
    return bad


def _fmt_tags(tags):
    return "、".join(f"{k}({v})" for k, v in tags.items())


def _site_name(url):
    for host, name in (("jjwxc", "晋江"), ("gongzicp", "长佩"), ("changpei", "长佩"), ("po18", "PO18"),
                       ("lofter", "LOFTER"), ("qidian", "起点"), ("ao3", "AO3"), ("archiveofourown", "AO3")):
        if host in url:
            return name
    return "首发网站"


def _title_key(title):
    return re.sub(r"[\s\W_]+|\(.*?\)|（.*?）|\[.*?\]", "", title).lower()


def _finish(out):
    analysis = list(out.get("analysis") or [])
    if out.get("reason"):
        analysis.append({"label": "为什么推荐给你", "text": out["reason"]})
    return analysis


# ---------- 扫文小院 ----------

def _eligible(n, skip):
    info = n["info"]
    return (n["id"] not in skip and not n["marked"] and not SEQUEL.search(n["title"])
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
            log(f"  扫文：标签「{tag}」找到 {len(found)} 本候选")
            # 偏好的类型排前面，同类按评分
            found.sort(key=lambda n: (-any(GOOD_TAG.search(t) for t in n["tags"]), -n["score"]))
            return found[:WANT]
    return []


def _saowen_pick(ctx):
    skip = set(ctx.seen("novel")) | set(ctx.seen("novel_rejected"))
    titles = set(ctx.seen("novel_titles"))
    for n in _candidates(ctx, skip):
        if _title_key(n["title"]) in titles:
            continue
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
        ctx.mark_seen("novel_titles", _title_key(n["title"]))
        parts = [n["author"], f"扫文 {n['score']} 分（{n['raters']} 人评分）"]
        if info.get("篇幅"):
            parts.append(f"篇幅：{info['篇幅']}")
        links = [{"name": "扫文小院（评分和书评）", "url": saowen.novel_url(n["id"])}]
        if detail["source_url"]:
            links.append({"name": f"去{_site_name(detail['source_url'])}看", "url": detail["source_url"]})
        return make_item(
            title=f"《{n['title']}》", subtitle="扫文小院高分 · " + " · ".join(parts), summary=out.get("summary", ""),
            analysis=_finish(out), links=links, tags=out.get("tags", []),
            source_note="评分和标签来自扫文小院；介绍根据读者标签和书评整理，AI 没有读过原文。")
    raise RuntimeError("扫文小院今天没找到符合口味的书")


# ---------- 长佩 / 晋江 ----------

def _platform_candidates(ctx, platform):
    """换着排序方式和页码取一批书，打乱顺序，偏好的类型排前面。"""
    rng = ctx.rng
    found = []
    for _ in range(3):
        if platform == "长佩":
            items = platforms.cp_list(ctx.http, rng.randint(1, 50), rng.choice([0, 1, 3, 4]))
        else:
            tag = rng.choice([None, None, *platforms.JJ_TAGS.values()])
            items = platforms.jj_list(ctx.http, rng.randint(1, 10), rng.choice([2, 4]), tag)
        found += items
    rng.shuffle(found)
    found.sort(key=lambda n: -any(GOOD_TAG.search(t) for t in n["tags"]))
    return found


def _platform_pick(ctx, platform):
    key = "cp" if platform == "长佩" else "jj"
    skip = set(ctx.seen("novel")) | set(ctx.seen("novel_rejected"))
    titles = set(ctx.seen("novel_titles"))
    fetch = platforms.cp_detail if platform == "长佩" else platforms.jj_detail
    checked = llm_calls = 0
    seen_ids = set()
    why = {"详情失败": 0, "未完结/非纯爱": 0, f"点击不到 {MIN_CLICKS}": 0, "标签踩雷": 0}
    for c in _platform_candidates(ctx, platform):
        if checked >= PLATFORM_DETAILS or llm_calls >= WANT:
            break
        uid = f"{key}:{c['id']}"
        if (uid in skip or uid in seen_ids or _title_key(c["title"]) in titles or _bad_tags(c["tags"])
                or SEQUEL.search(c["title"])):
            continue
        seen_ids.add(uid)
        checked += 1
        try:
            b = fetch(ctx.http, c["id"])
        except Exception as e:
            log(f"  {platform} {c['id']} 详情没取到：{e}")
            why["详情失败"] += 1
            continue
        if not (b["finished"] and b["bl"]):
            why["未完结/非纯爱"] += 1
            continue
        if b["clicks"] < MIN_CLICKS:
            why[f"点击不到 {MIN_CLICKS}"] += 1
            continue
        bad = _bad_tags(b["tags"])
        if bad:
            why["标签踩雷"] += 1
            log(f"  《{b['title']}》标签踩雷：{'、'.join(bad)}")
            ctx.mark_seen("novel_rejected", uid)
            continue

        # 扫文小院也收录了的话，读者标签和书评一起给模型看，排雷更准
        sw_note, sw_hint, sw_link = "", "", None
        try:
            sw = saowen.find(ctx.http, b["title"], b["author"])
            if sw:
                d = saowen.fetch_detail(ctx.http, sw["id"])
                tags = d["tags"] or sw["tags"]
                bad = _bad_tags(tags, min_count=2)
                if bad:
                    log(f"  《{b['title']}》扫文读者标签踩雷：{'、'.join(bad)}")
                    ctx.mark_seen("novel_rejected", uid)
                    continue
                if sw["raters"] >= 10 and sw["score"] < MIN_SAOWEN_SCORE:
                    log(f"  《{b['title']}》扫文评分只有 {sw['score']}，跳过")
                    ctx.mark_seen("novel_rejected", uid)
                    continue
                reviews = saowen.fetch_reviews(ctx.http, sw["id"], limit=6)
                sw_note = (f"扫文小院读者评价：{sw['score'] or '评分人数不足'} 分（{sw['raters']} 人评分）\n"
                           f"读者标签：{_fmt_tags(tags)}\n书评节选：\n" + "\n".join(f"- {r}" for r in reviews) + "\n")
                sw_hint, sw_link = "和扫文小院读者的评价", saowen.novel_url(sw["id"])
        except Exception as e:
            log(f"  扫文查《{b['title']}》失败：{e}")

        llm_calls += 1
        out = ctx.llm.json(SYSTEM, PLATFORM_TASK.format(
            title=b["title"], author=b["author"], platform=platform, category=b["category"],
            tags="、".join(b["tags"]) or "无", clicks=b["clicks"], clicks_label=b["clicks_label"], extra=b["extra"],
            words=round(b["words"] / 10000, 1), protagonists=b["protagonists"], intro=b["intro"][:1500],
            saowen=sw_note, saowen_hint=sw_hint))
        if not out.get("ok"):
            log(f"  《{b['title']}》模型判断不推荐：{out.get('reason', '')}")
            ctx.mark_seen("novel_rejected", uid)
            continue

        ctx.mark_seen("novel", uid)
        ctx.mark_seen("novel_titles", _title_key(b["title"]))
        links = [{"name": f"去{platform}看", "url": b["url"]}]
        if sw_link:
            links.append({"name": "扫文小院（读者评价）", "url": sw_link})
        return make_item(
            title=f"《{b['title']}》",
            subtitle=f"{platform}完结 · {b['author']} · {b['clicks']:,} {b['clicks_label']} · 约 {round(b['words'] / 10000)} 万字",
            summary=out.get("summary", ""), analysis=_finish(out), links=links, tags=out.get("tags", []),
            source_note=f"数据和文案来自{platform}；介绍根据文案、标签{sw_hint}整理，AI 没有读过原文。")
    log(f"  {platform}：查了 {checked} 本详情，问模型 {llm_calls} 次；" + "，".join(f"{k} {v}" for k, v in why.items()))
    raise RuntimeError(f"{platform}今天没找到符合口味的书")


def _fake():
    return [make_item(title="《示例小说》", subtitle="扫文小院高分 · 示例作者 · 扫文 8.5 分（100 人评分）",
                      summary="dry-run 示例。", analysis=[{"label": "讲什么", "text": "示例。"}],
                      links=[{"name": "扫文小院", "url": saowen.novel_url(1000)}], tags=["示例"]),
            make_item(title="《示例小说二》", subtitle="长佩完结 · 示例作者 · 12,345 人阅读",
                      summary="dry-run 示例。", analysis=[{"label": "讲什么", "text": "示例。"}],
                      links=[{"name": "去长佩看", "url": "https://www.gongzicp.com/"}], tags=["示例"])]


def run(ctx):
    if ctx.dry:
        return _fake()
    items, errors = [], []
    try:
        saowen.login(ctx.http)
    except Exception as e:
        errors.append(str(e))
    else:
        try:
            items.append(_saowen_pick(ctx))
        except Exception as e:
            log(f"  扫文小院：{e}")
            errors.append(str(e))

    first = "长佩" if ctx.date.toordinal() % 2 == 0 else "晋江"
    for platform in (first, "晋江" if first == "长佩" else "长佩"):
        try:
            items.append(_platform_pick(ctx, platform))
            break
        except Exception as e:
            log(f"  {platform}：{type(e).__name__}: {e}")
            errors.append(f"{platform}: {e}")
    if not items:
        raise RuntimeError("；".join(errors))
    return items
