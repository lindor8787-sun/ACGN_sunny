# -*- coding: utf-8 -*-
"""離線測試：不連網、不呼叫真的 Gemini。用模擬的網站回應測試解析、合併、排程對應與完整執行流程。
執行：python tests/test_offline.py   （會在暫存資料夾操作，不影響 data/）"""
import os, sys, json, re, shutil, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(ROOT / "data", TMP / "data")
sys.path.insert(0, str(ROOT))
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["HUB_RESULT"] = str(TMP / "result.md")

from hub import common  # noqa
common.DATA = TMP / "data"
common.STATUS.path = common.DATA / "status.json"
from hub import acgn, news, lang, weekly, lexicon, dictionary, feeds  # noqa
for m in (acgn, news, lang, weekly, lexicon, dictionary):
    if hasattr(m, "PATH") and str(m.PATH).startswith(str(ROOT / "data")):
        m.PATH = common.DATA / m.PATH.relative_to(ROOT / "data")
    if hasattr(m, "DATA"):
        m.DATA = common.DATA
import fetch  # noqa

T = "2026-10-20"
RSS = """<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>x</title>
<item><title>{t1}</title><link>{l1}</link><description><![CDATA[<img src="https://img.example/a.jpg"> {d1}]]></description><pubDate>{pd}</pubDate></item>
<item><title>{t2}</title><link>{l2}</link><description>{d2}</description><pubDate>{pd}</pubDate><media:content url="https://img.example/b.jpg"/></item>
</channel></rss>"""
ATOM = """<?xml version="1.0" encoding="utf-8"?><ns6:feed xmlns:ns6="http://www.w3.org/2005/Atom"><ns6:title>HBR</ns6:title>
<ns6:entry><ns6:title>How to Negotiate a Better Deal</ns6:title><ns6:link href="/2026/10/how-to-negotiate"/><ns6:id>1</ns6:id><ns6:updated>{iso}</ns6:updated>
<ns6:summary>Most managers avoid tough conversations. When you circle back with a clear agenda, the other side is more willing to move on price. Preparation matters more than charisma.</ns6:summary></ns6:entry>
<ns6:entry><ns6:title>Sponsored thing</ns6:title><ns6:link href="/sponsored/2026/10/x"/><ns6:id>2</ns6:id><ns6:updated>{iso}</ns6:updated><ns6:summary>Ad content that should be filtered out entirely.</ns6:summary></ns6:entry>
</ns6:feed>"""


def pubdate():
    return common.now().strftime("%a, %d %b %Y %H:%M:%S +0800")


