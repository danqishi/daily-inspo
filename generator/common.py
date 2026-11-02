"""共用的小工具：日志、JSON 读写、链接处理。"""
import json
import re
import time
from datetime import timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "generator"
BJ = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

BASE_SYSTEM = (
    "你是一位审美很好、懂短视频、设计和音乐的中文编辑，在为一位上班族写每日灵感日报。"
    "读者想提升审美、学习 AI 视频制作，基础不深，所以要说人话：具体、口语化，少用术语，用到术语就顺手解释。"
    "不要空话套话，不要编造你不确定的事实（数据、日期、人名），拿不准就不写。只输出 JSON。"
)
VIDEO_NOTE = "AI 没有看过视频本身，解读根据标题、简介和网上的公开评价整理，细节以视频为准。"


LOG_LINES = []  # 当天的运行记录，最后存到 docs/data/log/，方便排查


def log(*args):
    line = " ".join(str(a) for a in (time.strftime("%H:%M:%S"), *args))
    LOG_LINES.append(line)
    print(line, flush=True)


def load_json(path, default):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


SEARCH_SITES = {
    "bilibili": ("B站", "https://search.bilibili.com/all?keyword={}"),
    "youtube": ("YouTube", "https://www.youtube.com/results?search_query={}"),
    "douyin": ("抖音", "https://www.douyin.com/search/{}"),
    "xiaohongshu": ("小红书", "https://www.xiaohongshu.com/search_result?keyword={}"),
    "qqmusic": ("QQ音乐", "https://y.qq.com/n/ryqq/search?w={}"),
    "netease": ("网易云", "https://music.163.com/#/search/m/?s={}"),
    "pinterest": ("Pinterest", "https://www.pinterest.com/search/pins/?q={}"),
    "huaban": ("花瓣", "https://huaban.com/search?q={}"),
    "behance": ("Behance", "https://www.behance.net/search/projects?search={}"),
}


def search_link(site, keyword):
    name, tpl = SEARCH_SITES[site]
    return {"name": f"在{name}搜索", "url": tpl.format(quote(keyword))}


PLATFORMS = {
    "bilibili.com": "B站", "b23.tv": "B站", "youtube.com": "YouTube", "youtu.be": "YouTube",
    "douyin.com": "抖音", "xiaohongshu.com": "小红书", "xhslink.com": "小红书",
    "vimeo.com": "Vimeo", "weibo.com": "微博",
}


def platform_of(url):
    host = urlparse(url).netloc.lower()
    for domain, name in PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host.removeprefix("www.")


def link_alive(http, url):
    """只把明确的 404/410 和连不上算失效；很多平台会拦机器人（403/412），不算失效。"""
    try:
        r = http.get(url, timeout=15, allow_redirects=True, stream=True)
        r.close()
        return r.status_code not in (404, 410)
    except requests.RequestException:
        return False


def norm_analysis(raw):
    """把模型给的 analysis 统一成 [{label, text}]。"""
    out = []
    for a in raw or []:
        if isinstance(a, dict) and a.get("text"):
            out.append({"label": str(a.get("label", "")).strip(), "text": str(a["text"]).strip()})
        elif isinstance(a, str) and a.strip():
            out.append({"label": "", "text": a.strip()})
    return out


def grounded(name, sources):
    """name 是否真的出现在给模型看的资料里（去掉空格和标点再比），用来挡住模型编出来的梗和歌名。"""
    def squash(s):
        return re.sub(r"[\s\W_]+", "", str(s)).lower()
    key = squash(name)
    return len(key) >= 2 and any(key in squash(s) for s in sources)


def as_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def make_item(**kw):
    item = {"title": "", "subtitle": "", "summary": "", "analysis": [], "links": [],
            "images": [], "tags": [], "source_note": ""}
    item.update({k: v for k, v in kw.items() if v is not None})
    item["analysis"] = norm_analysis(item["analysis"])
    item["tags"] = [str(t).strip("# ") for t in item["tags"] if str(t).strip()][:6]
    return item
