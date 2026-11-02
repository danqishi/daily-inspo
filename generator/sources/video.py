"""视频候选：搜索 → 过滤推过的 → 用 B 站 / YouTube 公开接口补全封面、简介、播放量并检查是否失效。"""
import re

from common import link_alive, log, platform_of

VIDEO_DOMAINS = ["bilibili.com", "youtube.com", "douyin.com", "xiaohongshu.com", "vimeo.com"]
VIDEO_URL = re.compile(r"bilibili\.com/video/|b23\.tv/|youtube\.com/(watch|shorts/)|youtu\.be/|"
                       r"douyin\.com/(video|note)/|xiaohongshu\.com/(explore|discovery/item)/|vimeo\.com/\d+")
BVID = re.compile(r"BV[0-9A-Za-z]{10}")
YTID = re.compile(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})")


def _bilibili(ctx, url):
    m = BVID.search(url)
    if not m:
        return None
    try:
        j = ctx.http.get("https://api.bilibili.com/x/web-interface/view",
                         params={"bvid": m.group(0)}, timeout=20).json()
    except Exception:
        return None
    if j.get("code") != 0:
        return {"alive": False}
    d = j["data"]
    return {"alive": True, "title": d.get("title"), "desc": (d.get("desc") or "")[:300],
            "cover": (d.get("pic") or "").replace("http://", "https://"),
            "author": (d.get("owner") or {}).get("name"), "views": (d.get("stat") or {}).get("view"),
            "url": f"https://www.bilibili.com/video/{m.group(0)}"}


def _youtube(ctx, url):
    m = YTID.search(url)
    if not m:
        return None
    vid = m.group(1)
    try:
        r = ctx.http.get("https://www.youtube.com/oembed",
                         params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}, timeout=20)
    except Exception:
        return None
    if r.status_code in (400, 401, 403, 404):
        return {"alive": False}
    j = r.json() if r.ok else {}
    return {"alive": True, "title": j.get("title"), "author": j.get("author_name"),
            "cover": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", "url": f"https://www.youtube.com/watch?v={vid}"}


def enrich(ctx, url):
    if ctx.dry:
        return {"alive": True, "cover": "https://images.metmuseum.org/CRDImages/ep/web-large/DP-42549-001.jpg",
                "author": "示例 UP 主", "views": 123456}
    info = _bilibili(ctx, url) or _youtube(ctx, url)
    if info is None:
        info = {"alive": link_alive(ctx.http, url)}
    return info


def candidates(ctx, seen_key, queries, limit=12):
    """queries: [(query, kwargs)]。返回去重、补全后的候选列表。"""
    seen = set(ctx.seen(seen_key))
    pool, urls = [], set()
    for q, kw in queries:
        kw = {"domains": VIDEO_DOMAINS, **kw}
        for r in ctx.search(q, **kw)["results"]:
            url = r.get("url", "")
            if not VIDEO_URL.search(url) or url in seen or url in urls:
                continue
            urls.add(url)
            pool.append({"title": r.get("title", ""), "url": url, "snippet": (r.get("content") or "")[:300]})
    out = []
    for c in pool:
        if len(out) >= limit:
            break
        info = enrich(ctx, c["url"])
        if not info.get("alive"):
            log(f"  失效，跳过：{c['url']}")
            continue
        if info.get("url") and info["url"] in seen:
            continue
        c.update({k: v for k, v in info.items() if v})
        c["platform"] = platform_of(c["url"])
        out.append(c)
    return out


def describe(cands):
    lines = []
    for i, c in enumerate(cands):
        extra = []
        if c.get("author"):
            extra.append(f"作者：{c['author']}")
        if c.get("views"):
            extra.append(f"播放：{c['views']}")
        lines.append(f"[{i}] {c['platform']}｜{c['title']}｜{'｜'.join(extra)}\n    简介：{c.get('desc') or c['snippet']}")
    return "\n".join(lines)


def subtitle(c):
    parts = [c.get("platform", "")]
    if c.get("author"):
        parts.append(c["author"])
    if c.get("views"):
        v = c["views"]
        parts.append(f"{v / 10000:.1f} 万播放" if v >= 10000 else f"{v} 播放")
    return " · ".join(p for p in parts if p)
