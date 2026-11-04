"""✒️ 每天 1 句文案：诗句、台词、语录、书里的句子都可以，必须写明出处。
可以和当天推荐的电影有关，也可以无关；只读电影栏目的结果，不影响它。
出处用搜索核实：搜索结果里要能找到这句话、而且同一条结果里提到作者或作品，否则换一句。"""
import re

from common import BASE_SYSTEM, load_json, log, make_item

ID, NAME, EMOJI = "quote", "每日一句", "✒️"
DAYS = range(7)
ATTEMPTS = 3

# 按日期轮换类型，避免天天都是古诗
KINDS = ["中国古典诗词", "外国诗歌", "电影台词，或导演、演员说过的话", "小说或散文里的句子",
         "现当代中文诗歌或散文", "哲学家、艺术家、作家的语录", "不限类型"]

TASK = """今天请推荐一句文案（侧重类型：{kind}）。
{film_note}
要求：
- 好看、耐读，适合抄在本子上或者配在视频里；不要鸡汤、不要网络段子。
- 必须是真实存在的原句，出处准确（作者、作品，能写篇名/章节就写）。拿不准的不要选，宁可选一句你非常确定的。
- 不要编造、不要改写原文，不要选“网传是某某说的”但其实出处可疑的句子。
- 不要选最近推荐过的：{recent}。
{retry_note}
输出 JSON：
{{"text": "原文（外文就写外文原文）", "translation": "如果原文不是中文，给一个中文译文（注明是通行译本还是意译）；中文原文就写空字符串",
  "author": "作者（中文名）", "author_original": "作者原名（中文作者就和上面一样）",
  "work": "出自哪部作品（书名/诗名/电影名），中文", "work_original": "作品原名", "detail": "篇章、场景或年份等更细的出处，拿不准就写空字符串",
  "film_related": true 或 false（是否和今天的电影有关）,
  "note": "两三句话：这句话的背景、好在哪里；如果和今天的电影有关，说说关系在哪",
  "tags": ["2–3 个"]}}"""


def _squash(s):
    return re.sub(r"[\s\W_]+", "", str(s or "")).lower()


def _today_film(ctx):
    """今天电影栏目的结果：同一次运行里直接拿，单独重跑这一栏时从当天的日报文件里读。"""
    film = getattr(ctx, "today_film", None)
    if film:
        return film
    day = load_json(ctx.site / "data" / f"{ctx.date_str}.json", {})
    for s in day.get("sections", []):
        if s.get("id") == "film" and s.get("status") == "ok":
            items = [it for it in s.get("items", []) if it.get("subtitle", "").startswith("电影")]
            if items:
                return {"title": items[0]["title"], "subtitle": items[0]["subtitle"], "summary": items[0].get("summary", "")}
    return None


def _verify(ctx, q):
    """搜原句，同一条结果里既有这句话又有作者或作品才算出处对得上。返回来源网页 {title, url} 或 None。"""
    text = _squash(q.get("text"))
    if len(text) < 4:
        return None
    key = text[:20]  # 长句子各网站断句、标点不同，取开头一段比
    who = [_squash(x) for x in (q.get("author"), q.get("author_original"), q.get("work"), q.get("work_original")) if x]
    # 外文作者名常常只写姓
    who += [_squash(x.split()[-1]) for x in (q.get("author_original"),) if x and " " in x]
    who = [w for w in who if len(w) >= 2]
    for query in (f"\"{q.get('text')}\" {q.get('author', '')}", f"{q.get('text')} {q.get('work', '')}"):
        for r in ctx.search(query, max_results=8)["results"]:
            body = _squash(r.get("title", "") + r.get("content", ""))
            if key in body and any(w in body for w in who):
                return {"title": r.get("title", ""), "url": r.get("url", "")}
    return None


def run(ctx):
    if ctx.dry:
        return [make_item(title="示例文案", subtitle="—— 示例作者《示例作品》", summary="dry-run 示例。")]
    recent = ctx.seen("quotes")
    film = None
    try:
        film = _today_film(ctx)
    except Exception as e:
        log(f"  没读到今天的电影：{e}")
    film_note = (f"今天推荐的电影是：{film['title']}（{film['subtitle']}）——{film['summary']}\n"
                 "如果有特别贴切的句子（片中台词、导演说过的话、和电影主题呼应的诗文）可以选它，没有就不必硬凑，选一句本身好的。"
                 if film else "")
    kind = ctx.rotate(KINDS)
    notes = []
    for attempt in range(ATTEMPTS):
        q = ctx.llm.json(BASE_SYSTEM, TASK.format(
            kind=kind, film_note=film_note, recent="、".join(recent[-60:]) or "无",
            retry_note=("注意：" + "；".join(notes) + "。请换一句。\n") if notes else ""))
        if not isinstance(q, dict) or not q.get("text") or not q.get("author"):
            notes.append("上次没给出原文或作者")
            continue
        if _squash(q["text"])[:20] in [_squash(r)[:20] for r in recent]:
            notes.append(f"「{q['text'][:20]}」最近推荐过了")
            continue
        src = _verify(ctx, q)
        if not src:
            notes.append(f"「{q['text'][:30]}」（{q.get('author')}）搜不到可靠出处")
            log(f"  出处没核实到：{q['text'][:40]} / {q.get('author')}")
            continue
        break
    else:
        raise RuntimeError("今天的文案出处都没核实成功：" + "；".join(notes))

    ctx.mark_seen("quotes", q["text"])
    work = q.get("work", "")
    if q.get("work_original") and _squash(q["work_original"]) != _squash(work):
        work += f"（{q['work_original']}）"
    author = q["author"]
    if q.get("author_original") and _squash(q["author_original"]) != _squash(author):
        author += f" {q['author_original']}"
    analysis = []
    if q.get("translation"):
        analysis.append({"label": "译文", "text": q["translation"]})
    analysis.append({"label": "出处", "text": "，".join(x for x in (author, f"《{work}》" if work else "", q.get("detail", "")) if x)})
    if q.get("note"):
        analysis.append({"label": "和今天的电影" if q.get("film_related") and film else "说说这句", "text": q["note"]})
    links = [{"name": "出处来源", "url": src["url"]}] if src.get("url") else []
    return [make_item(
        title=q["text"], subtitle=f"—— {q['author']}《{q.get('work', '')}》" if q.get("work") else f"—— {q['author']}",
        analysis=analysis, links=links, tags=q.get("tags", []),
        source_note=f"出处已通过搜索核实（{src.get('title', '')[:40]}）；译文和解读由 AI 整理。")]
