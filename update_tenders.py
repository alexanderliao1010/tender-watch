#!/usr/bin/env python3
"""
每日抓取「新竹、桃園」招標中的工程案（預算 < 2,800 萬），輸出 docs/index.html。
資料來源：政府電子採購網（經 g0v 標案 API 鏡像 pcc-api.openfun.app / pcc.g0v.ronny.tw）
"""
import datetime as dt
import json
import os
import re
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

# ===== 可調整的設定 =====
BUDGET_MAX = 28_000_000          # 預算上限（不含）
LOOKBACK_DAYS = 45               # 往回掃描幾天的公告（等標期最長約 40 天）
REFETCH_RECENT_DAYS = 5          # 最近幾天的公告每次重抓（鏡像站可能延遲入庫）
REGION_KEYWORDS = {
    "新竹": ["新竹", "竹北", "竹東", "新埔", "關西", "湖口", "新豐", "芎林", "橫山",
             "北埔", "寶山", "峨眉", "尖石", "五峰", "香山"],
    "桃園": ["桃園", "中壢", "平鎮", "八德", "楊梅", "蘆竹", "大溪", "龍潭", "龜山",
             "大園", "觀音", "新屋", "復興"],
}
# 機關名稱不含地名、但位於新竹桃園的機關，可在這裡補關鍵字
EXTRA_UNIT_KEYWORDS = ["北區水資源分署", "石門"]
# =======================

TZ = ZoneInfo("Asia/Taipei")
HOSTS = ["https://pcc-api.openfun.app", "https://pcc.g0v.ronny.tw"]
BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE, "data", "cache.json")
OUT_FILE = os.path.join(BASE, "docs", "index.html")
TEMPLATE_FILE = os.path.join(BASE, "template.html")

TENDER_TYPE = re.compile(r"招標|公開取得")
SKIP_TYPE = re.compile(r"決標|閱覽|定期彙送")
CLOSED_TYPE = re.compile(r"決標|撤銷|停止|廢標")

session = requests.Session()
session.headers["User-Agent"] = "tender-watch/1.0 (daily github action)"
_debug_printed = False


def api(path):
    last = None
    for host in HOSTS:
        for attempt in range(3):
            try:
                r = session.get(host + path, timeout=30)
                if r.status_code == 200:
                    return r.json()
                last = f"{host} HTTP {r.status_code}"
            except Exception as e:  # 連線失敗或回傳非 JSON（例如防火牆頁）
                last = f"{host} {e}"
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def all_unit_keywords():
    kws = list(EXTRA_UNIT_KEYWORDS)
    for v in REGION_KEYWORDS.values():
        kws += v
    return kws


UNIT_KWS = all_unit_keywords()


def unit_match(name):
    return any(k in (name or "") for k in UNIT_KWS)


def region_from_address(addr):
    if re.search(r"新竹[縣市]", addr or ""):
        return "新竹"
    if re.search(r"桃園[縣市]", addr or ""):
        return "桃園"
    return None


def region_from_name(name):
    for region, kws in REGION_KEYWORDS.items():
        if any(k in (name or "") for k in kws):
            return region
    return None


def brief_type(rec):
    b = rec.get("brief") or {}
    return b.get("type") or rec.get("type") or ""


def is_tender_type(t):
    return bool(TENDER_TYPE.search(t)) and not SKIP_TYPE.search(t)


def field(detail, *names):
    """欄位名稱像「採購資料:預算金額」，先比對冒號後完全相同，再退而比對結尾。"""
    for exact in (True, False):
        for k, v in detail.items():
            if v in (None, "") or not isinstance(v, (str, int, float)):
                continue
            tail = k.split(":")[-1].strip()
            for n in names:
                if (tail == n) if exact else k.endswith(n):
                    return str(v).strip()
    return ""


def parse_date(s):
    m = re.search(r"(\d{2,4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", s or "")
    if not m:
        return None
    y = int(m[1])
    if y < 1911:
        y += 1911
    try:
        return dt.datetime(y, int(m[2]), int(m[3]), int(m[4] or 0), int(m[5] or 0), tzinfo=TZ)
    except ValueError:
        return None


def parse_money(s):
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s.split("元")[0])
    return int(digits) if digits else None


def abs_url(u):
    if not u:
        return ""
    return u if u.startswith("http") else "https://web.pcc.gov.tw" + u


def slim(r):
    b = r.get("brief") or {}
    return {
        "date": r.get("date", 0),
        "type": b.get("type", ""),
        "category": b.get("category", "") or "",
        "title": b.get("title", ""),
        "unit_id": r.get("unit_id", ""),
        "unit_name": r.get("unit_name", ""),
        "job_number": r.get("job_number", ""),
        "url": r.get("url", ""),
    }


