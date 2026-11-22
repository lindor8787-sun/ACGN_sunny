# -*- coding: utf-8 -*-
"""站內詳解字典（data/dict/detail.json）：一個字詞列出『所有』意思＋中文＋情境＋例句。
來源：學習卡片的 dictWord、字庫新字、週報詞條，以及網頁送出的『請求 AI 詳解』Issue。"""
import json, re

from .common import DATA, log, load_json, save_json, gemini_json, gemini_available, days_ago

PATH = DATA / "dict" / "detail.json"
SPEC = ('{"<字詞>": {"lang":"en或ja","ph":"音標或假名讀音","level":"CEFR 或 JLPT 等級或「商用書面」",'
        '"forms":"詞形變化／相關詞（一行）","senses":[{"pos":"詞性","zh":"繁中意思","def":"英文或日文簡短定義",'
        '"ex":"例句","exZh":"例句繁中翻譯","scene":"使用情境（職場優先）"}],"syn":"近義","ant":"反義或 —","confuse":"易混淆說明"}}')


def key_of(word, lang):
    return word.strip().lower() if lang == "en" else word.strip()


def candidates(limit=8):
    detail = load_json(PATH, {})
    out = []
    for x in load_json(DATA / "lang.json", {"items": []})["items"]:
        if x.get("dictWord") and x.get("added", "") >= days_ago(3):
            out.append((x["dictWord"], x["cat"]))
    lex = load_json(DATA / "lexicon.json", {"fam": [], "jlpt": {}})
    for f in lex.get("fam", [])[:6]:
        if f["r"][0] != "—":
            out.append((f["r"][0], "en"))
    for lv in ("N1", "N2", "N3"):
        for g in (lex.get("jlpt") or {}).get(lv, [])[:2]:
            out.append((re.sub(r"^〜", "", g["g"]).split("（")[0], "ja"))
    seen, res = set(), []
    for w, l in out:
        k = key_of(w, l)
        if k and k not in detail and k not in seen and len(k) <= 40:
            seen.add(k)
            res.append((w, l))
    return res[:limit]


def generate(words):
    """words：[(字詞, 'en'|'ja')]。回傳新增筆數。"""
    if not words or not gemini_available():
        return 0
    detail = load_json(PATH, {})
    res = gemini_json(
        "請為下列字詞寫完整詳解。要求：列出『所有』常見意思（多義字務必分開列，2~6 個），每個意思都要有繁中、定義、例句＋翻譯、使用情境；"
        "例句盡量用職場情境。日文字詞的 def 用日文。輸出格式：%s\n\n字詞清單：%s"
        % (SPEC, json.dumps([{"word": w, "lang": l} for w, l in words], ensure_ascii=False)),
        system="你是嚴謹的雙語辭典編輯，不確定的資訊寧可留空。", temperature=0.2, expect=dict) or {}
    n = 0
    for w, l in words:
        e = res.get(w) or res.get(w.lower()) or res.get(key_of(w, l))
        if not isinstance(e, dict) or not isinstance(e.get("senses"), list) or not e["senses"]:
            continue
        e["lang"] = l
        e["senses"] = [s for s in e["senses"] if isinstance(s, dict) and (s.get("zh") or s.get("def"))][:8]
        detail[key_of(w, l)] = e
        n += 1
    save_json(PATH, detail)
    log("字典詳解：新增 %d" % n)
    return n


def run():
    return generate(candidates())
