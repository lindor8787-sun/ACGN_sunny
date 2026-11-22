#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建置離線辭典分檔（由 GitHub Actions 的 build-dict 工作執行，不需在本機跑）。

英文：ECDICT（MIT 授權，skywind3000/ECDICT）→ 篩常用詞 → 中文轉台灣正體 → data/dict/en/<前兩個字母>.json
日文：JMdict 常用詞（EDRDG，CC BY-SA 4.0，scriptin/jmdict-simplified）→ data/dict/ja/<首字碼位 % 64>.json
網頁查詢時只下載需要的那一小檔。分檔規則需與 index.html 的 lookup() 一致。
"""
import csv, io, json, re, sys, zipfile, tarfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hub.common import DATA, SESSION, to_tw, save_json, log, today  # noqa

ECDICT_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
JMDICT_API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
OUT = DATA / "dict"
EXCH = {"p": "過去式", "d": "過去分詞", "i": "現在分詞", "3": "第三人稱單數", "r": "比較級", "t": "最高級", "s": "複數"}
POS_EN = {"n.": "n.", "v.": "v.", "vt.": "vt.", "vi.": "vi.", "a.": "adj.", "adj.": "adj.", "ad.": "adv.", "adv.": "adv.",
          "prep.": "prep.", "conj.": "conj.", "pron.": "pron.", "int.": "int.", "num.": "num.", "art.": "art."}
POS_JA = [(r"^v5", "五段動詞"), (r"^v1", "一段動詞"), (r"^vs", "サ變動詞"), (r"^vk", "カ變動詞"), (r"^adj-i", "い形容詞"),
          (r"^adj-na", "な形容詞"), (r"^adj-no", "の形容詞"), (r"^adv", "副詞"), (r"^n", "名詞"), (r"^exp", "慣用表現"),
          (r"^suf", "接尾語"), (r"^pref", "接頭語"), (r"^prt", "助詞"), (r"^conj", "接續詞"), (r"^int", "感嘆詞"), (r"^aux", "助動詞")]


def en_shard(key):
    return re.sub(r"[^a-z]", "", key)[:2] or "_"


def ja_shard(key):
    return str(ord(key[0]) % 64)


def _int(s):
    try:
        return int(s or 0)
    except ValueError:
        return 0


def _lines(s):
    return [x.strip() for x in (s or "").replace("\\n", "\n").split("\n") if x.strip()]


def build_en(max_rank=60000):
    log("下載 ECDICT …")
    r = SESSION.get(ECDICT_URL, timeout=300)
    r.raise_for_status()
    rows = csv.DictReader(io.StringIO(r.content.decode("utf-8")))
    keep = []
    for row in rows:
        w = (row.get("word") or "").strip()
        if not w or len(w) > 40 or not re.match(r"^[A-Za-z][A-Za-z '\-\.]*$", w) or not row.get("translation"):
            continue
        frq, bnc = _int(row.get("frq")), _int(row.get("bnc"))
        if not ((0 < frq <= max_rank) or (0 < bnc <= max_rank) or row.get("tag") or _int(row.get("collins")) > 0 or row.get("oxford") == "1"):
            continue
        keep.append(row)
    log("ECDICT 保留 %d 筆，轉換繁體中 …" % len(keep))
    # 一次轉換大量文字以加速
    SEP = "⁣"
    big = SEP.join(r["translation"] for r in keep)
    tw = to_tw(big).split(SEP)
    shards = defaultdict(dict)
    for row, trans in zip(keep, tw):
        key = row["word"].strip().lower()
        defs = defaultdict(list)          # 英文定義依詞性分組，依序配給同詞性的中文義項
        for x in _lines(row.get("definition")):
            dm = re.match(r"^([a-z]+\.)\s*(.+)$", x)
            if dm:
                defs[dm.group(1)].append(dm.group(2))
        senses = []
        for line in _lines(trans)[:8]:
            m = re.match(r"^([a-z]+\.)\s*(.+)$", line)
            pos, zh = (POS_EN.get(m.group(1), m.group(1)), m.group(2)) if m else ("", line)
            d = defs[m.group(1)].pop(0) if m and defs.get(m.group(1)) else ""
            senses.append({"pos": pos, "zh": zh, "def": d[:160]})
        forms = []
        for part in (row.get("exchange") or "").split("/"):
            k, _, v = part.partition(":")
            if k in EXCH and v:
                forms.append("%s %s" % (EXCH[k], v))
        e = {"ph": ("/%s/" % row["phonetic"]) if row.get("phonetic") else "", "senses": senses}
        if forms:
            e["forms"] = "｜".join(forms)
        shards[en_shard(key)][key] = e
    for k, v in shards.items():
        save_json(OUT / "en" / ("%s.json" % k), v)
    return sum(len(v) for v in shards.values()), len(shards)


def build_ja():
    log("查詢 JMdict 最新版 …")
    rel = SESSION.get(JMDICT_API, timeout=60).json()
    asset = next(a for a in rel["assets"] if "jmdict-eng-common" in a["name"] and (a["name"].endswith(".zip") or a["name"].endswith(".tgz")))
    log("下載", asset["name"])
    blob = SESSION.get(asset["browser_download_url"], timeout=300).content
    if asset["name"].endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(blob))
        data = json.loads(z.read(next(n for n in z.namelist() if n.endswith(".json"))).decode("utf-8"))
    else:
        t = tarfile.open(fileobj=io.BytesIO(blob))
        m = next(x for x in t.getmembers() if x.name.endswith(".json"))
        data = json.loads(t.extractfile(m).read().decode("utf-8"))
    shards = defaultdict(dict)
    for w in data.get("words", []):
        kana = [k["text"] for k in w.get("kana", [])]
        senses = []
        for s in w.get("sense", [])[:6]:
            pos = ""
            for p in s.get("partOfSpeech", []):
                pos = next((zh for pat, zh in POS_JA if re.match(pat, p)), "")
                if pos:
                    break
            gl = "; ".join(g["text"] for g in s.get("gloss", [])[:4])
            if gl:
                senses.append({"pos": pos, "zh": "", "def": gl})
        if not senses:
            continue
        e = {"ph": kana[0] if kana else "", "senses": senses}
        for key in [k["text"] for k in w.get("kanji", [])] + kana:
            if key and key not in shards[ja_shard(key)]:
                shards[ja_shard(key)][key] = e
    for k, v in shards.items():
        save_json(OUT / "ja" / ("%s.json" % k), v)
    return sum(len(v) for v in shards.values()), len(shards)


def main():
    meta = {"built": today()}
    try:
        meta["en_entries"], meta["en_files"] = build_en()
    except Exception as e:
        meta["en_error"] = str(e)[:200]
    try:
        meta["ja_entries"], meta["ja_files"] = build_ja()
    except Exception as e:
        meta["ja_error"] = str(e)[:200]
    meta["licenses"] = {"ECDICT": "MIT License — https://github.com/skywind3000/ECDICT",
                        "JMdict": "EDRDG License / CC BY-SA 4.0 — https://www.edrdg.org/edrdg/licence.html （經 scriptin/jmdict-simplified 轉換）"}
    save_json(OUT / "meta.json", meta)
    log(meta)
    if "en_error" in meta and "ja_error" in meta:
        sys.exit(1)


if __name__ == "__main__":
    main()
