#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crawl all Komeri stores (all brands) from www.komeri.com store search.
Concurrent + cached + resumable.

Pipeline:
  1. Per prefecture: CriteriaResult.aspx?search={pref}&cmdSearch=0 (paginated)
     -> collect ResultList.aspx?lat&lon&area_name links.
  2. Each ResultList -> storeDetail.aspx?id= ids.
  3. Each storeDetail -> name, address, tel, goo.gl maps link.
  4. Expand goo.gl link (302 Location) -> !3d{lat}!4d{lon} -> exact coords.
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://www.komeri.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEB_DATA = os.path.join(REPO, "web", "data")
OUT = os.path.join(WEB_DATA, "all_stores.json")
CACHE = os.path.join(HERE, "crawl_cache.json")
WORKERS = 6

PREFS = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

_lock = threading.Lock()


def get(url, want="body"):
    if want == "redirect":
        cmd = ["curl", "-s", "--max-time", "25", "-A", UA,
               "-o", "/dev/null", "-w", "%{redirect_url}", url]
    else:
        cmd = ["curl", "-s", "-L", "--max-time", "25", "--max-redirs", "5",
               "-A", UA, "-w", "\n%{http_code}", url]
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True)
        out = r.stdout.decode("utf-8", "replace")
        if want == "redirect":
            return out.strip()
        body, _, code = out.rpartition("\n")
        try:
            c = int(code.strip())
        except ValueError:
            c = 0
        if c == 200 and body:
            return body
        if c in (429, 503):
            time.sleep(3 * (attempt + 1))
            continue
        if c == 0:
            time.sleep(1.5)
            continue
        return None
    return None


def load_cache():
    base = {"resultlist_links": {}, "store_ids_by_rl": {}, "store_detail": {}, "coords": {}}
    if os.path.exists(CACHE):
        try:
            data = json.load(open(CACHE, encoding="utf-8"))
            for k, v in base.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return base


def save_cache(c):
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def collect_resultlist_links(pref, cache):
    if pref in cache["resultlist_links"]:
        return cache["resultlist_links"][pref]
    links = []
    seen = set()
    p = 1
    while True:
        url = (f"{BASE}/shop/storeSearch/CriteriaResult.aspx?"
               f"search={urllib.parse.quote(pref)}&cmdSearch=0&p={p}&ps=50")
        html = get(url)
        if not html:
            break
        found = re.findall(r'href="(/shop/storeSearch/ResultList\.aspx\?[^"]+)"', html)
        new = 0
        for h in found:
            h = h.replace("&amp;", "&")
            u = BASE + h
            m = re.search(r"lat=([0-9.]+)&lon=([0-9.]+)", u)
            k = m.group(1) + "," + m.group(2) if m else u
            if k not in seen:
                seen.add(k)
                links.append(u)
                new += 1
        pages = [int(x) for x in re.findall(r"criteriaresult\.aspx\?p=(\d+)&", html)]
        maxp = max(pages) if pages else p
        if p >= maxp or new == 0:
            break
        p += 1
    with _lock:
        cache["resultlist_links"][pref] = links
        save_cache(cache)
    print(f"  {pref}: {len(links)} area groups", flush=True)
    return links


def collect_store_ids(rl_url, cache):
    with _lock:
        if rl_url in cache["store_ids_by_rl"]:
            return cache["store_ids_by_rl"][rl_url]
    html = get(rl_url)
    ids = []
    if html:
        for m in re.finditer(r'storeDetail\.aspx\?id=(\d+)', html):
            sid = m.group(1)
            if sid not in ids:
                ids.append(sid)
    with _lock:
        cache["store_ids_by_rl"][rl_url] = ids
    return ids


def parse_store_detail(html):
    if not html:
        return None
    title = re.search(r"<title>([^<]*)</title>", html)
    name = ""
    if title:
        t = title.group(1).strip()
        name = t.split(" 店舗詳細")[0].split(" -")[0].strip()
    addr = ""
    m = re.search(r"住所</th>\s*<td[^>]*>(.*?)</td>", html, re.S)
    if m:
        addr = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", m.group(1)))
    tel = ""
    m = re.search(r"電話番号</th>\s*<td[^>]*>(.*?)</td>", html, re.S)
    if m:
        tel = re.sub(r"[^\d-]", "", re.sub(r"<[^>]+>", "", m.group(1)))
    goo = ""
    m = re.search(r"https://goo\.gl/maps/[A-Za-z0-9_]+", html)
    if m:
        goo = m.group(0)
    return {"name": name, "address": addr, "tel": tel, "goo": goo}


def fetch_store_detail(sid, cache):
    with _lock:
        if sid in cache["store_detail"]:
            return cache["store_detail"][sid]
    html = get(f"{BASE}/shop/storeSearch/storeDetail.aspx?id={sid}")
    d = parse_store_detail(html)
    with _lock:
        cache["store_detail"][sid] = d
    return d


def expand_goo(goo, cache):
    if not goo:
        return None, None
    with _lock:
        if goo in cache["coords"]:
            c = cache["coords"][goo]
            return c.get("lat"), c.get("lon")
    loc = get(goo, want="redirect")
    lat = lon = None
    if loc:
        m = re.search(r"!3d(-?[0-9.]+)!4d(-?[0-9.]+)", loc)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
        else:
            m = re.search(r"@(-?[0-9.]+),(-?[0-9.]+)", loc)
            if m:
                lat, lon = float(m.group(1)), float(m.group(2))
    with _lock:
        cache["coords"][goo] = {"lat": lat, "lon": lon}
    return lat, lon


