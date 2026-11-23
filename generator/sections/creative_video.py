"""✨ 每天 1 条非 AI 的实拍 / 动画创意短片，面向剪辑师找可复用灵感。宁缺毋滥：没有达标的就不推。

信源：
- Vimeo Staff Picks 官方 RSS（直接抓，不花搜索次数；oEmbed 补全完整简介和时长）
- Tavily 限定专业站点搜索：NOWNESS、Ads of the World、新片场 / 场库、数英（后两个 403 拦脚本，只能靠搜索）
卡片字段：tags（创意维度）/ duration / title / highlight / techniques×2 / use_case / url，
存在 item["breakdown"]，同时映射到通用卡片字段，前端和收藏不用改。
"""
import html
import re
import xml.etree.ElementTree as ET

from common import BASE_SYSTEM, VIDEO_NOTE, as_int, link_alive, log, make_item, search_link
from sources.images import save_image

ID, NAME, EMOJI = "creative_video", "创意视频", "✨"
DAYS = range(7)

DIMENSIONS = ["视觉与美术", "剧情与叙事", "剪辑与节奏", "声音与声画", "营销与商业", "形式与媒介"]

STAFF_PICKS_RSS = "https://vimeo.com/channels/staffpicks/videos/rss"
PRO_SITES = {  # 域名 → 显示名
    "nowness.com": "NOWNESS", "adsoftheworld.com": "Ads of the World",
    "xinpianchang.com": "新片场", "digitaling.com": "数英",
}
# 作品详情页（排除首页、列表页、文章页）
PRO_URL = re.compile(r"nowness\.com/(?:[a-z]{2}/)?(?:story|series)/[\w-]+|adsoftheworld\.com/campaigns/[\w-]+|"
                     r"xinpianchang\.com/a\d+|digitaling\.com/projects/\d+")
VIMEO_ID = re.compile(r"vimeo\.com/(?:channels/[\w-]+/|video/)?(\d{6,})")

# 按日期轮换搜索方向（对应 6 个维度），中文查新片场 / 数英，英文查 NOWNESS / Ads of the World
THEMES = [
    ("视觉 美术 构图 色彩 创意短片", "visually striking short film art direction"),
    ("高概念 微电影 反转 无台词", "high concept short film no dialogue"),
    ("剪辑 节奏 蒙太奇 创意短片", "editing montage match cut short film"),
    ("声音设计 声画 创意短片", "sound design driven short film"),
    ("品牌 TVC 创意 广告片", "brand commercial film campaign"),
    ("一镜到底 伪纪录片 实验短片", "one take mockumentary experimental short film"),
]

# 标题 / 简介里出现这些就直接剔除（AI 生成、教程、口播等），模型那边还会再判一次
BLOCK = re.compile(r"\bAI\b|AIGC|AI生成|AI 生成|人工智能生成|Sora|Midjourney|Runway|Stable Diffusion|Kling|可灵|即梦|"
                   r"教程|tutorial|how to|教你|整蛊|prank|口播|reaction|模板|卡点", re.I)

