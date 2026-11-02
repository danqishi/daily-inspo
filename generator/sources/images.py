"""图片：下载压缩到仓库里、从维基共享资源找图、用看图模型检查图片是否对题。"""
import hashlib
import io
from urllib.parse import urlparse

from PIL import Image

from common import BASE_SYSTEM, log

MAX_SIDE = 1200
MIN_SIDE = 300


def fetch_image(ctx, url):
    """下载图片并压缩成 JPEG 字节；太小或失败返回 None。"""
    try:
        r = ctx.http.get(url, timeout=30, headers={"Referer": f"{urlparse(url).scheme}://{urlparse(url).netloc}/"})
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        if min(im.size) < MIN_SIDE:
            return None
        im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
        return buf.getvalue()
    except Exception as e:  # 图片失败不影响整条内容
        log(f"  图片下载失败 {url[:80]}：{e}")
        return None


def write_image(ctx, data, url, name_hint="img"):
    """把图片存到 docs/img/年-月/，返回网站里的相对路径。"""
    digest = hashlib.md5(url.encode()).hexdigest()[:8]
    rel = f"img/{ctx.date_str[:7]}/{ctx.date_str}-{name_hint}-{digest}.jpg"
    (ctx.site / rel).parent.mkdir(parents=True, exist_ok=True)
    (ctx.site / rel).write_bytes(data)
    return rel


def save_image(ctx, url, name_hint="img"):
    if ctx.dry:
        return url  # dry-run 直接用原图链接，不下载
    data = fetch_image(ctx, url)
    return write_image(ctx, data, url, name_hint) if data else None


def wikimedia_images(ctx, query, n=6):
    """在维基共享资源搜图，返回 [{url, page, credit}]。"""
    if ctx.dry:
        return []
    try:
        r = ctx.http.get("https://commons.wikimedia.org/w/api.php", timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": query,
            "gsrnamespace": 6, "gsrlimit": n, "prop": "imageinfo",
            "iiprop": "url|mime", "iiurlwidth": 1000,
        })
        pages = (r.json().get("query") or {}).get("pages") or {}
    except Exception as e:
        log(f"  维基共享资源搜索失败：{e}")
        return []
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime", "").startswith(("image/jpeg", "image/png", "image/svg", "image/webp")) and info.get("thumburl"):
            out.append({"url": info["thumburl"], "page": info.get("descriptionurl", ""),
                        "credit": "Wikimedia Commons"})
    return out


def pick_images(ctx, candidates, topic, want=4, name_hint="img", max_checks=8):
    """逐张检查候选图是否真的体现了 topic，留下 want 张，每张配一句说明。"""
    if ctx.dry:
        return [{"src": c["url"], "caption": f"示例：{topic}", "credit": c.get("credit", "")} for c in candidates[:want]]
    chosen, checked, rejected = [], 0, 0
    for c in candidates:
        if len(chosen) >= want or checked >= max_checks:
            break
        data = fetch_image(ctx, c["url"])
        if not data:
            continue
        checked += 1
        caption = ""
        if ctx.llm.can_see:
            try:
                v = ctx.llm.json(
                    BASE_SYSTEM,
                    f"这张图是否是「{topic}」的典型、清晰的例子？如果是网页截图、文字为主、模糊、无关、"
                    "主体不是它（比如一堆东西里只有一小部分是它）或水印很重，算不合格。\n"
                    '输出 JSON：{"ok": true 或 false, "caption": "一句中文（20 字以内）说图里哪里体现了它"}',
                    image=data,
                )
                if not v.get("ok"):
                    rejected += 1
                    continue
                caption = v.get("caption") or ""
            except Exception as e:
                log(f"  看图检查失败（不检查直接用）：{type(e).__name__}: {e}")
        chosen.append({"src": write_image(ctx, data, c["url"], name_hint), "caption": caption,
                       "credit": c.get("credit", ""), "page": c.get("page", "")})
    log(f"  配图：检查 {checked} 张，不合格 {rejected} 张，留下 {len(chosen)} 张")
    return chosen
