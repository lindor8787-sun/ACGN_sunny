# -*- coding: utf-8 -*-
"""ACGN 模組：動畫／漫畫／遊戲／小說（含封面、截圖）。
資料一律來自公開、免金鑰的來源；Gemini 只負責把「已抓到的文字」翻成繁中、整理成卡片欄位。
"""
import re, json, time, datetime as dt
from urllib.parse import quote

from bs4 import BeautifulSoup

from .common import (DATA, today, log, http_get, http_post_json, load_json, save_json, clean_text, to_tw,
                     make_id, merge_items, source, gemini_json, gemini_available, now)

PATH = DATA / "acgn.json"
ANILIST = "https://graphql.anilist.co"
CAP = 40                      # 每個子群組最多保留筆數
VOLATILE = ("latest", "status", "episodes", "broadcast", "release", "price", "image", "screenshots", "season_type", "watch")


def _anilist(query, variables):
    j = http_post_json(ANILIST, {"query": query, "variables": variables},
                       headers={"Content-Type": "application/json", "Accept": "application/json"})
    if j.get("errors"):
        raise RuntimeError(str(j["errors"])[:200])
    return j["data"]["Page"]["media"]


def _gsearch(site, q):
    """以 Google 站內搜尋產生可靠連結（不依賴各站搜尋頁格式）。"""
    return "https://www.google.com/search?q=" + quote("site:%s %s" % (site, q))


# ================================================================ 動畫
SEASONS = ["WINTER", "SPRING", "SUMMER", "FALL"]
SEASON_ZH = {"WINTER": "冬", "SPRING": "春", "SUMMER": "夏", "FALL": "秋"}
Q_ANIME = """query($season:MediaSeason,$year:Int,$n:Int){Page(perPage:$n){media(season:$season,seasonYear:$year,type:ANIME,
sort:POPULARITY_DESC,isAdult:false,format_in:[TV,TV_SHORT,ONA]){id title{native romaji english} synonyms
studios(isMain:true){nodes{name}} episodes status nextAiringEpisode{episode airingAt} startDate{year month day}
genres coverImage{extraLarge large} description(asHtml:false) siteUrl source externalLinks{site url type}}}}"""
SOURCE_ZH = {"ORIGINAL": "原創動畫", "MANGA": "漫畫改編", "LIGHT_NOVEL": "輕小說改編", "NOVEL": "小說改編",
             "WEB_NOVEL": "網路小說改編", "VIDEO_GAME": "遊戲改編", "VISUAL_NOVEL": "視覺小說改編", "WEB_MANGA": "網路漫畫改編"}
WEEKDAY = "一二三四五六日"


