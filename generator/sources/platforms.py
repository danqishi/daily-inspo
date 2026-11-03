"""长佩文学（gongzicp）和晋江文学城（jjwxc）的公开接口：取候选书和书的详情。"""
import html
import re

CP_API = "https://webapi.gongzicp.com/novel"
JJ_API = "https://app-cdn.jjwxc.net/androidapi/novelbasicinfo"

# 晋江的标签 id，用来换着筛选，扩大候选范围
JJ_TAGS = {"强强": 19, "情有独钟": 39, "天作之合": 52, "甜文": 124, "正剧": 263, "轻松": 262, "破镜重圆": 47,
           "仙侠修真": 68, "宫廷侯爵": 32, "娱乐圈": 64, "无限流": 83, "悬疑推理": 128, "灵异神怪": 26,
           "星际": 135, "年下": 21, "救赎": 329, "治愈": 265, "江湖": 35, "末世": 81, "HE": 318}


def _text(s):
    s = re.sub(r"<br\s*/?>|</p>", "\n", html.unescape(html.unescape(str(s or ""))))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", s)).strip()


def _num(s):
    m = re.search(r"[\d,]+", str(s or ""))
    return int(m.group(0).replace(",", "")) if m else 0


# ---------- 长佩 ----------

def cp_list(http, page, field):
    """纯爱、已完结；field：0 人气 1 收藏 3 更新时间 4 创建时间。"""
    j = http.get(f"{CP_API}/novelGetList", timeout=30, params={
        "page": page, "size": 10, "tid": 75, "process": 2, "field": field, "order": -1}).json()
    return [{"id": str(n["novel_id"]), "title": n["novel_name"], "author": n["novel_author"],
             "tags": n.get("novel_tags") or []} for n in (j.get("data") or {}).get("list", [])]


def cp_detail(http, nid):
    d = http.get(f"{CP_API}/novelInfo", params={"id": nid}, timeout=30).json().get("data") or {}
    return {
        "platform": "长佩", "id": str(nid), "title": d.get("novel_name", ""), "author": d.get("author_nickname", ""),
        "finished": d.get("novel_process") == "完结", "bl": "纯爱" in (d.get("type_list") or []),
        "clicks": int(d.get("read_total") or 0), "clicks_label": "人阅读",
        "words": int(d.get("novel_wordnumber") or 0),
        "tags": d.get("tag_list") or [], "category": "/".join(d.get("type_list") or []),
        "intro": _text(d.get("novel_info")), "url": f"https://www.gongzicp.com/novel-{nid}.html",
        "extra": f"评论 {d.get('comment_number', 0)} 条", "protagonists": "",
    }


# ---------- 晋江 ----------

def jj_list(http, page, sort_type, tag=None):
    """原创纯爱、已完结；sort_type：2 积分 4 收藏 3 最新发表 1 最近更新。不登录只能翻 10 页。"""
    params = {"xx2": 2, "ycx1": 1, "isfinish": 2, "sortType": sort_type, "page": page, "collectiontypes": "ors"}
    if tag:
        params["bq"] = tag
    t = http.get("https://www.jjwxc.net/bookbase.php", params=params, timeout=30).content.decode("gb18030", "replace")
    table = t[t.find('class="cytable"'):]
    out = []
    for nid, title in re.findall(r'href="onebook\.php\?novelid=(\d+)"[^>]*>([^<]+)</a>', table):
        out.append({"id": nid, "title": html.unescape(title).strip(), "author": "", "tags": []})
    return out


def jj_detail(http, nid):
    d = http.get(JJ_API, params={"novelId": nid}, timeout=30).json()
    score = d.get("novelReviewScore") or ""
    return {
        "platform": "晋江", "id": str(nid), "title": d.get("novelName", ""), "author": d.get("authorName", ""),
        "finished": str(d.get("novelStep")) == "2", "bl": "纯爱" in (d.get("novelClass") or ""),
        "clicks": _num(d.get("novip_clicks")), "clicks_label": "章均点击",
        "words": _num(d.get("novelSize")),
        "tags": [t for t in (d.get("novelTags") or "").split(",") if t], "category": d.get("novelClass", ""),
        "intro": _text(d.get("novelIntro")), "url": f"https://www.jjwxc.net/onebook.php?novelid={nid}",
        "extra": "；".join(x for x in (f"收藏 {d.get('novelbefavoritedcount', '')}",
                                       f"读者评分 {score}" if score else "", d.get("ageString", "")) if x),
        "protagonists": d.get("protagonist", ""),
    }