def fake_get(url, params=None, as_json=False, encoding=None, **kw):
    pd = pubdate()
    if "bgm.tv" in url:
        return [{"weekday": {"cn": "星期六"}, "items": [{"name": "星海のエコー", "name_cn": "星海的回声", "summary": "少年与失忆的星舰AI寻找故乡的故事，每一集解开一段记忆。", "air_date": "2026-10-04",
                                                     "images": {"large": "http://lain.bgm.tv/pic/cover/l/a.jpg"}, "url": "http://bgm.tv/subject/1", "rating": {"score": 7.9}}]}]
    if "8comic.com" in url:
        return '<div><a href="https://www.8comic.com/html/29774.html" title="超能力少女無能為力">- 超能力少女無能為力 - 漫畫9 - 2026-10-20</a><a href="https://www.8comic.com/html/1.html" title="鎖定">- 鎖定 - 漫畫3(登入觀看) - 2026-10-20</a></div>'
    if "manhuaren.com" in url:
        return '<ul><li><a href="/manhua-yiyiguangniandemao/" title="一亿光年的猫"><img src="https://mhfm1us.cdndm5.com/100/9/20261020_180x240.jpg"></a><p>最新 第12话</p></li></ul>'
    if "featuredcategories" in url:
        return {"new_releases": {"items": [{"id": 101, "type": 0, "name": "Lumen"}]}, "coming_soon": {"items": [{"id": 102, "type": 0, "name": "Orchard"}]}}
    if "appdetails" in url:
        aid = str(params["appids"])
        indie = aid == "101"
        return {aid: {"success": True, "data": {"type": "game", "name": "Lumen Drift" if indie else "Iron Orchard", "developers": ["Dev%s" % aid],
                                                 "short_description": "A puzzle adventure about reflecting light through a drowned city.",
                                                 "header_image": "https://cdn.steam/%s/header.jpg" % aid, "is_free": False,
                                                 "price_overview": {"final_formatted": "NT$ 300"}, "genres": [{"id": "23" if indie else "2", "description": "獨立製作" if indie else "策略"}],
                                                 "platforms": {"windows": True, "mac": indie}, "release_date": {"coming_soon": not indie, "date": "2026 年 11 月"},
                                                 "screenshots": [{"path_thumbnail": "https://cdn.steam/%s/ss%d.jpg" % (aid, i)} for i in range(4)]}}}
    if "marketingtools.apple.com" in url:
        return {"feed": {"results": [{"id": "11"}, {"id": "12"}]}}
    if "itunes.apple.com/lookup" in url:
        return {"results": [{"trackName": "星環戰紀", "artistName": "Sample Inc.", "primaryGenreId": 6014, "genreIds": ["6014"], "genres": ["遊戲", "角色扮演"],
                             "description": "開放世界動作RPG，四人即時共鬥。", "artworkUrl512": "https://is1.mzstatic/a.jpg", "screenshotUrls": ["https://is1/s1.jpg"],
                             "releaseDate": "2026-10-01T00:00:00Z", "formattedPrice": "免費", "trackViewUrl": "https://apps.apple.com/tw/app/id11"},
                            {"trackName": "Threads", "primaryGenreId": 6005, "genreIds": ["6005"]}]}
    if "jjwxc.net/topten" in url:
        return '<table><tr><td><a href="onebook.php?novelid=273">《长安夜雨》</a></td><td><a href="oneauthor.php?authorid=9">明晓溪</a></td></tr></table>'
    if "jjwxc.net/onebook" in url:
        return '<div id="novelintro">大理寺女评事追查连环悬案，一路查到宫廷深处的旧案。</div><span>文章进度：连载</span><span>全文字数：720,000字</span>'
    if "series.naver.com" in url:
        return '<ul><li><a href="/novel/detail.series?productNo=555" title="전지적 독자 시점"><img src="https://naver/c.jpg"></a><span class="author">싱숑</span></li></ul>'
    if "jikan.moe" in url:
        return {"data": []}
    if "4gamers" in url or "gnn.gamer" in url:
        return RSS.format(t1="年度遊戲展首日重點整理", l1="https://www.4gamers.com.tw/news/detail/1", d1="首日公開 12 款新作，其中 5 款支援繁中。獨立遊戲區人潮創新高。", t2="成人向 18禁 新作", l2="https://www.4gamers.com.tw/news/detail/2", d2="nsfw", pd=pd)
    if "gematsu" in url or "siliconera" in url or "animenewsnetwork" in url:
        return RSS.format(t1="New manga app launches globally", l1=url + "/news-1", d1="A global publisher launched an app with 200 titles and Traditional Chinese support.", t2="Steam autumn sale dates announced", l2=url + "/news-2", d2="The sale starts next month with many hit games.", pd=pd)
    if "hbr.org" in url:
        return ATOM.format(iso=common.now().isoformat())
    if "nhk.or.jp" in url or "yahoo.co.jp" in url:
        return RSS.format(t1="円安基調が続く", l1="https://www3.nhk.or.jp/news/html/1.html", d1="市場では円安基調が続いており、輸入企業のコスト負担が増している。政府は対応を検討している。",
                          t2="新製品の発表", l2="https://www3.nhk.or.jp/news/html/2.html", d2="大手メーカーは新製品について詳しく説明した。発売は来月の予定です。", pd=pd)
    if "bbci.co.uk" in url or "voanews" in url:
        raise common.FetchError("blocked (模擬)")
    raise common.FetchError("未模擬的網址 " + url)