def _season_of(d):
    return SEASONS[(d.month - 1) // 3], d.year


def _shift(season, year, k):
    i = SEASONS.index(season) + k
    return SEASONS[i % 4], year + (i // 4)


def anime_from_anilist(n=8):
    cur = _season_of(now())
    out = []
    for stype, k, cnt in (("current", 0, n), ("prev", -1, 4), ("next", 1, 5)):
        s, y = _shift(cur[0], cur[1], k)
        for m in _anilist(Q_ANIME, {"season": s, "year": y, "n": cnt}):
            nxt = m.get("nextAiringEpisode") or {}
            if stype == "current":
                latest = ("第%d話" % (nxt["episode"] - 1)) if nxt.get("episode", 0) > 1 else ("完結" if m.get("status") == "FINISHED" else "首播前")
            elif stype == "prev":
                latest = "完結（全%s話）" % (m.get("episodes") or "?") if m.get("status") == "FINISHED" else ("第%d話" % (nxt["episode"] - 1) if nxt.get("episode", 0) > 1 else "播出中")
            else:
                sd = m.get("startDate") or {}
                latest = "%s月開播" % sd["month"] if sd.get("month") else "下季開播"
            bc = ""
            if nxt.get("airingAt"):
                t = dt.datetime.fromtimestamp(nxt["airingAt"], tz=dt.timezone(dt.timedelta(hours=9)))
                bc = "每週%s %02d:%02d（日本）" % (WEEKDAY[t.weekday()], t.hour, t.minute)
            native = (m["title"].get("native") or m["title"].get("romaji") or "")
            watch = [{"name": l["site"], "url": l["url"]} for l in (m.get("externalLinks") or []) if l.get("type") == "STREAMING"][:4]
            out.append({
                "cat": "anime", "season_type": stype, "season": "%d %s" % (y, SEASON_ZH[s]),
                "title_orig": native, "_en": m["title"].get("english") or m["title"].get("romaji") or "",
                "_syn": [x for x in (m.get("synonyms") or []) if re.search(r"[一-鿿]", x)][:3],
                "studio": ", ".join(x["name"] for x in (m.get("studios") or {}).get("nodes", [])[:2]),
                "latest": latest, "broadcast": bc, "episodes": ("全 %d 話" % m["episodes"]) if m.get("episodes") else "未公布",
                "original": SOURCE_ZH.get(m.get("source") or "", ""), "_desc": clean_text(m.get("description"), 700),
                "_genres": m.get("genres") or [], "image": (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or "",
                "imageSrc": "AniList", "watch": watch, "_link": m.get("siteUrl"),
            })
    return out


def bangumi_calendar():
    """bgm.tv 放送表：提供中文名、中文簡介、封面（作為中文名對照與 AniList 失效時的備援）。"""
    data = http_get("https://api.bgm.tv/calendar", as_json=True)
    out = []
    for day in data:
        for it in day.get("items", []):
            img = ((it.get("images") or {}).get("large") or "").replace("http://", "https://")
            out.append({"name": it.get("name") or "", "name_cn": to_tw(it.get("name_cn") or ""), "summary": to_tw(it.get("summary") or ""),
                        "air_date": it.get("air_date") or "", "weekday": (day.get("weekday") or {}).get("cn", ""),
                        "image": img, "url": (it.get("url") or "").replace("http://", "https://"),
                        "score": ((it.get("rating") or {}).get("score") or 0)})
    out.sort(key=lambda x: -x["score"])
    return out


def anime_from_bangumi(bgm, n=10):
    out = []
    for b in bgm[:n]:
        weeks = ""
        try:
            d0 = dt.date.fromisoformat(b["air_date"])
            k = (now().date() - d0).days // 7 + 1
            if 0 < k < 60:
                weeks = "約第%d話（推估）" % k
        except Exception:
            pass
        out.append({"cat": "anime", "season_type": "current", "season": "%d %s" % (now().year, SEASON_ZH[_season_of(now())[0]]),
                    "title": b["name_cn"] or b["name"], "title_orig": b["name"], "latest": weeks or "播出中",
                    "broadcast": ("每週%s" % to_tw(b["weekday"])) if b.get("weekday") else "", "_desc": b["summary"][:700],
                    "image": b["image"], "imageSrc": "Bangumi", "watch": [], "_link": b["url"]})
    return out


def collect_anime():
    items = source("anilist_anime", "AniList 季番（本季/上季/下季）", "acgn", anime_from_anilist) or []
    bgm = source("bangumi", "Bangumi 放送表（中文名）", "acgn", bangumi_calendar) or []
    if not items and bgm:
        items = anime_from_bangumi(bgm)
    by_native = {b["name"]: b for b in bgm}
    for it in items:
        b = by_native.get(it.get("title_orig"))
        if b:
            if b["name_cn"] and not it.get("title"):
                it["title"] = b["name_cn"]
            if b["summary"] and len(b["summary"]) > 20:
                it["_desc_zh"] = b["summary"][:700]
            if not it.get("image"):
                it["image"], it["imageSrc"] = b["image"], "Bangumi"
    for it in items:
        name = it.get("title") or (it.get("_syn") or [None])[0] or it.get("title_orig")
        it["watch"] = (it.get("watch") or []) + [{"name": "在動畫瘋搜尋", "url": _gsearch("ani.gamer.com.tw", name or "")}]
    return items


# ================================================================ 漫畫
Q_MANGA = """query($c:CountryCode,$n:Int,$fmt:[MediaFormat]){Page(perPage:$n){media(type:MANGA,countryOfOrigin:$c,
sort:TRENDING_DESC,isAdult:false,format_in:$fmt){id title{native romaji english} synonyms status chapters genres
staff(perPage:3,sort:RELEVANCE){edges{role node{name{full native}}}} coverImage{extraLarge large}
description(asHtml:false) siteUrl externalLinks{site url type}}}}"""
STATUS_ZH = {"RELEASING": "連載中", "FINISHED": "已完結", "HIATUS": "休刊中", "NOT_YET_RELEASED": "即將推出", "CANCELLED": "已中止"}


def _author(m):
    for e in (m.get("staff") or {}).get("edges", []):
        if re.search(r"Story|Original|Art", e.get("role") or ""):
            nm = e["node"]["name"]
            return nm.get("native") or nm.get("full") or ""
    return ""


def manga_from_anilist(country, origin, n=6, fmt=("MANGA", "ONE_SHOT")):
    out = []
    for m in _anilist(Q_MANGA, {"c": country, "n": n, "fmt": list(fmt)}):
        out.append({"cat": "comic", "origin": origin, "title_orig": m["title"].get("native") or m["title"].get("romaji") or "",
                    "_en": m["title"].get("english") or m["title"].get("romaji") or "",
                    "_syn": [x for x in (m.get("synonyms") or []) if re.search(r"[一-鿿]", x)][:3],
                    "author": _author(m), "status": STATUS_ZH.get(m.get("status"), ""),
                    "latest": ("第%d話" % m["chapters"]) if m.get("chapters") else "",
                    "_desc": clean_text(m.get("description"), 700), "_genres": m.get("genres") or [],
                    "image": (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or "",
                    "imageSrc": "AniList",
                    "watch": [{"name": l["site"], "url": l["url"]} for l in (m.get("externalLinks") or []) if l.get("type") in ("STREAMING", "INFO")][:3]
                    or [{"name": "AniList", "url": m.get("siteUrl")}]})
    return out


def comic_8comic(limit=15):
    """無限動漫 更新列表：『- 作品名 - 漫畫N - YYYY-MM-DD』。"""
    soup = BeautifulSoup(http_get("https://www.8comic.com/comic/u-1.html"), "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="/html/"]'):
        txt = a.get_text(" ", strip=True)
        m = re.match(r"^-?\s*(.+?)\s+-\s+(\S+?)\s+-\s+(\d{4}-\d{2}-\d{2})", txt)
        idm = re.search(r"/html/(\d+)\.html", a.get("href", ""))
        if not m or not idm or "登入觀看" in txt:
            continue
        title = (a.get("title") or m.group(1)).strip()
        if title in seen:
            continue
        seen.add(title)
        out.append({"cat": "comic", "origin": "連載更新", "title": to_tw(title), "latest": m.group(2).replace("漫畫", "第") + ("話" if re.search(r"\d$", m.group(2)) else ""),
                    "status": "連載中", "freq": "無限動漫 %s 更新" % m.group(3)[5:], "synopsis": "",
                    "image": "https://www.8comic.com/pics/0/%s.jpg" % idm.group(1), "imageSrc": "無限動漫",
                    "watch": [{"name": "無限動漫", "url": a["href"] if a["href"].startswith("http") else "https://www.8comic.com" + a["href"]}],
                    "_date": m.group(3)})
        if len(out) >= limit:
            break
    return out


def comic_manhuaren(limit=12):
    """漫畫人 最近更新（/manhua-list-s2/）：封面、標題、最新話。"""
    html_ = http_get("https://www.manhuaren.com/manhua-list-s2/")
    soup = BeautifulSoup(html_, "html.parser")
    out, seen = [], set()
    for li in soup.select("li"):
        a = li.find("a", href=re.compile(r"^/manhua-[\w-]+/?$"))
        if not a:
            continue
        img = li.find("img")
        title = (a.get("title") or (img.get("alt") if img else "") or a.get_text(" ", strip=True)).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        mm = re.search(r"(第\s*[\d\.]+\s*[话話回卷])", li.get_text(" ", strip=True))
        out.append({"cat": "comic", "origin": "連載更新", "title": to_tw(title), "latest": to_tw(mm.group(1).replace(" ", "")) if mm else "有更新",
                    "status": "連載中", "freq": "漫畫人 最近更新",
                    "image": (img.get("data-src") or img.get("src") or "") if img else "", "imageSrc": "漫畫人",
                    "watch": [{"name": "漫畫人", "url": "https://www.manhuaren.com" + a["href"]}]})
        if len(out) >= limit:
            break
    return out


def collect_comic():
    items = []
    jp = source("anilist_manga_jp", "AniList 日漫熱門", "acgn", manga_from_anilist, "JP", "日漫")
    kr = source("anilist_manga_kr", "AniList 韓漫熱門", "acgn", manga_from_anilist, "KR", "韓漫", 6, ("MANGA",))
    if not jp or not kr:  # 備援：Jikan（MyAnimeList）
        jk = source("jikan_manga", "Jikan 連載中熱門漫畫（備援）", "acgn", manga_from_jikan) or []
        if not jp:
            jp = [x for x in jk if x["origin"] == "日漫"]
        if not kr:
            kr = [x for x in jk if x["origin"] == "韓漫"]
    items += (jp or []) + (kr or [])
    items += source("8comic", "無限動漫 更新列表", "comics", comic_8comic) or []
    items += source("manhuaren", "漫畫人 最近更新", "comics", comic_manhuaren) or []
    return items


def manga_from_jikan():
    j = http_get("https://api.jikan.moe/v4/top/manga", params={"filter": "publishing", "limit": 15}, as_json=True)
    out = []
    for m in j.get("data", []):
        typ = (m.get("type") or "").lower()
        origin = "韓漫" if typ == "manhwa" else ("日漫" if typ in ("manga", "one-shot") else None)
        if not origin:
            continue
        out.append({"cat": "comic", "origin": origin, "title_orig": m.get("title_japanese") or m.get("title"), "_en": m.get("title_english") or m.get("title"),
                    "author": ", ".join(a["name"] for a in (m.get("authors") or [])[:2]), "status": "連載中",
                    "latest": ("第%d話" % m["chapters"]) if m.get("chapters") else "", "_desc": clean_text(m.get("synopsis"), 700),
                    "_genres": [g["name"] for g in m.get("genres") or []],
                    "image": ((m.get("images") or {}).get("jpg") or {}).get("large_image_url", ""), "imageSrc": "MyAnimeList",
                    "watch": [{"name": "MyAnimeList", "url": m.get("url")}]})
    return out


# ================================================================ 遊戲
def steam_featured():
    j = http_get("https://store.steampowered.com/api/featuredcategories/", params={"cc": "tw", "l": "tchinese"}, as_json=True)
    picks = []
    for key, n in (("new_releases", 5), ("coming_soon", 5)):
        for it in ((j.get(key) or {}).get("items") or [])[:n * 2]:
            if it.get("id") and it.get("type", 0) == 0 and it["id"] not in [p[0] for p in picks]:
                picks.append((it["id"], key))
            if sum(1 for p in picks if p[1] == key) >= n:
                break
    out = []
    for appid, key in picks:
        try:
            d = http_get("https://store.steampowered.com/api/appdetails", params={"appids": appid, "l": "tchinese", "cc": "tw"}, as_json=True)
            d = (d.get(str(appid)) or {}).get("data") or {}
        except Exception:
            continue
        if not d or d.get("type") != "game":
            continue
        genres = [g.get("description", "") for g in d.get("genres") or []]
        indie = any(g in ("獨立製作", "Indie", "独立") for g in genres) or any(str(g.get("id")) == "23" for g in d.get("genres") or [])
        plats = ["PC/Steam"] + (["Mac"] if (d.get("platforms") or {}).get("mac") else [])
        price = ("免費" if d.get("is_free") else (d.get("price_overview") or {}).get("final_formatted") or "未定價")
        rd = d.get("release_date") or {}
        out.append({"cat": "games", "title": d.get("name"), "developer": ", ".join((d.get("developers") or [])[:2]),
                    "platform": "Indie" if indie else "PC/Steam", "platforms": plats,
                    "release": ("即將推出：" if rd.get("coming_soon") else "") + (rd.get("date") or ""),
                    "genre": "、".join(genres[:3]), "price": price, "_desc": clean_text(d.get("short_description"), 600),
                    "image": d.get("header_image", ""), "imageSrc": "Steam",
                    "screenshots": [s.get("path_thumbnail") for s in (d.get("screenshots") or [])[:3] if s.get("path_thumbnail")],
                    "watch": [{"name": "Steam 商店頁", "url": "https://store.steampowered.com/app/%s/" % appid}]})
        time.sleep(1.2)
    return out


def mobile_games(limit=6):
    """App Store（台灣）免費榜 → iTunes Lookup 篩出遊戲類（genreId 6014）。"""
    feed = http_get("https://rss.marketingtools.apple.com/api/v2/tw/apps/top-free/100/apps.json", as_json=True)
    ids = [r["id"] for r in (feed.get("feed") or {}).get("results", [])][:100]
    out = []
    for i in range(0, len(ids), 50):
        j = http_get("https://itunes.apple.com/lookup", params={"id": ",".join(ids[i:i + 50]), "country": "tw"}, as_json=True)
        for r in j.get("results", []):
            if str(r.get("primaryGenreId")) != "6014" and "6014" not in [str(g) for g in r.get("genreIds") or []]:
                continue
            out.append({"cat": "games", "title": r.get("trackName"), "developer": r.get("artistName", ""), "platform": "手機",
                        "platforms": ["iOS", "Android（多數同步）"], "release": "上架 %s" % (r.get("releaseDate") or "")[:10],
                        "genre": "、".join([g for g in r.get("genres") or [] if g not in ("遊戲", "Games")][:3]),
                        "price": r.get("formattedPrice") or "免費", "_desc": clean_text(r.get("description"), 600),
                        "image": r.get("artworkUrl512") or r.get("artworkUrl100", ""), "imageSrc": "App Store",
                        "screenshots": (r.get("screenshotUrls") or [])[:3],
                        "watch": [{"name": "App Store", "url": r.get("trackViewUrl")}, {"name": "Google Play 搜尋", "url": "https://play.google.com/store/search?c=apps&q=" + quote(r.get("trackName") or "")}],
                        "_rel": (r.get("releaseDate") or "")[:10]})
    out.sort(key=lambda x: x["_rel"], reverse=True)   # 越新上架越前面
    return out[:limit]


def collect_games():
    items = source("steam", "Steam 新推出／即將推出", "acgn", steam_featured) or []
    items += source("appstore", "App Store 台灣免費榜（遊戲）", "acgn", mobile_games) or []
    return items


# ================================================================ 小說
def jjwxc_rank(limit=8):
    """晉江文學城 月榜（orderstr=5）。網站為 GB 編碼、簡體字。"""
    html_ = http_get("https://www.jjwxc.net/topten.php", params={"orderstr": 5, "t": 0}, encoding="gb18030")
    soup = BeautifulSoup(html_, "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="onebook.php?novelid="]'):
        title = a.get_text(strip=True).strip("《》")
        nid = re.search(r"novelid=(\d+)", a["href"])
        if not title or not nid or nid.group(1) in seen:
            continue
        seen.add(nid.group(1))
        row = a.find_parent("tr")
        au = row.find("a", href=re.compile("oneauthor")) if row else None
        url = "https://www.jjwxc.net/onebook.php?novelid=%s" % nid.group(1)
        it = {"cat": "novel", "origin": "華文網文", "title": to_tw(title), "author": to_tw(au.get_text(strip=True)) if au else "",
              "watch": [{"name": "晉江文學城", "url": url}], "_desc": ""}
        try:  # 作品頁：文案、狀態、字數
            page = BeautifulSoup(http_get(url, encoding="gb18030"), "html.parser")
            intro = page.find(id="novelintro")
            it["_desc"] = to_tw(clean_text(intro.get_text(" ", strip=True) if intro else "", 700))
            txt = page.get_text(" ", strip=True)
            st = re.search(r"文章进度：\s*(\S+)", txt)
            wc = re.search(r"全文字数：\s*([\d,]+)字", txt)
            it["status"] = "已完結" if st and "完结" in st.group(1) else ("連載中" if st else "")
            it["length"] = ("約 %d 萬字" % (int(wc.group(1).replace(",", "")) // 10000)) if wc else ""
            time.sleep(1)
        except Exception:
            pass
        out.append(it)
        if len(out) >= limit:
            break
    return out


def naver_series(limit=6):
    html_ = http_get("https://series.naver.com/novel/top100List.series", params={"rankingTypeCode": "DAILY", "categoryCode": "ALL"})
    soup = BeautifulSoup(html_, "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="productNo="]'):
        title = (a.get("title") or a.get_text(" ", strip=True)).strip()
        pid = re.search(r"productNo=(\d+)", a["href"])
        if not title or not pid or pid.group(1) in seen or len(title) < 2:
            continue
        seen.add(pid.group(1))
        li = a.find_parent("li")
        img = li.find("img") if li else None
        au = li.find(class_=re.compile("author")) if li else None
        out.append({"cat": "novel", "origin": "韓國網路小說", "title_orig": title, "author": au.get_text(strip=True) if au else "",
                    "image": img.get("src", "") if img else "", "imageSrc": "Naver Series", "_desc": "",
                    "watch": [{"name": "Naver Series", "url": "https://series.naver.com/novel/detail.series?productNo=%s" % pid.group(1)}]})
        if len(out) >= limit:
            break
    return out


def novels_from_anilist(country, origin, n=6):
    out = []
    for m in _anilist(Q_MANGA, {"c": country, "n": n, "fmt": ["NOVEL"]}):
        out.append({"cat": "novel", "origin": origin, "title_orig": m["title"].get("native") or m["title"].get("romaji") or "",
                    "_en": m["title"].get("english") or m["title"].get("romaji") or "",
                    "_syn": [x for x in (m.get("synonyms") or []) if re.search(r"[一-鿿]", x)][:3],
                    "author": _author(m), "status": STATUS_ZH.get(m.get("status"), ""),
                    "length": ("%d 章" % m["chapters"]) if m.get("chapters") else "",
                    "_desc": clean_text(m.get("description"), 700), "_genres": m.get("genres") or [],
                    "image": (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or "",
                    "imageSrc": "AniList", "watch": [{"name": "AniList", "url": m.get("siteUrl")}]})
    return out


def collect_novel():
    items = []
    items += source("jjwxc", "晉江文學城 月榜", "acgn", jjwxc_rank) or []
    items += source("anilist_novel_cn", "AniList 華文網文熱門", "acgn", novels_from_anilist, "CN", "華文網文", 5) or []
    items += source("naver_series", "Naver Series 小說排行", "acgn", naver_series) or []
    items += source("anilist_novel_kr", "AniList 韓國網路小說熱門", "acgn", novels_from_anilist, "KR", "韓國網路小說", 6) or []
    return items


# ================================================================ Gemini 整理成繁中卡片
FIELDS = {
    "anime": "title（台灣常用中文譯名；不確定就用提供的中文名或原名）, synopsis（繁中 40~70 字）, hook（推薦理由 20~40 字）, tags（2~4 個繁中標籤）",
    "comic": "title（台灣常用中文譯名；不確定就意譯並保留原名）, synopsis（繁中 40~70 字）, hook（推薦理由 20~40 字）, tags（2~4 個）, freq（若資料有更新頻率，否則空字串）",
    "games": "synopsis（繁中 40~70 字）, highlights（3 條玩法亮點，每條 15 字內）, hook（推薦理由 20~40 字）, tags（2~4 個）",
    "novel": "title（中文書名；韓文作品請翻成中文並保留原名）, synopsis（40~70 字）, genre（類型，如 仙俠・經營）, setting（世界觀 20~40 字）, protagonist（主角設定 20~40 字）, hook（推薦理由）, readers（適合哪種讀者）, adaptation（資料有提到改編才寫，否則空字串）, tags（2~4 個）",
}


def enrich(cat, items):
    """只把『資料裡已有的內容』翻譯整理成繁中欄位；不得自行捏造。沒有 Gemini 時改用原始文字。"""
    if not items:
        return
    if gemini_available():
        payload = [{"id": it["id"], "title": it.get("title") or "", "title_orig": it.get("title_orig") or "", "english": it.get("_en") or "",
                    "chinese_alias": it.get("_syn") or [], "description": it.get("_desc_zh") or it.get("_desc") or "",
                    "genres": it.get("_genres") or [], "origin": it.get("origin") or ""} for it in items]
        for i in range(0, len(payload), 10):
            chunk = payload[i:i + 10]
            res = gemini_json(
                "以下是從公開資料庫抓到的%s資料（JSON）。請為每一筆輸出欄位：%s。\n"
                "規則：只能根據 description、genres 等提供的資訊撰寫，不可加入資料中沒有的劇情或事實；資訊不足的欄位給空字串。"
                "輸出格式：{\"<id>\": {欄位...}, ...}\n\n%s" % ({"anime": "動畫", "comic": "漫畫", "games": "遊戲", "novel": "小說"}[cat], FIELDS[cat],
                                                           json.dumps(chunk, ensure_ascii=False)),
                system="你是台灣的 ACGN 編輯，文字精簡、口語自然。", temperature=0.3, expect=dict) or {}
            for it in items:
                r = res.get(it["id"])
                if not isinstance(r, dict):
                    continue
                for k, v in r.items():
                    if k in ("title",) and it.get("title") and it.get("origin") == "連載更新":
                        continue
                    if isinstance(v, (str, list)) and v:
                        it[k] = v
                it["_ai"] = True
    for it in items:   # 降級：無 Gemini 或沒回傳
        it.setdefault("title", (it.get("_syn") or [None])[0] or it.get("title_orig") or it.get("_en") or "（未命名）")
        if not it.get("title"):
            it["title"] = it.get("title_orig") or it.get("_en") or "（未命名）"
        if not it.get("synopsis"):
            it["synopsis"] = clean_text(it.get("_desc_zh") or it.get("_desc") or "", 120)
        if not it.get("tags") and it.get("_genres"):
            it["tags"] = it["_genres"][:3]


def _finalize(it):
    it["mod"] = "acgn"
    key_title = it.get("title_orig") or it.get("title") or it.get("_en")
    it["id"] = make_id(it["cat"], key_title, "" if it.get("origin") == "連載更新" else it.get("author", ""))
    return it


def run():
    db = load_json(PATH, {"meta": {}, "items": []})
    old = db.get("items", [])
    old_ids = {x["id"] for x in old}
    fresh = []
    for fn in (collect_anime, collect_comic, collect_games, collect_novel):
        try:
            fresh += [_finalize(x) for x in fn()]
        except Exception as e:  # noqa
            log("collect 失敗", fn.__name__, e)
    seen, uniq = set(), []          # 同一次抓取中重複的作品只留第一筆
    for it in fresh:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    fresh = uniq
    # 只有『新作品』或『尚未整理過』的才送 Gemini，省額度
    by_cat = {}
    old_map = {x["id"]: x for x in old}
    for it in fresh:
        if it["id"] not in old_ids or not old_map[it["id"]].get("_ai"):
            by_cat.setdefault(it["cat"], []).append(it)
    for cat, lst in by_cat.items():
        enrich(cat, lst)
    for it in fresh:   # 既有作品的標題、簡介不會被覆蓋（merge 只更新集數等易變欄位）
        for k in [k for k in it if k.startswith("_") and k != "_ai"]:
            it.pop(k, None)
    items, new_ids = merge_items(old, fresh, volatile=VOLATILE, cap=CAP,
                                 cap_key=lambda x: x["cat"] + ("_upd" if x.get("origin") == "連載更新" else ""))
    db["items"] = items
    db["meta"] = {"last_updated": now().isoformat(timespec="minutes"), "seed": False,
                  "counts": {c: sum(1 for x in items if x["cat"] == c) for c in ("anime", "comic", "games", "novel")}}
    save_json(PATH, db)
    log("ACGN 完成：新增 %d，共 %d" % (len(new_ids), len(items)))
    return len(new_ids)
