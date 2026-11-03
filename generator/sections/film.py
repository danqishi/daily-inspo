"""🎬 每天 1 位导演 + 他/她的 1 部电影 + 1 首电影配乐。
电影要在维基百科上查得到、导演对得上，而且不能是全世界都看过的那种（用维基百科语言版本数粗略判断）；
配乐出名的也可以，但要在网易云音乐搜得到，避免模型编造曲名。"""
import io
import re
import time

import requests
from PIL import Image

from common import BASE_SYSTEM, log, make_item, search_link
from sources.images import write_image

ID, NAME, EMOJI = "film", "导演、电影和配乐", "🎬"
DAYS = range(7)

WIKI = "https://en.wikipedia.org"
# 维基媒体要求 User-Agent 写明项目和联系方式，否则图片服务器容易返回 429
WIKI_UA = {"User-Agent": "daily-inspo/1.0 (https://github.com/danqishi/daily-inspo; personal daily digest)"}
MAX_LANGS = 55      # 维基百科语言版本超过这个数，基本就是世界级名片，换一部
ATTEMPTS = 3

# 按日期轮换地区，避免总推同几个国家
REGIONS = ["日本", "法国", "韩国", "中国台湾或香港", "伊朗或中东", "意大利或西班牙", "北欧", "东欧或俄罗斯",
           "拉丁美洲", "英国或爱尔兰", "美国独立电影", "德国或奥地利", "中国大陆", "东南亚或南亚", "不限地区"]

TASK = """今天请推荐（侧重地区：{region}）：
1. 一位导演（剧情片、纪录片、动画导演都可以）。不要选最近推荐过的：{recent_directors}。
2. 这位导演的一部电影。要求：口碑好、值得看，但**不要选全世界都知道的名片**（比如各大影史前 100 名、票房爆款、导演最出名的那一部），
   优先选影迷圈好评、普通观众不一定看过的作品。
3. 一首电影配乐（可以来自任何电影，不必是上面那部），要求：好听、有辨识度，出名的经典配乐也完全可以推，
   而且你要确定这首曲子真实存在、名字准确（写原版曲名，不要自己翻译）。不要选最近推荐过的：{recent_tracks}。
{retry_note}
读者想提升审美、学做视频，所以要多讲画面、镜头、声音这些看得见听得见的东西，少讲空泛的评价。不要编造你不确定的事实（获奖、年份、演员），拿不准就不写。

输出 JSON：
{{"director": {{"name_zh": "中文名", "name_en": "英文名或原名的拉丁写法", "country": "国家/地区",
   "summary": "一句话", "analysis": [{{"label": "风格", "text": "…"}}, {{"label": "常用手法", "text": "镜头、色彩、节奏、声音上的习惯"}}, {{"label": "代表作", "text": "…"}}, {{"label": "从 TA 身上学什么", "text": "做视频可以借鉴的地方"}}],
   "tags": ["2–4 个"]}},
 "film": {{"title_zh": "中文片名", "title_en": "英文片名（维基百科上的写法）", "year": 年份数字,
   "summary": "一句话，不剧透", "analysis": [{{"label": "讲什么", "text": "不剧透结局"}}, {{"label": "为什么值得看", "text": "…"}}, {{"label": "视听看点", "text": "画面、镜头、配乐上注意什么"}}, {{"label": "适合什么时候看", "text": "…"}}],
   "tags": ["2–4 个"]}},
 "score": {{"track": "曲名（原名）", "composer": "作曲（英文或拉丁写法）", "composer_native": "作曲的母语原名（比如 久石譲、坂本龍一、Ennio Morricone）", "film_zh": "出自哪部电影（中文）", "film_en": "英文片名",
   "summary": "一句话", "listen_for": "听的时候注意什么（乐器、旋律、情绪变化）", "scene": "这段音乐在片中大概用在什么情境（拿不准就写空字符串）",
   "tags": ["2–3 个"]}}}}"""


def _squash(s):
    return re.sub(r"[\s\W_]+", "", str(s or "")).lower()