def fetch_detail(j):
    global _debug_printed
    data = api(f"/api/tender?unit_id={quote(j['unit_id'])}&job_number={quote(j['job_number'])}")
    recs = sorted(data.get("records", []), key=lambda r: (r.get("date", 0), r.get("filename", "")))
    if not recs:
        return None
    if CLOSED_TYPE.search(brief_type(recs[-1])):
        return {"closed": True}
    tender_recs = [r for r in recs if is_tender_type(brief_type(r))]
    if not tender_recs:
        return None
    rec = tender_recs[-1]
    d = rec.get("detail") or {}

    category = field(d, "標的分類")
    if category and "工程" not in category:
        return {"not_works": True}

    unit = field(d, "機關名稱") or j["unit_name"]
    region = region_from_address(field(d, "機關地址")) or region_from_name(unit)
    budget = parse_money(field(d, "預算金額"))
    deadline = parse_date(field(d, "截止投標"))
    opening = parse_date(field(d, "開標時間"))
    announce = parse_date(field(d, "公告日"))
    if not announce and rec.get("date"):
        announce = parse_date(f"{str(rec['date'])[:4]}/{str(rec['date'])[4:6]}/{str(rec['date'])[6:8]}")

    if (budget is None or deadline is None) and not _debug_printed:
        print("⚠️ 欄位解析不到，detail 欄位名稱如下（供調整 field() 使用）：")
        print(list(d.keys())[:80])
        _debug_printed = True

    iso = lambda x: x.isoformat() if x else None
    return {
        "region": region,
        "unit": unit,
        "title": field(d, "標案名稱") or j["title"],
        "job": j["job_number"],
        "method": field(d, "招標方式"),
        "budget": budget,
        "announce": iso(announce),
        "deadline": iso(deadline),
        "opening": iso(opening),
        "url": abs_url(rec.get("url") or j.get("url")),
    }


def main():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {"days": {}, "tenders": {}}

    now = dt.datetime.now(TZ)
    today = now.date()
    keep_days = set()
    jobs = {}

    # 1) 掃描每日公告清單，只留新竹桃園機關
    for i in range(LOOKBACK_DAYS):
        ds = (today - dt.timedelta(days=i)).strftime("%Y%m%d")
        keep_days.add(ds)
        if i >= REFETCH_RECENT_DAYS and ds in cache["days"]:
            recs = cache["days"][ds]
        else:
            try:
                raw = api(f"/api/listbydate?date={ds}")
                recs = [slim(r) for r in raw.get("records", []) if unit_match(r.get("unit_name"))]
                cache["days"][ds] = recs
            except Exception as e:
                print("略過", ds, e)
                recs = cache["days"].get(ds, [])
            time.sleep(0.3)
        for r in recs:
            key = f"{r['unit_id']}|{r['job_number']}"
            j = jobs.setdefault(key, {**r, "max_date": 0, "works": False})
            j["max_date"] = max(j["max_date"], r["date"])
            if is_tender_type(r["type"]) and ("工程" in r["category"] or not r["category"]):
                j["works"] = True
                j["title"], j["url"] = r["title"], r["url"] or j["url"]

    cache["days"] = {k: v for k, v in cache["days"].items() if k in keep_days}

    # 2) 只對新的或有更新（更正、決標）的案子抓明細
    fetched = 0
    for key, j in jobs.items():
        if not j["works"]:
            continue
        c = cache["tenders"].get(key)
        if c and c.get("max_date", 0) >= j["max_date"]:
            continue
        try:
            info = fetch_detail(j)
        except Exception as e:
            print("明細失敗", key, e)
            continue
        cache["tenders"][key] = {"max_date": j["max_date"], "info": info}
        fetched += 1
        time.sleep(0.3)

    # 3) 篩選：招標中、預算 < 上限、在新竹桃園
    items = []
    for key, c in list(cache["tenders"].items()):
        info = c.get("info") or {}
        dl = dt.datetime.fromisoformat(info["deadline"]) if info.get("deadline") else None
        if key not in jobs or (dl and dl < now - dt.timedelta(days=3)):
            del cache["tenders"][key]   # 清掉過期或超出掃描範圍的快取
            continue
        if info.get("closed") or info.get("not_works") or not info.get("region"):
            continue
        if info.get("budget") is None or info["budget"] >= BUDGET_MAX:
            continue
        if not dl or dl <= now:
            continue
        items.append(info)
    items.sort(key=lambda x: x["deadline"])

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    render(items, now)
    print(f"完成：本次抓明細 {fetched} 筆，符合條件 {len(items)} 筆")


def render(items, now):
    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        tpl = f.read()
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = (tpl.replace("__DATA__", payload)
               .replace("__UPDATED__", now.strftime("%Y-%m-%d %H:%M"))
               .replace("__BUDGET_WAN__", f"{BUDGET_MAX // 10000:,}"))
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)


if __name__ == "__main__":
    main()
