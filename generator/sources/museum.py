"""大都会博物馆 Open Access API：随机取一件有图、公有领域、没推过的作品。"""
from common import log

BASE = "https://collectionapi.metmuseum.org/public/collection"
PAINTING_DEPTS = [11, 21, 6, 15]  # 欧洲绘画、现代艺术、亚洲艺术、雷曼收藏
PHOTO_DEPTS = [19]
INSTRUMENT_DEPT = 18

FAKE = {
    "objectID": 436535, "title": "Wheat Field with Cypresses", "artistDisplayName": "Vincent van Gogh",
    "objectDate": "1889", "medium": "Oil on canvas", "department": "European Paintings",
    "primaryImageSmall": "https://images.metmuseum.org/CRDImages/ep/web-large/DP-42549-001.jpg",
    "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/DP-42549-001.jpg",
    "objectURL": "https://www.metmuseum.org/art/collection/search/436535", "classification": "Paintings",
}


def _search(ctx, **params):
    r = ctx.http.get(f"{BASE}/v1.1/search", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _obj(ctx, oid):
    r = ctx.http.get(f"{BASE}/v1/objects/{oid}", timeout=30)
    r.raise_for_status()
    return r.json()


def random_object(ctx, kind, query="*"):
    """kind: painting / photo / instrument。返回作品信息 dict，找不到返回 None。"""
    if ctx.dry:
        return FAKE
    depts = {"painting": PAINTING_DEPTS, "photo": PHOTO_DEPTS, "instrument": [INSTRUMENT_DEPT]}[kind]
    seen = set(ctx.seen("artwork"))
    for attempt in range(4):
        dept = ctx.rng.choice(depts)
        params = {"q": query, "hasImages": "true", "departmentId": dept, "limit": 1}
        if kind != "instrument":
            params["isHighlight"] = "true"  # 只要馆藏精品
        try:
            total = _search(ctx, **params).get("total") or 0
            if not total:
                continue
            params.update(limit=20, offset=ctx.rng.randrange(max(total - 20, 1)))
            ids = _search(ctx, **params).get("objectIDs") or []
        except Exception as e:
            log(f"  大都会搜索失败：{e}")
            continue
        ctx.rng.shuffle(ids)
        for oid in ids[:8]:
            if oid in seen:
                continue
            try:
                o = _obj(ctx, oid)
            except Exception:
                continue
            if not (o.get("isPublicDomain") and o.get("primaryImageSmall")):
                continue
            if kind == "painting" and dept != 11 and not (o.get("classification") or "").lower().startswith("painting"):
                continue  # 亚洲艺术、现代艺术部门里也有陶瓷、纺织品，只要绘画
            return o
    return None