def _wiki(ctx, path, params=None):
    """维基百科偶尔会限流返回空内容，重试两次。"""
    for i in range(3):
        try:
            return ctx.http.get(f"{WIKI}{path}", params=params, headers=WIKI_UA, timeout=20).json()
        except ValueError:
            time.sleep(3 * (i + 1))
    return {}


def _wiki_film(ctx, title_en, year, director_en):
    """在英文维基百科找这部电影，确认导演对得上。返回 {title, url, extract, image, langs} 或 None。"""
    r = _wiki(ctx, "/w/api.php", {"action": "query", "list": "search", "format": "json", "srlimit": 5,
                                   "srsearch": f"{title_en} {year} film {director_en}"})
    surname = _squash(director_en.split()[-1]) if director_en else ""
    for hit in (r.get("query") or {}).get("search", []):
        s = _wiki(ctx, f"/api/rest_v1/page/summary/{hit['title'].replace(' ', '_')}")
        extract = s.get("extract", "")
        if "film" not in extract.lower() or (surname and surname not in _squash(extract)):
            continue
        if _squash(title_en)[:6] not in _squash(hit["title"]):
            continue
        ll = _wiki(ctx, "/w/api.php", {"action": "query", "prop": "langlinks", "titles": hit["title"],
                                        "lllimit": "max", "format": "json"})
        langs = sum(len(p.get("langlinks", [])) for p in (ll.get("query") or {}).get("pages", {}).values())
        return {"title": hit["title"], "url": (s.get("content_urls") or {}).get("desktop", {}).get("page", ""),
                "extract": extract, "image": (s.get("originalimage") or {}).get("source", ""), "langs": langs}
    return None


def _netease_track(ctx, track, composers, film_en):
    """在网易云搜这首曲子，曲名对得上、作曲或专辑也对得上才算。返回 {id, name, artists, album} 或 None。"""
    names = [_squash(c.split()[-1] if re.match(r"^[A-Za-z .'-]+$", c) else c) for c in composers if c]
    for q in [f"{track} {c}" for c in composers if c] + [f"{track} {film_en}"]:
        try:
            # 不能用共用的会话：带上网易云的 NMTID cookie 后，搜索会返回不相关的热门歌
            r = requests.post("https://music.163.com/api/search/get", timeout=20,
                              headers={"Referer": "https://music.163.com/", "User-Agent": ctx.http.headers["User-Agent"]},
                              data={"s": q, "type": 1, "limit": 10}).json()
        except Exception as e:
            log(f"  网易云搜索失败：{e}")
            return None
        for s in (r.get("result") or {}).get("songs") or []:
            artists = [a["name"] for a in s.get("artists", [])]
            album = (s.get("album") or {}).get("name", "")
            name_ok = _squash(track) in _squash(s["name"]) or _squash(s["name"]) in _squash(track)
            who_ok = any(n and n in _squash(a) for n in names for a in artists)
            film_ok = _squash(film_en)[:6] in _squash(album) if film_en else False
            if name_ok and (who_ok or film_ok):
                return {"id": s["id"], "name": s["name"], "artists": artists, "album": album}
    return None


def _poster(ctx, url):
    """维基百科的海报只有低分辨率版本，不走通用图片下载的最小尺寸限制。"""
    url = url.split("?")[0]
    try:
        for i in range(3):
            r = requests.get(url, headers=WIKI_UA, timeout=30)
            if r.status_code != 429:
                break
            time.sleep(5 * (i + 1))
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return write_image(ctx, buf.getvalue(), url, name_hint="film")
    except Exception as e:
        log(f"  海报下载失败：{e}")
        return None


def _fake():
    return [make_item(title="示例导演", subtitle="导演", summary="dry-run 示例。"),
            make_item(title="《示例电影》", subtitle="电影", summary="dry-run 示例。"),
            make_item(title="示例配乐", subtitle="电影配乐", summary="dry-run 示例。")]


