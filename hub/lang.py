# -*- coding: utf-8 -*-
"""語言學習：商用英文 4 篇＋日文 5 篇（真實文章 3 篇＋商用文法 2 則）。
真實文章來自 RSS；『原文』句子必須逐字取自文章摘要（程式會檢查），中譯與學習重點由 Gemini 整理。"""
import re, json

from .common import DATA, today, now, log, load_json, save_json, merge_items, make_id, source, gemini_json, gemini_available
from .feeds import fetch_feed

PATH = DATA / "lang.json"
EN_FEEDS = [("hbr", "Harvard Business Review", "http://feeds.hbr.org/harvardbusiness", "https://hbr.org"),
            ("bbc_le", "BBC Learning English", "https://podcasts.files.bbci.co.uk/p02pc9tn.rss", None),
            ("voa_le", "VOA Learning English", "https://learningenglish.voanews.com/api/zmgqoe$moi", None)]
JA_FEEDS = [("nhk_biz", "NHK ニュース（経済）", "https://www3.nhk.or.jp/rss/news/cat5.xml", None),
            ("nhk_main", "NHK ニュース（主要）", "https://www3.nhk.or.jp/rss/news/cat0.xml", None),
            ("yahoo_biz", "Yahoo!ニュース（経済）", "https://news.yahoo.co.jp/rss/topics/business.xml", None)]
EN_CATS = ["商務Email", "會議英文", "談判協商", "簡報英文", "報告撰寫", "人脈拓展", "商業詞彙", "商用慣用語"]
JA_CATS = ["ニュース", "文法", "語彙", "ビジネス", "敬語"]


def _gather(feeds, n, used):
    out = []
    for key, name, url, base in feeds:
        got = source("lang_" + key, name + " RSS", "lang", fetch_feed, url, base=base, limit=15, max_age_hours=96) or []
        for e in got:
            if "/sponsored/" in e["link"] or e["link"] in used or len((e["summary"] or e["content"])) < 40:
                continue
            e["source_name"] = name
            out.append(e)
        if len(out) >= n * 2:
            break
    return out[: n * 2]


def _sentences(text, lang):
    parts = re.split(r"(?<=[。！？!?\.])\s*", text)
    return [p.strip() for p in parts if 15 <= len(p.strip()) <= (220 if lang == "en" else 120)]


def _card(e, lang, session):
    text = e["summary"] or e["content"]
    sents = _sentences(text, lang)
    return {"mod": "lang", "cat": lang, "title": e["title"], "url": e["link"], "source": e["source_name"],
            "original": sents[0] if sents else text[:200], "_text": text[:1200], "_session": session}


def _ai_cards(cards, lang, session):
    if not cards or not gemini_available():
        return
    focus_en = "上午場偏重 Email／會議／簡報／詞彙" if session == "am" else "下午場偏重 談判／報告／社交／慣用語"
    focus_ja = "上午場偏重 N1 文法" if session == "am" else "下午場偏重 N2・N3 商用實戰與敬語"
    payload = [{"id": c["id"], "title": c["title"], "text": c["_text"]} for c in cards]
    if lang == "en":
        spec = ("original（從 text 中『逐字』挑 1~2 句最適合學商用英文的句子，不可改寫）, translation（繁中翻譯）, "
                "points（3 條學習重點，格式「片語 = 中文說明」）, category（只能是：%s）, difficulty（初級/中級/高級）, "
                "dictWord（original 中最值得查的單字或片語）。%s" % ("、".join(EN_CATS), focus_en))
    else:
        spec = ("original（從 text 中『逐字』挑 1 句，不可改寫）, translation（繁中翻譯）, "
                "points（3 條，開頭分別用【N1文法】或【N2文法】或【N3文法】、【商用場景】、【例句對照】）, level（N1/N2/N3）, "
                "category（只能是：%s）, dictWord（句中最值得查的詞，辭書形）。%s" % ("、".join(JA_CATS), focus_ja))
    res = gemini_json("把下列真實文章整理成語言學習卡。每筆輸出：%s\n輸出格式：{\"<id>\": {...}}\n\n%s"
                      % (spec, json.dumps(payload, ensure_ascii=False)),
                      system="你是台灣的商用%s老師。" % ("英文" if lang == "en" else "日文"), temperature=0.3, expect=dict) or {}
    for c in cards:
        r = res.get(c["id"]) or {}
        orig = (r.get("original") or "").strip()
        if orig and orig.replace(" ", "") in c["_text"].replace(" ", ""):   # 確認真的是原文
            c["original"] = orig
        for k in ("translation", "points", "category", "difficulty", "level", "dictWord"):
            if r.get(k):
                c[k] = r[k]
        if lang == "ja":
            c["tags"] = ["💼 商用"] if c.get("category") in ("ビジネス", "敬語") or "経済" in c["source"] else []


def _grammar_cards(n, session, existing_titles):
    """日文商用文法卡（無外部文章，由 Gemini 依 JLPT 範圍編寫）。"""
    if not gemini_available():
        return []
    levels = "N1、N2" if session == "am" else "N2、N3"
    res = gemini_json(
        "請編寫 %d 則日本職場常用的 JLPT %s 文法或敬語表達卡，不要與這些重複：%s。\n"
        "每則輸出：title（文法或句型）, level（N1/N2/N3）, category（文法/敬語/ビジネス）, original（自然的商用例句）, translation（繁中）, "
        "points（3 條：【N?文法】用法說明、【商用場景】使用時機、【例句對照】另一個例句）, dictWord（核心詞，辭書形）。\n輸出格式：[{...}]"
        % (n, levels, "、".join(list(existing_titles)[:40])), system="你是台灣的商用日文老師。", temperature=0.5, expect=list) or []
    out = []
    for r in res[:n]:
        if not isinstance(r, dict) or not r.get("title") or not r.get("original"):
            continue
        out.append({"mod": "lang", "cat": "ja", "title": r["title"], "level": r.get("level", "N2"), "category": r.get("category", "文法"),
                    "original": r["original"], "translation": r.get("translation", ""), "points": r.get("points", [])[:3],
                    "tags": ["💼 商用"], "source": "Sunny Hub（AI 編寫）", "url": "", "dictWord": r.get("dictWord", "")})
    return out


def run(session="am"):
    db = load_json(PATH, {"meta": {}, "items": []})
    used = {x.get("url") for x in db.get("items", [])}
    fresh = []
    for lang, feeds, n in (("en", EN_FEEDS, 4), ("ja", JA_FEEDS, 3)):
        cards = [_card(e, lang, session) for e in _gather(feeds, n, used)][:n]
        for c in cards:
            c["id"] = make_id(lang, c["url"])
        _ai_cards(cards, lang, session)
        for c in cards:
            c.setdefault("points", [])
            c.setdefault("translation", "")
            c.setdefault("category", "ニュース" if lang == "ja" else "商業詞彙")
            if lang == "ja":
                c.setdefault("level", "N1")
                c.setdefault("tags", [])
        fresh += cards
    titles = {x["title"] for x in db.get("items", []) if x.get("cat") == "ja"}
    for g in _grammar_cards(2, session, titles):
        g["id"] = make_id("ja", g["title"])
        fresh.append(g)
    for c in fresh:
        for k in [k for k in c if k.startswith("_")]:
            c.pop(k)
    items, new_ids = merge_items(db.get("items", []), fresh, keep_days=7)
    db["items"] = items
    db["meta"] = {"last_updated": now().isoformat(timespec="minutes"), "seed": False}
    save_json(PATH, db)
    log("語言完成：新增 %d，共 %d" % (len(new_ids), len(items)))
    return len(new_ids)