def fake_post(url, payload, **kw):
    v = payload["variables"]
    if "season" in v:
        cur = acgn._season_of(common.now())
        is_cur = (v["season"], v["year"]) == cur
        native = "星海のエコー" if is_cur else "作品" + v["season"]
        return {"data": {"Page": {"media": [{"id": 1, "title": {"native": native, "romaji": "Hoshiumi no Echo", "english": "Echo of the Star Sea"}, "synonyms": [],
                                             "studios": {"nodes": [{"name": "Studio A"}]}, "episodes": 12, "status": "RELEASING", "nextAiringEpisode": {"episode": 8, "airingAt": 1792000000},
                                             "startDate": {"year": 2026, "month": 10, "day": 4}, "genres": ["Sci-Fi"], "coverImage": {"extraLarge": "https://anilist/cover1.jpg"},
                                             "description": "A boy and an amnesiac starship AI search for home.", "siteUrl": "https://anilist.co/anime/1", "source": "ORIGINAL",
                                             "externalLinks": [{"site": "Crunchyroll", "url": "https://crunchyroll.com/x", "type": "STREAMING"}]}]}}}
    fmt = v.get("fmt") or []
    origin = v["c"]
    return {"data": {"Page": {"media": [{"id": 9, "title": {"native": "作品%s%s" % (origin, "N" if "NOVEL" in fmt else "M"), "romaji": "x", "english": "Work %s" % origin}, "synonyms": [],
                                         "status": "RELEASING", "chapters": 42, "genres": ["Action"], "staff": {"edges": [{"role": "Story & Art", "node": {"name": {"native": "作者%s" % origin}}}]},
                                         "coverImage": {"large": "https://anilist/c%s.jpg" % origin}, "description": "A hero fights back.", "siteUrl": "https://anilist.co/manga/9",
                                         "externalLinks": []}]}}}