TASK = f"""你是资深影视剪辑师的选片助手。从候选中挑出 **1 条** 最值得剪辑师学习、能借鉴手法的非 AI 实拍或动画创意短片。宁缺毋滥。

必须明显命中以下 6 个创意维度中的至少 1 个：
1. 视觉与美术：独特构图、色彩情绪、实拍错位、混合媒介拼贴等
2. 剧情与叙事：高概念微电影、高级反转、无台词视觉叙事、切入点独特的微纪录片
3. 剪辑与节奏：匹配剪辑、蒙太奇、非线性结构、极致的节奏反差
4. 声音与声画：音效 / Foley 驱动剪辑、J/L-Cut 巧思、声画对位与留白
5. 营销与商业：有高级感的品牌 TVC、洞察犀利或包装新颖的商业短片
6. 形式与媒介：一镜到底、桌面电影、伪纪录片、画幅变化玩法

严格排除：AI 生成或 AI 辅助为卖点的视频、土味段子、猎奇整蛊、纯口播 / 访谈、软件教程、没有内容表达的纯模板卡点、预告片、幕后花絮。
优先 Vimeo Staff Picks、NOWNESS、Ads of the World、新片场 / 场库、数英这类专业信源。
如果没有一条明确达标，pick 填 -1。

重要：你看不到画面，只能看到标题和简介。techniques 要从简介里明确提到的信息出发，
或者写这类作品的典型做法并注明「从简介看」「这类片通常」，不要编具体镜头和台词。
每条 technique 要具体到剪辑师能直接上手试（说清怎么做、达到什么效果），不要写“画面精美”“节奏紧凑”这种空话。

输出 JSON：{{"pick": 候选序号或 -1, "reason_if_none": "pick 为 -1 时说明原因",
"tags": ["从 {'/'.join(DIMENSIONS)} 中选 1–2 个"],
"title": "中文片名（原片名）", "highlight": "一句话核心亮点：创意高级或巧妙在哪",
"techniques": ["可复用技法 1", "可复用技法 2"], "use_case": "适用参考场景，2–4 个简短关键词，用 / 分隔"}}"""


def _fmt_duration(sec):
    sec = as_int(sec, 0)
    if sec <= 0:
        return ""
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _blocked(c):
    return BLOCK.search(f"{c.get('title', '')} {c.get('desc', '')}")


