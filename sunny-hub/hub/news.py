# -*- coding: utf-8 -*-
"""ACGN 新聞：台灣＋國際 RSS → Gemini 翻譯、分類、整理 3~5 點重點、挑今日必看 3 則。連結一律是 RSS 原始網址。"""
import re, json, hashlib

from .common import DATA, today, now, log, load_json, save_json, merge_items, source, gemini_json, gemini_available, to_tw
from .feeds import fetch_feed

PATH = DATA / "news.json"
FEEDS = [  # (key, 名稱, 地區, url, base)
    ("gnn", "巴哈姆特 GNN", "TW", "https://gnn.gamer.com.tw/rss.xml", "https://gnn.gamer.com.tw"),
    ("4gamers", "4Gamers", "TW", "https://www.4gamers.com.tw/rss/latest-news", None),
    ("ann", "Anime News Network", "INTL", "https://www.animenewsnetwork.com/all/rss.xml?ann-edition=w", None),
    ("gematsu", "Gematsu", "INTL", "https://www.gematsu.com/feed", None),
    ("siliconera", "Siliconera", "INTL", "https://www.siliconera.com/feed/", None),
]
NSFW = re.compile(r"成人|18禁|R-?18|紳士|NSFW|hentai|情色|裏番|里番", re.I)
CATS = ["動漫", "漫畫", "遊戲", "小說", "業界"]
KW = [("漫畫", r"漫畫|manga|manhwa|webtoon|連載"), ("小說", r"小說|輕小說|light novel|web novel|novel"),
      ("動漫", r"動畫|anime|番|聲優|劇場版"), ("遊戲", r"遊戲|game|steam|switch|playstation|xbox|手遊|rpg")]


def _guess_cat(t):
    for c, pat in KW:
        if re.search(pat, t, re.I):
            return c
    return "業界"


def collect():
    raw, seen = [], set()
    for key, name, origin, url, base in FEEDS:
        got = source("news_" + key, name + " RSS", "news", fetch_feed, url, base=base, limit=20, max_age_hours=36) or []
        for e in got:
            if NSFW.search(e["title"] + e["summary"]) or not e["link"] or e["link"] in seen:
                continue
            seen.add(e["link"])
            e.update(source_name=name, origin=origin)
            raw.append(e)
    tw = [e for e in raw if e["origin"] == "TW"][:9]
    intl = [e for e in raw if e["origin"] == "INTL"][:9]
    return tw + intl


def run():
    db = load_json(PATH, {"meta": {}, "items": []})
    known = {x.get("url") for x in db.get("items", [])}
    entries = [e for e in collect() if e["link"] not in known]
    fresh = []
    for e in entries:
        fresh.append({"id": "news_" + hashlib.sha1(e["link"].encode()).hexdigest()[:12], "mod": "news", "cat": "news",
                      "title": e["title"], "url": e["link"], "source": e["source_name"], "origin": e["origin"],
                      "image": e["image"], "category": _guess_cat(e["title"] + " " + e["summary"]),
                      "points": [e["summary"][:120]] if e["summary"] else [], "summary": e["summary"][:160],
                      "_text": (e["content"] or e["summary"])[:1500], "pick": False})
    if fresh and gemini_available():
        payload = [{"id": f["id"], "title": f["title"], "region": f["origin"], "text": f["_text"]} for f in fresh]
        res = gemini_json(
            "以下是今天抓到的 ACGN 新聞（JSON）。請為每一則輸出：title_zh（繁中標題；國際新聞請翻譯，台灣新聞沿用原標題）、"
            "category（只能是：%s）、points（3~5 點繁中重點，每點 15~40 字，只能根據 text 內容，不可補充外部資訊）。"
            "另外選出最值得看的 3 則 id 放進 picks。\n輸出格式：{\"items\": {\"<id>\": {\"title_zh\":..., \"category\":..., \"points\": [...]}}, \"picks\": [id, id, id]}\n\n%s"
            % ("、".join(CATS), json.dumps(payload, ensure_ascii=False)),
            system="你是台灣的 ACGN 新聞編輯。", temperature=0.3, expect=dict) or {}
        m = res.get("items") or {}
        for f in fresh:
            r = m.get(f["id"]) or {}
            if r.get("title_zh"):
                f["title"] = to_tw(r["title_zh"])
            if r.get("category") in CATS:
                f["category"] = r["category"]
            pts = [p for p in (r.get("points") or []) if isinstance(p, str) and p.strip()]
            if len(pts) >= 3:
                f["points"] = pts[:5]
                f["summary"] = pts[0]
        for pid in (res.get("picks") or [])[:3]:
            for f in fresh:
                if f["id"] == pid:
                    f["pick"] = True
    for f in fresh:   # 必看不足 3 則（無 Gemini 或回傳不足）→ 依序補滿
        if sum(1 for x in fresh if x["pick"]) >= 3:
            break
        f["pick"] = True
    for f in fresh:
        f.pop("_text", None)
    if fresh:   # 新一輪必看出現時，舊的必看取消
        for x in db.get("items", []):
            if x.get("pick") and x.get("added") == today():
                x["pick"] = False
    items, new_ids = merge_items(db.get("items", []), fresh, volatile=(), keep_days=7)
    db["items"] = items
    db["meta"] = {"last_updated": now().isoformat(timespec="minutes"), "seed": False}
    save_json(PATH, db)
    log("新聞完成：新增 %d，共 %d" % (len(new_ids), len(items)))
    return len(new_ids)
