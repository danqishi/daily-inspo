"""扫文小院（saowen.net）：登录后读书单、标签和书评。账号放在环境变量 SAOWEN_EMAIL / SAOWEN_PASSWORD。"""
import html
import os
import re
from urllib.parse import quote

BASE = "http://saowen.net"


def _text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def login(http):
    email, password = os.environ.get("SAOWEN_EMAIL"), os.environ.get("SAOWEN_PASSWORD")
    if not (email and password):
        raise RuntimeError("没有设置 SAOWEN_EMAIL / SAOWEN_PASSWORD")
    http.post(f"{BASE}/users/login", timeout=30, data={
        "_method": "POST", "data[User][email]": email,
        "data[User][password]": password, "data[User][remember]": "1"})
    r = http.get(f"{BASE}/novels", timeout=30)
    if "/users/login" in r.url:
        raise RuntimeError("扫文小院登录失败，检查账号密码")


def tag_list_url(tag, page=1):
    """某个标签下的作品，按平均分从高到低。"""
    return f"{BASE}/noveltags/search/page:{page}/sort:Novel.pseudo_avg/direction:desc?search={quote(tag)}"


def all_list_url(page=1):
    return f"{BASE}/novels/index/page:{page}/sort:Novel.pseudo_avg/direction:desc"


def _tags(fragment):
    return {html.unescape(name).strip(): int(n) for name, n in
            re.findall(r'class="taglink"[^>]*>([^<]+)</a>\s*\((\d+)\)', fragment)}


def parse_list(page_html):
    out = []
    for li in re.findall(r'<li class="item[^"]*" data-novelid="\d+">.*?</li>', page_html, flags=re.S):
        nid = re.search(r'data-novelid="(\d+)"', li).group(1)
        title = re.search(r'class="novellink"[^>]*>《?(.*?)》?</a>', li, flags=re.S)
        author = re.search(r'class="authorlink"[^>]*>(.*?)</a>', li, flags=re.S)
        score = re.search(r'class="ratenumber">([\d.]+)<', li)
        raters = re.search(r"共(\d+)人评分", li)
        extend = re.search(r'class="extend-info">(.*?)</span>', li, flags=re.S)
        # 自己在扫文上标过状态的书，按钮区会变成“看过/想看 … 修改 删除”
        status = re.search(r'class="my-status[^"]*">(.*?)</div>', li, flags=re.S)
        marked = bool(status) and ("修改" in _text(status.group(1)) or "删除" in _text(status.group(1)))
        out.append({
            "id": nid,
            "title": _text(title.group(1)) if title else "",
            "author": _text(author.group(1)) if author else "",
            "score": float(score.group(1)) if score else 0.0,
            "raters": int(raters.group(1)) if raters else 0,
            "info": _text(extend.group(1)).split("/") if extend else [],
            "tags": _tags(li),
            "marked": marked,
        })
    return out


def fetch_list(http, url):
    r = http.get(url, timeout=30)
    r.encoding = "utf-8"
    return parse_list(r.text)


def fetch_detail(http, nid):
    """详情页：完整的 20 个读者标签、作品信息、首发地址。"""
    r = http.get(f"{BASE}/novels/view/{nid}", timeout=30)
    r.encoding = "utf-8"
    page = r.text
    info = {_text(k).rstrip(" :"): _text(v) for k, v in
            re.findall(r"<li><small>(.*?)</small>(.*?)</li>", page, flags=re.S)}
    source = ""
    m = re.search(r"发表地址 : </small>(.*?)</li>", page, flags=re.S)
    href = re.search(r'href="(https?://[^"]+)"', m.group(1)) if m else None
    if href and "saowen.net" not in href.group(1):
        source = html.unescape(href.group(1))
    return {"info": info, "tags": _tags(page), "source_url": source}


def fetch_reviews(http, nid, limit=10):
    """按“有用度”排序的前几条书评，只取正文。"""
    r = http.get(f"{BASE}/Readstatuses/novelReviews/{nid}/0/p_ratio/1/limit:{limit}", timeout=30,
                 headers={"X-Requested-With": "XMLHttpRequest"})
    r.encoding = "utf-8"
    page = re.sub(r"<script.*?</script>", "", r.text, flags=re.S)
    items = re.split(r"<li[ >]", page)[1:] or [page]
    reviews = []
    for it in items:
        t = re.sub(r"▲有用.*$", "", _text("<li " + it)).strip()
        if len(t) > 15:
            reviews.append(t[:600])
    return reviews[:limit]


def novel_url(nid):
    return f"{BASE}/novels/view/{nid}"


def find(http, title, author):
    """在扫文小院里按书名找同一本书（作者也要对上），找不到返回 None。"""
    r = http.get(f"{BASE}/novels/search", params={"q": title}, timeout=30)
    r.encoding = "utf-8"
    for n in parse_list(r.text):
        if n["author"] == author and re.sub(r"\(.*?\)|（.*?）", "", n["title"]).strip() == title.strip():
            return n
    return None
