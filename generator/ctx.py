"""一次运行的上下文：日期、状态（去重记录等）、HTTP、模型、搜索。"""
import random

import requests

from common import GEN, UA, load_json, save_json
from llm import LLM
from search import Search


class Ctx:
    def __init__(self, date, dry, site_dir):
        self.date = date
        self.dry = dry
        self.site = site_dir
        self.state_path = GEN / "state.json"
        self.state = load_json(self.state_path, {})
        self.http = requests.Session()
        self.http.headers["User-Agent"] = UA
        self.llm = LLM(dry)
        self.search = Search(self.http, dry)
        self.rng = random.Random(date.toordinal())

    @property
    def date_str(self):
        return self.date.isoformat()

    def seen(self, key):
        return self.state.setdefault("seen", {}).setdefault(key, [])

    def mark_seen(self, key, value, cap=1000):
        lst = self.seen(key)
        lst.append(value)
        del lst[:-cap]

    def rotate(self, options, offset=0):
        """按日期轮换，每天换一个。"""
        return options[(self.date.toordinal() + offset) % len(options)]

    def save_state(self):
        if not self.dry:
            save_json(self.state_path, self.state)
