"""每日灵感日报生成器。

用法：
  python generator/main.py                       生成今天（北京时间）的日报
  python generator/main.py --date 2026-11-03     生成指定日期
  python generator/main.py --only meme,artwork   只重新生成某几个栏目（合并进当天已有的内容）
  python generator/main.py --dry-run --site 临时目录   不调用任何接口，用假数据检查页面
"""
import argparse
import importlib
import sys
import time
from datetime import date, datetime
from pathlib import Path

from common import BJ, LOG_LINES, ROOT, load_json, log, save_json

SECTIONS = ["ai_video", "creative_video", "ai_news", "meme", "hot_music", "design_style", "music_style", "artwork", "film", "quote", "novel"]
WEEKDAYS = "一二三四五六日"


def section_meta(mod):
    return {"id": mod.ID, "name": mod.NAME, "emoji": mod.EMOJI}


def run_section(ctx, mod):
    log(f"{mod.EMOJI} {mod.NAME}")
    err = ""
    for attempt in (1, 2):
        try:
            items = mod.run(ctx)
            log(f"  完成，{len(items)} 条")
            return {**section_meta(mod), "status": "ok", "items": items}
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log(f"  第 {attempt} 次失败：{err}")
            if attempt == 1:
                time.sleep(10)
    return {**section_meta(mod), "status": "missing", "items": [], "note": "今天这一栏没生成出来", "error": err[:300]}


def day_status(sections):
    ok = sum(s["status"] == "ok" for s in sections)
    return "ok" if ok == len(sections) else ("failed" if ok == 0 else "partial")


def rebuild_index(site):
    days = []
    for f in sorted((site / "data").glob("????-??-??.json"), reverse=True):
        d = load_json(f, {})
        days.append({
            "date": d["date"], "weekday": d.get("weekday", ""), "status": d.get("status", "ok"),
            "items": [{"s": s["id"], "i": i, "t": it["title"], "g": it.get("tags", []), "m": it.get("summary", "")[:80]}
                      for s in d.get("sections", []) for i, it in enumerate(s.get("items", []))],
        })
    mods = [importlib.import_module(f"sections.{name}") for name in SECTIONS]
    save_json(site / "data" / "index.json", {
        "updated": datetime.now(BJ).isoformat(timespec="seconds"),
        "sections": [section_meta(m) for m in mods],
        "days": days,
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD，默认今天（北京时间）")
    p.add_argument("--only", help="只生成这些栏目，逗号分隔")
    p.add_argument("--force", action="store_true", help="当天已经生成过也重新生成")
    p.add_argument("--dry-run", action="store_true", help="不调用接口，用假数据")
    p.add_argument("--site", default=str(ROOT / "docs"), help="网站目录")
    args = p.parse_args()

    day = date.fromisoformat(args.date) if args.date else datetime.now(BJ).date()
    site = Path(args.site)
    day_path = site / "data" / f"{day.isoformat()}.json"
    existing = load_json(day_path, None)
    if existing and existing.get("status") == "ok" and not (args.force or args.only):
        log(f"{day} 已经生成过，跳过（要重新生成加 --force）")
        return 0

    only = set(args.only.split(",")) if args.only else None
    names = [n for n in SECTIONS if only is None or n in only]
    mods = [importlib.import_module(f"sections.{n}") for n in names]
    if only is None:
        mods = [m for m in mods if day.weekday() in m.DAYS]

    try:
        from ctx import Ctx
        ctx = Ctx(day, args.dry_run, site)
    except Exception as e:  # 比如 Key 没填：记一个“失败”的日报，网站上会提示
        log(f"初始化失败：{e}")
        if existing:  # 已有内容就不覆盖
            return 1
        sections = [{**section_meta(m), "status": "missing", "items": [], "note": "今天更新失败"} for m in mods]
        save_json(day_path, {"date": day.isoformat(), "weekday": f"周{WEEKDAYS[day.weekday()]}",
                             "status": "failed", "error": str(e)[:300], "sections": sections})
        rebuild_index(site)
        return 1

    log(f"生成 {day}（周{WEEKDAYS[day.weekday()]}），AI：{ctx.llm.provider}/{ctx.llm.model}"
        f"{'，dry-run' if args.dry_run else ''}")
    new_sections = {}
    for mod in mods:
        new_sections[mod.ID] = run_section(ctx, mod)
        ctx.save_state()  # 每个栏目做完就存，中途失败也不会重复推荐
        time.sleep(0 if args.dry_run else 3)

    if only and existing:
        sections = [new_sections.pop(s["id"], s) for s in existing.get("sections", [])]
        sections += list(new_sections.values())
        order = {n: i for i, n in enumerate(SECTIONS)}
        sections.sort(key=lambda s: order.get(s["id"], 99))
    else:
        sections = list(new_sections.values())

    status = day_status(sections)
    save_json(day_path, {
        "date": day.isoformat(), "weekday": f"周{WEEKDAYS[day.weekday()]}", "status": status,
        "generated_at": datetime.now(BJ).isoformat(timespec="seconds"),
        "llm": f"{ctx.llm.provider}/{ctx.llm.model}", "searches": ctx.search.used, "sections": sections,
    })
    rebuild_index(site)
    log(f"完成：{status}，用了 {ctx.search.used} 次搜索 → {day_path}")
    log_path = site / "data" / "log" / f"{day.isoformat()}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(LOG_LINES) + "\n\n")
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