def fake_gemini(prompt, system=None, temperature=0.4):
    ids = re.findall(r'"id": "([^"]+)"', prompt)
    if "整理成語言學習卡" in prompt:
        out = {}
        for i in ids:
            if i.startswith("en_"):
                out[i] = {"original": "When you circle back with a clear agenda, the other side is more willing to move on price.", "translation": "當你帶著清楚議程回頭再談，對方更願意在價格上讓步。",
                          "points": ["circle back = 回頭再談", "move on price = 價格讓步", "clear agenda = 清楚議程"], "category": "談判協商", "difficulty": "中級", "dictWord": "circle back"}
            else:
                out[i] = {"original": "市場では円安基調が続いており、輸入企業のコスト負担が増している。", "translation": "市場持續日圓走弱。", "points": ["【N1文法】〜ており", "【商用場景】經濟報告", "【例句對照】…"],
                          "level": "N1", "category": "ニュース", "dictWord": "基調"}
        return json.dumps(out, ensure_ascii=False)
    if "JLPT %s 文法或敬語表達卡" % "" in prompt or "文法或敬語表達卡" in prompt:
        return json.dumps([{"title": "〜次第", "level": "N2", "category": "文法", "original": "確認でき次第ご連絡いたします。", "translation": "確認後立即聯絡。", "points": ["【N2文法】", "【商用場景】", "【例句對照】"], "dictWord": "次第"},
                           {"title": "〜につき", "level": "N2", "category": "文法", "original": "工事中につき通行止め。", "translation": "施工中禁止通行。", "points": ["a", "b", "c"], "dictWord": "につき"}], ensure_ascii=False)
    if "ACGN 新聞" in prompt:
        return "```json\n" + json.dumps({"items": {i: {"title_zh": "（譯）標題 " + i[-4:], "category": "遊戲", "points": ["重點一說明內容", "重點二說明內容", "重點三說明內容"]} for i in ids},
                                         "picks": ids[:3]}, ensure_ascii=False) + "\n```"
    if "從公開資料庫抓到的" in prompt:
        return "好的，以下是結果：\n" + json.dumps({i: {"title": "中文名" + i[-3:], "synopsis": "根據資料整理的繁中簡介。", "hook": "推薦理由。", "tags": ["熱血", "冒險"],
                                                 "highlights": ["亮點一", "亮點二", "亮點三"], "genre": "奇幻", "setting": "世界觀", "protagonist": "主角", "readers": "讀者"} for i in ids}, ensure_ascii=False)
    if "字根家族" in prompt:
        return json.dumps([["allocate", "allocation", "allocated", "—", "budget allocation 預算分配"], ["accept", "acceptance", "acceptable", "acceptably", "dup"]], ensure_ascii=False)
    if "JLPT 文法：N1、N2、N3" in prompt:
        return json.dumps([{"level": "N1", "g": "〜を皮切りに", "m": "以…為開端", "ex": "東京を皮切りに全国展開します。"}, {"level": "N2", "g": "〜次第", "m": "dup", "ex": "x"}], ensure_ascii=False)
    if "完整詳解" in prompt:
        words = re.findall(r'"word": "([^"]+)"', prompt)
        return json.dumps({w: {"ph": "", "level": "", "forms": "", "senses": [{"pos": "n.", "zh": "意思一", "def": "d", "ex": "e", "exZh": "例", "scene": "職場"},
                                                                               {"pos": "v.", "zh": "意思二", "def": "d2", "ex": "e2", "exZh": "例2", "scene": "會議"}], "syn": "", "ant": "—", "confuse": ""} for w in words}, ensure_ascii=False)
    if "製作週報" in prompt:
        return json.dumps({"ja": {"grammar": [["〜次第", "N2", "一…就", "聯絡"]] * 4, "phrases": [["ご査収", "查收"]] * 3}, "en": {"phrases": [["circle back", "回頭再談"]] * 4}, "acgn": ["動畫：本季話題作"] * 4}, ensure_ascii=False)
    return "OK"


def check(cond, msg):
    print(("  ✔ " if cond else "  ✘ ") + msg)
    if not cond:
        check.fail += 1


check.fail = 0

# 套用模擬
for m in (common, acgn, feeds):
    if hasattr(m, "http_get"):
        m.http_get = fake_get
for m in (common, acgn):
    if hasattr(m, "http_post_json"):
        m.http_post_json = fake_post
common._sdk_call = lambda model, p: fake_gemini(p)
acgn.time.sleep = lambda s: None

print("1) 排程對應（hub.yml 的 cron 必須與 SCHEDULE_MAP 一致）")
import yaml  # noqa
wf = yaml.safe_load((ROOT / ".github/workflows/hub.yml").read_text(encoding="utf-8"))
crons = [c["cron"] for c in wf[True]["schedule"]]
check(sorted(crons) == sorted(fetch.SCHEDULE_MAP), "cron 與 SCHEDULE_MAP 一致：%s" % crons)
check(fetch.plan("schedule", "7 1 * * *") == ["acgn", "news"], "09:07 → acgn, news")
check(fetch.plan("schedule", "7 2 * * 1-5") == ["lang:am", "lexicon", "dict"], "10:07 → 語言上午＋字庫＋字典")
check(fetch.plan("schedule", "7 13 * * 0") == ["weekly"], "週日 21:07 → 週報")
check(fetch.plan("workflow_dispatch", inputs="all") == fetch.ALL, "手動 all")
check(fetch.plan("issues", issue_title="[dict] circle back (en)") == ["dictword:en:circle back"], "Issue：AI 詳解")
check(fetch.plan("issues", issue_title="[lexicon] refresh jlpt") == ["lexicon:jlpt"], "Issue：刷新字庫")
check(fetch.plan("issues", issue_title="random") == [], "其他 Issue 不執行")
tz = {"7 1 * * *": 9, "7 2 * * 1-5": 10, "7 9 * * 1-5": 17, "7 12 * * *": 20, "7 13 * * 0": 21}
check(all(int(k.split()[1]) + 8 == v for k, v in tz.items()), "UTC+8 換算：09/10/17/20/21 點")

