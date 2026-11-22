# -*- coding: utf-8 -*-
"""字庫：英文字根家族、日文 N1~N3 商用文法。每次新增少量並去重，標上 added 日期（網頁顯示 NEW）。"""
import json

from .common import DATA, today, log, load_json, save_json, gemini_json, gemini_available, norm_key

PATH = DATA / "lexicon.json"


def _db():
    d = load_json(PATH, {})
    d.setdefault("updated", {"fam": "", "jlpt": ""})
    d.setdefault("fam", [])
    d.setdefault("jlpt", {"N1": [], "N2": [], "N3": []})
    for lv in ("N1", "N2", "N3"):
        d["jlpt"].setdefault(lv, [])
    return d


def add_families(d, n=3):
    have = {norm_key(x["r"][0] if x["r"][0] != "—" else x["r"][2]) for x in d["fam"]}
    res = gemini_json(
        "請提供 %d 組職場常用、且不在下列清單中的英文字根家族：%s。\n每組輸出 5 個字串："
        "[動詞, 名詞（多個用 / 分隔）, 形容詞, 副詞（沒有就 —）, 商用搭配＋空格＋中文]，例如 "
        "[\"allocate\",\"allocation\",\"allocated\",\"—\",\"budget allocation 預算分配\"]。輸出格式：[[...],[...]]"
        % (n, ", ".join(sorted(have)[:200])), temperature=0.6, expect=list) or []
    added = 0
    for r in res:
        if isinstance(r, list) and len(r) == 5 and all(isinstance(s, str) for s in r):
            k = norm_key(r[0] if r[0] != "—" else r[2])
            if k and k not in have:
                d["fam"].insert(0, {"r": r, "added": today()})
                have.add(k)
                added += 1
    if added:
        d["updated"]["fam"] = today()
    return added


def add_jlpt(d, per_level=1):
    have = {norm_key(x["g"]) for lv in d["jlpt"].values() for x in lv}
    res = gemini_json(
        "請提供日本職場常用的 JLPT 文法：N1、N2、N3 各 %d 則，不可與下列重複：%s。\n"
        "每則輸出 {\"level\":\"N1\",\"g\":\"〜文法\",\"m\":\"繁中意思\",\"ex\":\"自然的商用例句\"}。輸出格式：[{...}]"
        % (per_level, "、".join(sorted(have)[:200])), temperature=0.6, expect=list) or []
    added = 0
    for r in res:
        if isinstance(r, dict) and r.get("level") in d["jlpt"] and r.get("g") and r.get("ex"):
            k = norm_key(r["g"])
            if k and k not in have:
                d["jlpt"][r["level"]].insert(0, {"g": r["g"], "m": r.get("m", ""), "ex": r["ex"], "added": today()})
                have.add(k)
                added += 1
    if added:
        d["updated"]["jlpt"] = today()
    return added


def run(kind="both"):
    if not gemini_available():
        log("字庫：未設定 GEMINI_API_KEY，略過")
        return 0
    d = _db()
    n = 0
    if kind in ("both", "fam"):
        n += add_families(d, 3 if kind == "both" else 5)
    if kind in ("both", "jlpt"):
        n += add_jlpt(d, 1 if kind == "both" else 2)
    save_json(PATH, d)
    log("字庫完成：新增 %d" % n)
    return n
