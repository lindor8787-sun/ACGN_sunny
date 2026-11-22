# -*- coding: utf-8 -*-
"""週報：彙整近 7 天語言學習與 ACGN／新聞，產生 data/weekly/index.json（最新在前，保留 12 期）。"""
import json

from .common import DATA, now, days_ago, today, log, load_json, save_json, gemini_json, gemini_available

PATH = DATA / "weekly" / "index.json"


def week_id(d=None):
    d = d or now()
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def run():
    lang = load_json(DATA / "lang.json", {"items": []})["items"]
    acgn = load_json(DATA / "acgn.json", {"items": []})["items"]
    news = load_json(DATA / "news.json", {"items": []})["items"]
    since = days_ago(7)
    ja = [x for x in lang if x["cat"] == "ja" and x.get("added", "") >= since]
    en = [x for x in lang if x["cat"] == "en" and x.get("added", "") >= since]
    ac = [x for x in acgn if x.get("added", "") >= since]
    nw = [x for x in news if x.get("added", "") >= since and x.get("pick")]
    wid = week_id()
    w = {"id": "weekly_" + wid, "mod": "weekly", "cat": "weekly", "title": "週報 " + wid, "weekId": wid,
         "range": "%s ~ %s" % (days_ago(6), today()), "added": today(),
         "ja": {"grammar": [], "phrases": []}, "en": {"phrases": []}, "acgn": []}
    res = None
    if gemini_available() and (ja or en or ac):
        src = {"ja": [{"title": x["title"], "level": x.get("level"), "points": x.get("points")} for x in ja][:20],
               "en": [{"title": x["title"], "points": x.get("points")} for x in en][:20],
               "acgn": [{"cat": x["cat"], "title": x["title"], "latest": x.get("latest", "")} for x in ac][:30],
               "news": [x["title"] for x in nw][:15]}
        res = gemini_json(
            "根據本週的學習與 ACGN 資料（JSON）製作週報。輸出："
            "{\"ja\":{\"grammar\":[[文法,JLPT級,意思,商用場景]...至少4則],\"phrases\":[[商用日文,中文]...至少3則]},"
            "\"en\":{\"phrases\":[[商用英文片語,中文]...至少4則]},\"acgn\":[本週 ACGN 動態一句話...4~6則]}。"
            "文法、片語優先從資料中挑選。\n\n%s" % json.dumps(src, ensure_ascii=False),
            system="你是台灣的語言與 ACGN 編輯。", temperature=0.4, expect=dict)
    if isinstance(res, dict):
        w["ja"]["grammar"] = [g for g in (res.get("ja") or {}).get("grammar", []) if isinstance(g, list) and len(g) >= 4][:6]
        w["ja"]["phrases"] = [p for p in (res.get("ja") or {}).get("phrases", []) if isinstance(p, list) and len(p) >= 2][:5]
        w["en"]["phrases"] = [p for p in (res.get("en") or {}).get("phrases", []) if isinstance(p, list) and len(p) >= 2][:8]
        w["acgn"] = [s for s in res.get("acgn", []) if isinstance(s, str)][:6]
    if not w["ja"]["grammar"]:   # 降級：直接取本週卡片
        w["ja"]["grammar"] = [[x["title"], x.get("level", ""), x.get("translation", "")[:30], x.get("category", "")] for x in ja[:5]]
        w["en"]["phrases"] = [[(x.get("points") or ["-"])[0].split(" = ")[0], ((x.get("points") or [" = "])[0].split(" = ") + [""])[1]] for x in en[:5]]
        w["acgn"] = ["%s：%s %s" % ({"anime": "動畫", "comic": "漫畫", "games": "遊戲", "novel": "小說"}[x["cat"]], x["title"], x.get("latest", "")) for x in ac[:5]]
    idx = [x for x in load_json(PATH, []) if x.get("id") != w["id"] and not x.get("seed")]
    save_json(PATH, ([w] + idx)[:12])
    log("週報完成", wid)
    return 1