def run(ctx):
    if ctx.dry:
        return _fake()
    recent_directors = ctx.seen("film_directors")
    recent_tracks = ctx.seen("film_tracks")
    region = ctx.rotate(REGIONS)
    notes = []
    director = film = score = wiki = song = None
    for attempt in range(ATTEMPTS):
        out = ctx.llm.json(BASE_SYSTEM, TASK.format(
            region=region, recent_directors="、".join(recent_directors[-60:]) or "无",
            recent_tracks="、".join(recent_tracks[-60:]) or "无",
            retry_note=("注意：" + "；".join(notes) + "。请换一个。\n") if notes else ""))
        d, f, s = out.get("director") or {}, out.get("film") or {}, out.get("score") or {}

        if not wiki or film is None:
            w = _wiki_film(ctx, f.get("title_en", ""), f.get("year", ""), d.get("name_en", ""))
            if not w:
                notes.append(f"《{f.get('title_zh')}》({f.get('title_en')}) 在维基百科上没查到、或导演对不上，换一位导演和电影")
                log(f"  电影没核实到：{f.get('title_en')} / {d.get('name_en')}")
                continue
            if w["langs"] > MAX_LANGS:
                notes.append(f"《{f.get('title_zh')}》太出名了（{w['langs']} 种语言的维基百科），换一部不那么出名的")
                log(f"  电影太出名：{f.get('title_en')}（{w['langs']} 种语言）")
                continue
            director, film, wiki = d, f, w

        if not song:
            song = _netease_track(ctx, s.get("track", ""), [s.get("composer", ""), s.get("composer_native", "")],
                                  s.get("film_en", ""))
            if not song:
                notes.append(f"配乐「{s.get('track')}」在网易云上没找到，换一首确定存在的；导演和电影保持「{director.get('name_zh')}」《{film.get('title_zh')}》不变")
                log(f"  配乐没核实到：{s.get('track')} / {s.get('composer')}")
                continue
            score = s
        break

    items = []
    if director and film:
        ctx.mark_seen("film_directors", director.get("name_zh", ""))
        items.append(make_item(
            title=f"{director.get('name_zh', '')} {director.get('name_en', '')}".strip(),
            subtitle=f"导演 · {director.get('country', '')}", summary=director.get("summary", ""),
            analysis=director.get("analysis"), tags=director.get("tags", []),
            links=[search_link("bilibili", f"{director.get('name_zh', '')} 导演 解读"),
                   search_link("douban", director.get("name_zh", ""))]))
        images = []
        if wiki.get("image"):
            src = _poster(ctx, wiki["image"])
            if src:
                images.append({"src": src, "caption": f"《{film.get('title_zh', '')}》海报", "credit": "Wikipedia"})
        links = [search_link("douban", film.get("title_zh", "")), search_link("bilibili", f"{film.get('title_zh', '')} 解读")]
        if wiki.get("url"):
            links.append({"name": "维基百科", "url": wiki["url"]})
        items.append(make_item(
            title=f"《{film.get('title_zh', '')}》{film.get('title_en', '')}",
            subtitle=f"电影 · {director.get('name_zh', '')} · {film.get('year', '')}", summary=film.get("summary", ""),
            analysis=film.get("analysis"), images=images, links=links, tags=film.get("tags", []),
            source_note="电影已在维基百科核实；介绍由 AI 根据公开资料整理，细节以影片为准。"))
    if score and song:
        ctx.mark_seen("film_tracks", score.get("track", ""))
        analysis = [{"label": "听什么", "text": score.get("listen_for", "")}]
        if score.get("scene"):
            analysis.append({"label": "在片中", "text": score["scene"]})
        items.append(make_item(
            title=song["name"], subtitle=f"电影配乐 · {' / '.join(song['artists'])} · 《{score.get('film_zh', '')}》",
            summary=score.get("summary", ""), analysis=analysis, tags=score.get("tags", []),
            links=[{"name": "在网易云听", "url": f"https://music.163.com/#/song?id={song['id']}"},
                   search_link("qqmusic", f"{song['name']} {score.get('composer', '')}"),
                   search_link("bilibili", f"{score.get('film_zh', '')} 配乐 {song['name']}")]))
    if not items:
        raise RuntimeError("今天的导演、电影和配乐都没核实成功：" + "；".join(notes))
    return items