BRANDS = ["コメリパワー", "コメリハード＆グリーン", "コメリハード&グリーン",
          "コメリリフォーム", "コメリＰＲＯ", "コメリPRO", "コメリ"]


def brand_of(name):
    for b in BRANDS:
        if b in name:
            if b in ("コメリＰＲＯ", "コメリPRO"):
                return "コメリPRO"
            if b in ("コメリハード＆グリーン", "コメリハード&グリーン"):
                return "コメリハード＆グリーン"
            return b
    return "コメリ"


def pref_of(address, fallback=""):
    """Derive prefecture from the address prefix (accurate)."""
    for p in PREFS:
        if address.startswith(p):
            return p
    return fallback


def main():
    cache = load_cache()
    if os.environ.get("FRESH_DISCOVERY"):
        # re-discover area groups / store ids (catches new stores) but reuse
        # cached store_detail and coords for known ids (much faster, gentler).
        # NOTE: reset to {} (not pop) so the keys still exist for direct lookups.
        n0 = sum(len(v) for v in cache.get("resultlist_links", {}).values())
        cache["resultlist_links"] = {}
        cache["store_ids_by_rl"] = {}
        save_cache(cache)
        print(f"FRESH_DISCOVERY: cleared discovery caches ({n0} area links)", flush=True)
    # Stage 1: ResultList links per pref (parallel across prefs)
    print("== Stage 1: discovering area groups ==", flush=True)
    rl_by_pref = {}
    with ThreadPoolExecutor(max_workers=min(WORKERS, 8)) as ex:
        futs = {ex.submit(collect_resultlist_links, p, cache): p for p in PREFS}
        for f in as_completed(futs):
            f.result()
    with _lock:
        rl_by_pref = {p: cache["resultlist_links"].get(p, []) for p in PREFS}
    total_rl = sum(len(v) for v in rl_by_pref.values())
    print(f"   {total_rl} area groups across {len(PREFS)} prefs", flush=True)

    # Stage 2: store ids from each ResultList (parallel)
    print("== Stage 2: collecting store ids ==", flush=True)
    all_rl = []
    for p, rls in rl_by_pref.items():
        for rl in rls:
            all_rl.append((p, rl))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(collect_store_ids, rl, cache): (p, rl) for p, rl in all_rl}
        done = 0
        for f in as_completed(futs):
            f.result()
            done += 1
            if done % 200 == 0:
                with _lock:
                    save_cache(cache)
                print(f"   resultlist {done}/{len(all_rl)}", flush=True)
    with _lock:
        save_cache(cache)
    # unique ids, tagged with the prefecture of first appearance
    id_pref = {}
    for p in PREFS:
        for rl in rl_by_pref[p]:
            for sid in cache["store_ids_by_rl"].get(rl, []):
                if sid not in id_pref:
                    id_pref[sid] = p
    print(f"   {len(id_pref)} unique stores", flush=True)

    # Stage 3: store details (parallel)
    print("== Stage 3: fetching store details ==", flush=True)
    sids = list(id_pref.keys())
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_store_detail, s, cache): s for s in sids}
        done = 0
        for f in as_completed(futs):
            f.result()
            done += 1
            if done % 200 == 0:
                with _lock:
                    save_cache(cache)
                print(f"   detail {done}/{len(sids)}", flush=True)
    with _lock:
        save_cache(cache)

    # Stage 4: expand goo.gl coords (parallel)
    print("== Stage 4: resolving coordinates ==", flush=True)
    goos = []
    for s in sids:
        d = cache["store_detail"].get(s) or {}
        g = d.get("goo", "")
        if g and g not in cache["coords"]:
            goos.append(g)
    print(f"   {len(goos)} goo.gl links to expand", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(expand_goo, g, cache): g for g in goos}
        done = 0
        for f in as_completed(futs):
            f.result()
            done += 1
            if done % 300 == 0:
                with _lock:
                    save_cache(cache)
                print(f"   coords {done}/{len(goos)}", flush=True)
    with _lock:
        save_cache(cache)

    # Build output
    stores = []
    for s in sids:
        d = cache["store_detail"].get(s) or {}
        goo = d.get("goo", "")
        c = cache["coords"].get(goo, {})
        name = d.get("name", "")
        address = d.get("address", "")
        stores.append({
            "id": s, "name": name, "brand": brand_of(name),
            "address": address,
            "prefecture": pref_of(address, id_pref.get(s, "")),
            "tel": d.get("tel", ""), "lat": c.get("lat"), "lon": c.get("lon"),
            "goo": goo,
            "url": f"{BASE}/shop/storeSearch/storeDetail.aspx?id={s}",
        })
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=1)
    withc = sum(1 for s in stores if s["lat"] is not None)
    print(f"\nDONE: {len(stores)} stores, {withc} with coords -> {OUT}", flush=True)
    from collections import Counter
    for k, v in Counter(s["brand"] for s in stores).most_common():
        print(f"  {k}: {v}", flush=True)


if __name__ == "__main__":
    main()