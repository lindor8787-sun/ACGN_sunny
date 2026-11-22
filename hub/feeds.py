# -*- coding: utf-8 -*-
"""RSS / Atom 讀取（feedparser），統一輸出 {title, link, summary, content, published, image}。"""
import re, time, calendar, datetime as dt
from urllib.parse import urljoin

import feedparser

from .common import http_get, clean_text, TZ


def _img(e):
    for k in ("media_content", "media_thumbnail"):
        for m in e.get(k) or []:
            if m.get("url"):
                return m["url"]
    for l in e.get("links") or []:
        if (l.get("type") or "").startswith("image"):
            return l.get("href")
    m = re.search(r'<img[^>]+src="([^"]+)"', (e.get("summary") or "") + str(e.get("content") or ""))
    return m.group(1) if m else ""


def fetch_feed(url, *, base=None, limit=30, max_age_hours=72):
    text = http_get(url)
    f = feedparser.parse(text)
    if not f.entries:
        raise RuntimeError("RSS 沒有項目（%s）" % (f.get("bozo_exception") or "格式不符"))
    out, now_ts = [], time.time()
    for e in f.entries[: limit * 2]:
        tp = e.get("published_parsed") or e.get("updated_parsed")
        ts = calendar.timegm(tp) if tp else now_ts
        if max_age_hours and now_ts - ts > max_age_hours * 3600:
            continue
        link = e.get("link") or ""
        if base and link.startswith("/"):
            link = urljoin(base, link)
        content = ""
        if e.get("content"):
            content = e["content"][0].get("value", "")
        out.append({"title": clean_text(e.get("title")), "link": link,
                    "summary": clean_text(e.get("summary"), 900), "content": clean_text(content, 1800),
                    "published": dt.datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M"), "image": _img(e)})
        if len(out) >= limit:
            break
    return out