def _vimeo_oembed(ctx, url):
    try:
        r = ctx.http.get("https://vimeo.com/api/oembed.json", params={"url": url}, timeout=20)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def _staff_picks(ctx, seen):
    if ctx.dry:
        return [{"title": "Souvenir", "url": "https://vimeo.com/1248536635", "source": "Vimeo Staff Picks",
                 "author": "示例作者", "duration": 873, "desc": "dry-run 示例简介。",
                 "cover": "https://images.metmuseum.org/CRDImages/ep/web-large/DP-42549-001.jpg"}]
    try:
        r = ctx.http.get(STAFF_PICKS_RSS, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        log(f"  Vimeo Staff Picks 抓取失败：{e}")
        return []
    ns = {"media": "http://search.yahoo.com/mrss/"}
    out = []
    for it in root.iter("item"):
        m = VIMEO_ID.search(it.findtext("link") or "")
        if not m:
            continue
        url = f"https://vimeo.com/{m.group(1)}"
        if url in seen:
            continue
        mc = it.find("media:content", ns)
        thumb = mc.find("media:thumbnail", ns) if mc is not None else None
        credit = mc.find("media:credit", ns) if mc is not None else None
        c = {"title": html.unescape(it.findtext("title") or ""), "url": url, "source": "Vimeo Staff Picks",
             "desc": html.unescape(re.sub(r"<[^>]+>", "", it.findtext("description") or "")),
             "duration": as_int(mc.get("duration"), 0) if mc is not None else 0,
             "cover": thumb.get("url") if thumb is not None else "",
             "author": credit.text if credit is not None else ""}
        out.append(c)
    log(f"  Vimeo Staff Picks：{len(out)} 条未推过")
    # 只给前 8 条补完整简介（RSS 里的简介被截断）
    for c in out[:8]:
        info = _vimeo_oembed(ctx, c["url"])
        if info.get("description"):
            c["desc"] = info["description"]
        c["duration"] = c["duration"] or info.get("duration", 0)
    return out


def _site_name(url):
    for domain, name in PRO_SITES.items():
        if domain in url:
            return name
    return "Vimeo" if "vimeo.com" in url else ""


def _searched(ctx, seen):
    zh, en = ctx.rotate(THEMES)
    queries = [(zh, ["xinpianchang.com", "digitaling.com"]),
               (en, ["nowness.com", "adsoftheworld.com", "vimeo.com"])]
    out, urls = [], set()
    for q, domains in queries:
        for r in ctx.search(q, domains=domains, time_range="year")["results"]:
            url = r.get("url", "").split("?")[0].split("#")[0]
            vm = VIMEO_ID.search(url)
            if vm:
                url = f"https://vimeo.com/{vm.group(1)}"
            elif not PRO_URL.search(url):
                continue
            if url in seen or url in urls:
                continue
            urls.add(url)
            out.append({"title": r.get("title", ""), "url": url, "source": _site_name(url),
                        "desc": (r.get("content") or "")[:500]})
    alive = []
    for c in out[:8]:
        if ctx.dry:
            alive.append(c)
            continue
        if "vimeo.com" in c["url"]:
            info = _vimeo_oembed(ctx, c["url"])
            if not info:
                log(f"  失效，跳过：{c['url']}")
                continue
            c.update({"desc": info.get("description") or c["desc"], "duration": info.get("duration", 0),
                      "author": info.get("author_name", ""), "cover": info.get("thumbnail_url", "")})
        elif not link_alive(ctx.http, c["url"]):
            log(f"  失效，跳过：{c['url']}")
            continue
        alive.append(c)
    return alive


def _describe(cands):
    lines = []
    for i, c in enumerate(cands):
        meta = [c["source"]]
        if c.get("author"):
            meta.append(f"作者：{c['author']}")
        if c.get("duration"):
            meta.append(f"时长：{_fmt_duration(c['duration'])}")
        desc = re.sub(r"\s+", " ", c.get("desc") or "")[:600]
        lines.append(f"[{i}] {c['title']}｜{'｜'.join(meta)}\n    简介：{desc}")
    return "\n".join(lines)


def run(ctx):
    seen = set(ctx.seen(ID))
    cands = [c for c in _staff_picks(ctx, seen) + _searched(ctx, seen) if not _blocked(c)]
    if not cands:
        raise RuntimeError("没有搜到可用的候选")
    fake = {"pick": 0, "tags": ["剪辑与节奏"], "title": "【示例】纪念品（Souvenir）", "highlight": "dry-run 示例亮点。",
            "techniques": ["示例技法 1", "示例技法 2"], "use_case": "示例 / 场景"}
    out = ctx.llm.json(BASE_SYSTEM, f"{TASK}\n\n候选：\n{_describe(cands)}", fake=fake)
    idx = as_int(out.get("pick"), -1)
    if not 0 <= idx < len(cands):
        raise RuntimeError(f"今天没有达标的候选（宁缺毋滥）：{out.get('reason_if_none', '')}"[:200])
    c = cands[idx]
    ctx.mark_seen(ID, c["url"])

    tags = [t for t in out.get("tags", []) if t in DIMENSIONS][:2] or [str(t) for t in out.get("tags", [])][:2]
    techniques = [str(t) for t in out.get("techniques", []) if str(t).strip()][:2]
    breakdown = {"tags": tags, "duration": _fmt_duration(c.get("duration")), "title": out.get("title") or c["title"],
                 "highlight": out.get("highlight", ""), "techniques": techniques,
                 "use_case": out.get("use_case", ""), "url": c["url"]}

    images = []
    if c.get("cover"):
        src = save_image(ctx, c["cover"], ID)
        if src:
            images.append({"src": src, "caption": "视频封面", "credit": c["source"]})
    analysis = [{"label": f"可复用技法 {i + 1}", "text": t} for i, t in enumerate(techniques)]
    if breakdown["use_case"]:
        analysis.append({"label": "适用参考场景", "text": breakdown["use_case"]})
    subtitle = " · ".join(p for p in (c["source"], c.get("author"), breakdown["duration"] and f"时长 {breakdown['duration']}") if p)
    links = [{"name": f"去 {c['source']} 看原片", "url": c["url"]}, search_link("bilibili", c["title"])]

    item = make_item(title=breakdown["title"], subtitle=subtitle, summary=breakdown["highlight"],
                     analysis=analysis, links=links, images=images, tags=tags, source_note=VIDEO_NOTE)
    item["badge"] = " / ".join(tags) if tags else None
    item["original_title"] = c["title"]
    item["breakdown"] = breakdown
    return [item]