print("2) 合併邏輯")
old = [{"id": "a", "title": "A", "latest": "第1話", "added": "2026-10-01", "updated": "2026-10-01", "synopsis": "舊簡介"},
       {"id": "s", "title": "範例", "seed": True, "added": T}]
fresh = [{"id": "a", "title": "A2", "latest": "第2話", "synopsis": "新"}, {"id": "b", "title": "B"}]
items, new = common.merge_items(old, fresh, volatile=("latest",))
a = next(x for x in items if x["id"] == "a")
check(a["latest"] == "第2話" and a["added"] == "2026-10-01" and a["title"] == "A" and a["synopsis"] == "舊簡介", "更新集數、保留原收錄日與標題簡介")
check(new == ["b"] and not any(x["id"] == "s" for x in items), "新項目加入、範例資料自動移除")
many = [{"id": str(i), "cat": "x", "added": "2026-10-%02d" % (i % 28 + 1)} for i in range(80)]
capped, _ = common.merge_items([], many, cap=40, cap_key=lambda x: x["cat"])
check(len(capped) == 40, "每類上限 40 筆")
olds = [{"id": "o", "added": "2020-01-01"}]
kept, _ = common.merge_items(olds, [], keep_days=7)
check(kept == [], "超過 7 天自動清除")

print("3) JSON 萃取")
check(common.extract_json('```json\n{"a":1}\n```') == {"a": 1}, "去除 ``` 圍欄")
check(common.extract_json('好的：[1,2,{"x":"]"}] 以上') == [1, 2, {"x": "]"}], "從說明文字中找出 JSON")
check(common.extract_json("沒有 JSON") is None, "壞輸入回傳 None")

print("4) 各來源解析")
check(len(acgn.comic_8comic()) == 1, "無限動漫：解析 1 筆、略過「登入觀看」")
c8 = acgn.comic_8comic()[0]
check(c8["latest"] == "第9話" and c8["image"].endswith("/29774.jpg"), "無限動漫：最新話數與封面")
mh = acgn.comic_manhuaren()[0]
check(mh["title"] == "一億光年的貓" and mh["latest"] == "第12話", "漫畫人：簡轉繁、最新話")
g = acgn.steam_featured()
check(len(g) == 2 and g[0]["platform"] == "Indie" and len(g[0]["screenshots"]) == 3, "Steam：獨立遊戲判斷、3 張截圖")
mg = acgn.mobile_games()
check(len(mg) == 1 and mg[0]["title"] == "星環戰紀", "App Store：只留遊戲類")
jj = acgn.jjwxc_rank()
check(jj[0]["title"] == "長安夜雨" and jj[0]["status"] == "連載中" and "72" in jj[0]["length"], "晉江：書名、狀態、字數（簡轉繁）")
nv = acgn.naver_series()
check(nv[0]["title_orig"] == "전지적 독자 시점", "Naver Series：書名")
f = feeds.fetch_feed("https://www.4gamers.com.tw/rss/latest-news")
check(len(f) == 2 and f[0]["image"] == "https://img.example/a.jpg", "RSS：標題、圖片")
h = feeds.fetch_feed("http://feeds.hbr.org/harvardbusiness", base="https://hbr.org")
check(h[0]["link"].startswith("https://hbr.org/2026/10/"), "HBR Atom（ns6 前綴）：相對連結補完整")

