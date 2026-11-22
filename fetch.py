#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sunny Hub 主程式（由 GitHub Actions 執行）。

用法：
  python fetch.py                       # 依 GitHub 事件自動決定要跑哪些模組
  python fetch.py --modules acgn,news   # 手動指定
  python fetch.py --selftest            # 逐一測試所有資料來源，寫入 data/status.json
模組：acgn, news, lang:am, lang:pm, lexicon[:fam|:jlpt], dict, dictword:<en|ja>:<字詞>, weekly
"""
import os, re, sys, argparse, traceback

from hub import common
from hub.common import STATUS, log

# 每個排程（UTC cron 字串，需與 .github/workflows/hub.yml 完全一致）→ 模組
SCHEDULE_MAP = {
    "7 1 * * *":   ["acgn", "news"],                 # 台北 09:07 每天
    "7 2 * * 1-5": ["lang:am", "lexicon", "dict"],   # 台北 10:07 平日
    "7 9 * * 1-5": ["lang:pm"],                      # 台北 17:07 平日
    "7 12 * * *":  ["acgn", "news"],                 # 台北 20:07 每天
    "7 13 * * 0":  ["weekly"],                       # 台北 21:07 週日
}
ALL = ["acgn", "news", "lang:am", "lexicon", "dict", "weekly"]


def plan(event, schedule="", inputs="", issue_title=""):
    event = (event or "").strip()
    if event == "schedule":
        return list(SCHEDULE_MAP.get((schedule or "").strip(), []))
    if event == "workflow_dispatch":
        v = (inputs or "all").strip()
        return list(ALL) if v in ("", "all") else [x.strip() for x in v.split(",") if x.strip()]
    if event == "issues":
        t = (issue_title or "").strip()
        m = re.match(r"^\[dict\]\s*(.+?)\s*\((en|ja)\)\s*$", t)
        if m:
            return ["dictword:%s:%s" % (m.group(2), m.group(1))]
        m = re.match(r"^\[lexicon\]\s*refresh\s*(fam|jlpt)?", t, re.I)
        if m:
            return ["lexicon:%s" % (m.group(1) or "both")]
    return []


def run_module(spec):
    name, _, arg = spec.partition(":")
    if name == "acgn":
        from hub import acgn; return acgn.run()
    if name == "news":
        from hub import news; return news.run()
    if name == "lang":
        from hub import lang; return lang.run(arg or "am")
    if name == "lexicon":
        from hub import lexicon; return lexicon.run(arg or "both")
    if name == "dict":
        from hub import dictionary; return dictionary.run()
    if name == "dictword":
        from hub import dictionary
        lang_, _, word = arg.partition(":")
        return dictionary.generate([(word, lang_ if lang_ in ("en", "ja") else "en")])
    if name == "weekly":
        from hub import weekly; return weekly.run()
    raise ValueError("未知模組：%s" % spec)


def selftest():
    """從 GitHub 伺服器逐一測試每個資料來源（不改動內容資料，只更新 status.json）。"""
    from hub import acgn, news, lang
    from hub.feeds import fetch_feed
    from hub.common import source, http_get, http_post_json
    S = source
    S("anilist_anime", "AniList 季番", "acgn", lambda: acgn._anilist(acgn.Q_ANIME, {"season": acgn._season_of(common.now())[0], "year": common.now().year, "n": 3}))
    S("bangumi", "Bangumi 放送表", "acgn", acgn.bangumi_calendar)
    S("anilist_manga_jp", "AniList 日漫", "acgn", acgn.manga_from_anilist, "JP", "日漫", 2)
    S("anilist_manga_kr", "AniList 韓漫", "acgn", acgn.manga_from_anilist, "KR", "韓漫", 2, ("MANGA",))
    S("jikan_manga", "Jikan 漫畫（備援）", "acgn", acgn.manga_from_jikan)
    S("8comic", "無限動漫 更新列表", "comics", acgn.comic_8comic, 3)
    S("manhuaren", "漫畫人 最近更新", "comics", acgn.comic_manhuaren, 3)
    S("steam", "Steam 精選分類", "acgn", lambda: http_get("https://store.steampowered.com/api/featuredcategories/", params={"cc": "tw", "l": "tchinese"}, as_json=True).get("new_releases", {}).get("items", []))
    S("appstore", "App Store 台灣免費榜（遊戲）", "acgn", acgn.mobile_games, 3)
    S("jjwxc", "晉江文學城 月榜", "acgn", acgn.jjwxc_rank, 2)
    S("anilist_novel_cn", "AniList 華文網文", "acgn", acgn.novels_from_anilist, "CN", "華文網文", 2)
    S("naver_series", "Naver Series 小說排行", "acgn", acgn.naver_series, 3)
    S("anilist_novel_kr", "AniList 韓國網路小說", "acgn", acgn.novels_from_anilist, "KR", "韓國網路小說", 2)
    for key, name, origin, url, base in news.FEEDS:
        S("news_" + key, name + " RSS", "news", fetch_feed, url, base=base, limit=5, max_age_hours=None)
    for key, name, url, base in lang.EN_FEEDS + lang.JA_FEEDS:
        S("lang_" + key, name + " RSS", "lang", fetch_feed, url, base=base, limit=5, max_age_hours=None)
    S("dict_freedict", "Free Dictionary API（網頁即時查詢用）", "dict", lambda: http_get("https://api.dictionaryapi.dev/api/v2/entries/en/subtle", as_json=True))
    S("dict_wiktionary", "Wiktionary API（網頁即時查詢用）", "dict", lambda: http_get("https://en.wiktionary.org/api/rest_v1/page/definition/%E6%AC%A1%E7%AC%AC", as_json=True).get("ja", []))
    S("dict_mymemory", "MyMemory 翻譯（網頁即時查詢用）", "dict", lambda: [http_get("https://api.mymemory.translated.net/get", params={"q": "subtle", "langpair": "en|zh-TW"}, as_json=True)["responseData"]["translatedText"]])
    S("dict_ecdict", "ECDICT 離線辭典下載點", "dict", lambda: [common.SESSION.head("https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv", timeout=20).headers.get("Content-Length")])
    S("dict_jmdict", "JMdict 離線辭典下載點", "dict", lambda: [a["name"] for a in http_get("https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest", as_json=True).get("assets", []) if "jmdict-eng-common" in a["name"]])
    if common.gemini_available():
        S("gemini", "Gemini %s（免費層）" % common.MODEL, "ai", lambda: [common.gemini("請只回覆：OK")])
    else:
        STATUS.record("gemini", "Gemini（未設定金鑰）", "ai", False, 0, "缺少 GEMINI_API_KEY")


def summary_md():
    rows = ["| 狀態 | 來源 | 模組 | 筆數 | 錯誤 |", "|---|---|---|---|---|"]
    for k, s in sorted(STATUS.d["sources"].items(), key=lambda kv: (kv[1].get("module", ""), kv[0])):
        rows.append("| %s | %s | %s | %s | %s |" % ("✅" if s.get("ok") else "❌", s.get("name"), s.get("module"), s.get("count", 0), (s.get("error") or "").replace("|", "/")[:120]))
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        modules = ["selftest"]
        selftest()
    else:
        modules = [m.strip() for m in a.modules.split(",") if m.strip()] or plan(
            os.environ.get("EVENT_NAME"), os.environ.get("SCHEDULE"), os.environ.get("INPUT_MODULES"), os.environ.get("ISSUE_TITLE"))
        if not modules:
            log("沒有需要執行的模組（事件=%s 排程=%s）" % (os.environ.get("EVENT_NAME"), os.environ.get("SCHEDULE")))
        for m in modules:
            log("=== 模組 %s ===" % m)
            try:
                n = run_module(m)
                STATUS.note("%s 完成（%s）" % (m, n))
            except Exception as e:  # 單一模組失敗不影響其他模組
                traceback.print_exc()
                STATUS.note("%s 失敗：%s" % (m, str(e)[:150]))
    STATUS.finish(modules, common.model_info())
    md = "## Sunny Hub 執行結果\n\n模組：%s\n\nGemini：%s\n\n%s\n\n備註：\n%s\n" % (
        ", ".join(modules) or "（無）", common.model_info(), summary_md(), "\n".join("- " + n for n in STATUS.notes) or "- 無")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    with open(os.environ.get("HUB_RESULT", "hub_result.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    sys.exit(main())
