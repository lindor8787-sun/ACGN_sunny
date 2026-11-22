# -*- coding: utf-8 -*-
"""共用工具：路徑、時間、HTTP、JSON、ID、合併、繁簡轉換、來源狀態、Gemini 呼叫。"""
import os, re, json, time, hashlib, html, unicodedata, datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ = dt.timezone(dt.timedelta(hours=8))          # 台北時間（無日光節約）


def now():
    return dt.datetime.now(TZ)


def today():
    return now().strftime("%Y-%m-%d")


def days_ago(n):
    return (now() - dt.timedelta(days=n)).strftime("%Y-%m-%d")


def log(*a):
    print("[%s]" % now().strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- HTTP
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 SunnyHub/1.0 (+https://github.com/lindor8787-sun/sunny-hub)")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en;q=0.7"})


class FetchError(RuntimeError):
    pass


def http_get(url, *, params=None, timeout=25, retries=2, as_json=False, encoding=None, headers=None):
    last = None
    for i in range(retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504):
                raise FetchError("HTTP %s" % r.status_code)
            r.raise_for_status()
            if as_json:
                return r.json()
            if encoding:
                r.encoding = encoding
            elif not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except Exception as e:  # noqa
            last = e
            if i < retries:
                time.sleep(2 * (i + 1))
    raise FetchError("GET %s 失敗：%s" % (url, last))


def http_post_json(url, payload, *, timeout=25, retries=2, headers=None):
    last = None
    for i in range(retries + 1):
        try:
            r = SESSION.post(url, json=payload, timeout=timeout, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504):
                raise FetchError("HTTP %s" % r.status_code)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa
            last = e
            if i < retries:
                time.sleep(3 * (i + 1))
    raise FetchError("POST %s 失敗：%s" % (url, last))


# ---------------------------------------------------------------- JSON 檔
def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


# ---------------------------------------------------------------- 文字
def clean_text(s, limit=None):
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


try:  # 繁簡轉換（簡體 → 台灣正體）
    from opencc import OpenCC
    try:
        _CC = OpenCC("s2twp")
    except Exception:
        _CC = OpenCC("s2twp.json")
except Exception:  # 套件不存在時原樣輸出
    _CC = None


def to_tw(s):
    if not s or _CC is None:
        return s
    try:
        return _CC.convert(s)
    except Exception:
        return s


def norm_key(s):
    """產生穩定比對用字串：全形轉半形、去空白標點、小寫、轉正體。"""
    s = unicodedata.normalize("NFKC", to_tw(str(s or ""))).lower()
    s = re.sub(r"（範例）|\(範例\)", "", s)
    return re.sub(r"[\W_]+", "", s)


def make_id(cat, *parts):
    key = "|".join(norm_key(p) for p in parts if p)
    if not key:
        key = str(time.time())
    return "%s_%s" % (cat, hashlib.sha1(key.encode("utf-8")).hexdigest()[:12])


# ---------------------------------------------------------------- 合併
def merge_items(existing, fresh, *, volatile=(), keep_days=None, cap=None, cap_key=None):
    """以 id 去重合併。
    - 既有項目：只更新 volatile 欄位（有新值才更新），保留原 added；有變動則 updated=今天。
    - 新項目：added = updated = 今天。
    - keep_days：刪除 added 超過 N 天的項目。
    - cap / cap_key：每組（例如每個 cat）最多保留 cap 筆，依 updated、added 由新到舊。
    回傳 (合併後清單, 新增 id 清單)
    """
    t = today()
    by_id = {}
    for it in existing:
        if it.get("seed"):        # 範例資料：第一次真實執行時自動移除
            continue
        if it.get("id"):
            by_id[it["id"]] = it
    new_ids = []
    for it in fresh:
        if not it.get("id"):
            continue
        old = by_id.get(it["id"])
        if old is None:
            it.setdefault("added", t)
            it.setdefault("updated", t)
            by_id[it["id"]] = it
            new_ids.append(it["id"])
            continue
        changed = False
        for k in volatile:
            v = it.get(k)
            if v not in (None, "", [], {}) and old.get(k) != v:
                old[k] = v
                changed = True
        for k, v in it.items():           # 補齊舊資料缺的欄位
            if k not in old or old.get(k) in (None, "", [], {}):
                if v not in (None, "", [], {}):
                    old[k] = v
        if changed:
            old["updated"] = t
    items = list(by_id.values())
    if keep_days is not None:
        limit = days_ago(keep_days)
        items = [x for x in items if (x.get("added") or t) >= limit]
    items.sort(key=lambda x: (x.get("updated", ""), x.get("added", "")), reverse=True)
    if cap:
        groups, out = {}, []
        for x in items:
            g = cap_key(x) if cap_key else "_"
            groups[g] = groups.get(g, 0) + 1
            if groups[g] <= cap:
                out.append(x)
        items = out
    return items, new_ids


# ---------------------------------------------------------------- 來源狀態
class Status:
    """記錄每個資料來源最近一次成功／失敗，寫入 data/status.json 給網頁「系統狀態」顯示。"""

    def __init__(self):
        self.path = DATA / "status.json"
        self.d = load_json(self.path, {"sources": {}, "runs": []})
        self.d.setdefault("sources", {})
        self.d.setdefault("runs", [])
        self.notes = []

    def record(self, key, name, module, ok, count=0, error=""):
        s = self.d["sources"].setdefault(key, {"name": name, "module": module})
        s.update(name=name, module=module, ok=bool(ok), last_run=now().isoformat(timespec="minutes"), count=count)
        if ok:
            s["last_ok"] = s["last_run"]
            s["error"] = ""
        else:
            s["error"] = str(error)[:300]

    def note(self, msg):
        self.notes.append(msg)
        log("NOTE", msg)

    def finish(self, modules, model_info):
        self.d["updated"] = now().isoformat(timespec="minutes")
        self.d["model"] = model_info
        self.d["runs"] = ([{"at": self.d["updated"], "modules": modules, "notes": self.notes[-12:]}] + self.d["runs"])[:20]
        save_json(self.path, self.d)


STATUS = Status()


def source(key, name, module, fn, *a, **kw):
    """執行一個資料來源；失敗不拋出，回傳 None 並記錄。"""
    try:
        res = fn(*a, **kw)
        n = len(res) if hasattr(res, "__len__") else (1 if res else 0)
        STATUS.record(key, name, module, n > 0, n, "" if n else "回傳 0 筆")
        log("✔" if n else "✘", name, n)
        return res if n else None
    except Exception as e:  # noqa
        STATUS.record(key, name, module, False, 0, e)
        log("✘", name, e)
        return None


# ---------------------------------------------------------------- Gemini
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
MAX_CALLS = int(os.environ.get("GEMINI_MAX_CALLS", "30"))
REST = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
_calls = {"n": 0, "by_model": {}}
_dead_models = set()


class GeminiError(RuntimeError):
    pass


def gemini_available():
    return bool(API_KEY)


def _quota(e):
    s = str(e)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _model_gone(e):
    s = str(e)
    return any(x in s for x in ("404", "NOT_FOUND", "403", "PERMISSION_DENIED", "not found", "not supported"))


def _sdk_call(model, prompt):
    """官方 SDK（google-genai）Interactions API：client.interactions.create(model, input)。"""
    from google import genai  # noqa
    client = genai.Client(api_key=API_KEY)
    r = client.interactions.create(model=model, input=prompt)
    text = getattr(r, "output_text", None)
    if not text:
        raise GeminiError("SDK 回傳空白")
    return text


def _rest_call(model, prompt, system=None, temperature=0.4):
    """備援：generateContent REST（官方文件標示為 legacy，但仍完整支援）。"""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = SESSION.post(REST % model, json=body, timeout=180,
                     headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"})
    if r.status_code != 200:
        raise GeminiError("HTTP %s %s" % (r.status_code, r.text[:300]))
    j = r.json()
    parts = (((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        raise GeminiError("REST 回傳空白：%s" % str(j)[:200])
    return text


def gemini(prompt, *, system=None, temperature=0.4):
    """呼叫 Gemini（免費層，純文字生成，不使用付費的搜尋 grounding）。
    依序嘗試：主模型 → 備援模型；每個模型先用 SDK，失敗再用 REST；額度用完自動換模型。"""
    if not API_KEY:
        raise GeminiError("未設定 GEMINI_API_KEY")
    if _calls["n"] >= MAX_CALLS:
        raise GeminiError("本次執行已達呼叫上限 %d" % MAX_CALLS)
    full = (system + "\n\n" + prompt) if system else prompt
    last = None
    for model in [m for m in (MODEL, FALLBACK_MODEL) if m and m not in _dead_models]:
        for attempt in range(3):
            try:
                _calls["n"] += 1
                _calls["by_model"][model] = _calls["by_model"].get(model, 0) + 1
                try:
                    return _sdk_call(model, full)
                except ImportError:
                    return _rest_call(model, prompt, system, temperature)
                except Exception as e_sdk:  # noqa
                    if _quota(e_sdk) or _model_gone(e_sdk):
                        raise
                    return _rest_call(model, prompt, system, temperature)
            except Exception as e:  # noqa
                last = e
                if _quota(e) or _model_gone(e):
                    _dead_models.add(model)
                    STATUS.note("模型 %s 暫不可用（%s），改用備援" % (model, str(e)[:80]))
                    break
                time.sleep(6 * (attempt + 1))
    raise GeminiError("Gemini 呼叫失敗：%s" % last)


def model_info():
    return {"model": MODEL, "fallback": FALLBACK_MODEL, "calls": _calls["n"], "by_model": _calls["by_model"],
            "unavailable": sorted(_dead_models), "has_key": bool(API_KEY)}


def extract_json(text):
    """從模型回覆萃取 JSON（去除 ``` 圍欄與前後說明文字）。失敗回傳 None。"""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: (t.find(p[0]) if t.find(p[0]) >= 0 else 1e9))
    for open_c, close_c in pairs:   # 從最先出現的括號開始找
        start = t.find(open_c)
        while start != -1:
            depth, ins, esc_ = 0, False, False
            for i in range(start, len(t)):
                ch = t[i]
                if ins:
                    if esc_:
                        esc_ = False
                    elif ch == "\\":
                        esc_ = True
                    elif ch == '"':
                        ins = False
                    continue
                if ch == '"':
                    ins = True
                elif ch == open_c:
                    depth += 1
                elif ch == close_c:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(t[start:i + 1])
                        except Exception:
                            break
            start = t.find(open_c, start + 1)
    return None


def gemini_json(prompt, *, system=None, temperature=0.4, expect=dict):
    """呼叫 Gemini 並解析 JSON；格式不對就重試一次。失敗回傳 None（呼叫端自行降級）。"""
    sys_ = (system or "") + "\n只輸出 JSON，不要任何說明文字或 ``` 圍欄。所有中文一律使用台灣繁體中文。"
    for _ in range(2):
        try:
            v = extract_json(gemini(prompt, system=sys_.strip(), temperature=temperature))
        except GeminiError as e:
            STATUS.note(str(e)[:160])
            return None
        if isinstance(v, expect):
            return v
        if expect is list and isinstance(v, dict):
            for val in v.values():
                if isinstance(val, list):
                    return val
    return None