print("5) 完整執行（模擬網路＋模擬 Gemini）")
sys.argv = ["fetch.py", "--modules", "acgn,news,lang:am,lexicon,dict,weekly"]
fetch.main()
A = common.load_json(common.DATA / "acgn.json", {})
cats = {c: [x for x in A["items"] if x["cat"] == c] for c in ("anime", "comic", "games", "novel")}
check(all(cats.values()) and not A["meta"]["seed"], "ACGN 四類都有資料、範例已移除：%s" % {k: len(v) for k, v in cats.items()})
an = cats["anime"][0]
check(an["title"] and an["latest"] == "第7話" and an["image"] and any(w["name"] == "在動畫瘋搜尋" for w in an["watch"]), "動畫：中文名、最新集數、封面、觀看連結")
check(all(not k.startswith("_") or k == "_ai" for x in A["items"] for k in x), "暫存欄位已清除")
check(any(x.get("origin") == "連載更新" for x in cats["comic"]), "漫畫：含連載更新")
N = common.load_json(common.DATA / "news.json", {})
check(len(N["items"]) >= 4 and sum(1 for x in N["items"] if x["pick"]) == 3 and all(len(x["points"]) >= 3 for x in N["items"]), "新聞：重點≥3、必看 3 則")
check(not any("18禁" in x["title"] for x in N["items"]), "新聞：過濾成人內容")
L = common.load_json(common.DATA / "lang.json", {})
en = [x for x in L["items"] if x["cat"] == "en"]
ja = [x for x in L["items"] if x["cat"] == "ja"]
check(en and en[0]["original"].startswith("When you circle back") and en[0]["url"].startswith("https://hbr.org"), "英文：原文逐字取自文章、連結正確、略過 sponsored")
check(len(ja) >= 3 and any(x["source"] == "Sunny Hub（AI 編寫）" for x in ja), "日文：新聞卡＋文法卡")
LX = common.load_json(common.DATA / "lexicon.json", {})
check(LX["fam"][0]["r"][0] == "allocate" and sum(1 for x in LX["fam"] if x["r"][0] == "accept") == 1, "字庫：新增 allocate、重複的 accept 被擋")
check(LX["jlpt"]["N1"][0]["g"] == "〜を皮切りに", "字庫：N1 新文法")
D = common.load_json(common.DATA / "dict" / "detail.json", {})
check("circle back" in D and len(D["circle back"]["senses"]) >= 2 or len(D) > 8, "字典詳解：新增多義項詞條（共 %d）" % len(D))
W = common.load_json(common.DATA / "weekly" / "index.json", [])
check(W and W[0]["weekId"] == weekly.week_id() and not any(w.get("seed") for w in W), "週報：產生本週、範例週報移除")
ST = common.load_json(common.DATA / "status.json", {})
check(ST["sources"]["lang_bbc_le"]["ok"] is False and ST["sources"]["steam"]["ok"] is True, "狀態：成功／失敗來源都有記錄")
check(ST["model"]["calls"] > 0, "Gemini 呼叫次數：%d" % ST["model"]["calls"])

print("6) 第二次執行：不重複、已整理的不再送 Gemini")
before = common._calls["n"]
fetch.run_module("acgn")
A2 = common.load_json(common.DATA / "acgn.json", {})
check(len(A2["items"]) == len(A["items"]), "ACGN 重跑筆數不變（去重）")
check(common._calls["n"] == before, "已整理過的作品不再呼叫 Gemini")
fetch.run_module("dictword:en:subtle")
check("subtle" in common.load_json(common.DATA / "dict" / "detail.json", {}), "Issue 請求詳解 → 寫入 detail.json")

print("7) 沒有金鑰時降級")
common.API_KEY = ""
lexicon_n = fetch.run_module("lexicon")
check(lexicon_n == 0, "無金鑰：字庫略過、不出錯")

print("\n輸出資料夾：", TMP / "data")
print("結果：%s" % ("全部通過 ✅" if check.fail == 0 else "%d 項失敗 ❌" % check.fail))
sys.exit(1 if check.fail else 0)
