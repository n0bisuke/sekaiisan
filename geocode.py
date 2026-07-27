#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geocode Komeri store addresses with Nominatim (OSM).
Policy: simple UA, <=1 req/sec, countrycodes=jp. Progressive address
simplification because full addresses (with 番/号) often return no hit.
Caches per-id to geocode_cache.json.
"""
import json
import re
import subprocess
import time

STORES = "/Users/nobisuke/ds/2_playground/komeri/stores.json"
CACHE = "/Users/nobisuke/ds/2_playground/komeri/geocode_cache.json"
UA = "KomeriStoreMap/1.0"


def nominatim(q):
    cmd = [
        "curl", "-s", "--max-time", "30", "-w", "\n%{http_code}",
        "-A", UA, "-H", "Accept-Language: ja",
        "-G", "https://nominatim.openstreetmap.org/search",
        "--data-urlencode", f"q={q}",
        "--data", "format=json", "--data", "limit=1",
        "--data", "countrycodes=jp",
    ]
    for attempt in range(5):
        res = subprocess.run(cmd, capture_output=True)
        out = res.stdout.decode("utf-8", "replace")
        body, _, code = out.rpartition("\n")
        try:
            code_i = int(code.strip())
        except ValueError:
            code_i = 0
        if code_i in (429, 403):
            wait = 30 * (attempt + 1)
            print(f"    [rate-limited {code_i}, waiting {wait}s]", flush=True)
            time.sleep(wait)
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None
        if data:
            d = data[0]
            return float(d["lat"]), float(d["lon"]), d.get("display_name", "")
        return None  # 200 but empty -> genuinely no match
    return None


def simplify(address):
    """Yield progressively shorter query strings."""
    yield address
    q = address
    # drop building suffix like "3番60号", "12番地6", "3番1"
    q1 = re.sub(r"\d+番地?\d*号?$", "", q).strip()
    if q1 and q1 != q:
        yield q1
    # drop trailing 号 only ("3丁目60号")
    q2 = re.sub(r"\d+号$", "", q1 or q).strip()
    if q2 and q2 != (q1 or q):
        yield q2
    # drop from the chome/block onward, keep city core: cut at first "丁目"
    base = re.split(r"\d+丁目", q1 or q)[0].strip()
    if base and base != (q1 or q):
        yield base
    # last resort: just the prefecture + city (split on 市/郡)
    m = re.match(r"^(.+?[市郡])", address)
    if m:
        yield m.group(1)


def geocode(address):
    seen = set()
    for q in simplify(address):
        if not q or q in seen:
            continue
        seen.add(q)
        time.sleep(2.0)
        r = nominatim(q)
        if r:
            return r[0], r[1], r[2], q
    return None, None, None, address


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def main():
    with open(STORES, encoding="utf-8") as f:
        stores = json.load(f)
    cache = load_cache()
    # drop any previously-failed (lat None) entries so they retry
    cache = {k: v for k, v in cache.items() if v.get("lat") is not None}
    todo = [s for s in stores if s["id"] not in cache]
    print(f"total {len(stores)}, cached {len(stores)-len(todo)}, to geocode {len(todo)}", flush=True)
    for i, s in enumerate(todo, 1):
        lat, lon, disp, used = geocode(s["address"])
        cache[s["id"]] = {"lat": lat, "lon": lon, "query": used, "display": disp or ""}
        status = "OK  " if lat is not None else "MISS"
        print(f"[{i}/{len(todo)}] {status} {s['id']} {s['address']} -> "
              f"{('%.4f,%.4f' % (lat, lon)) if lat else 'none'} (q={used})", flush=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    # merge into stores
    missing = 0
    for s in stores:
        c = cache.get(s["id"], {})
        s["lat"] = c.get("lat")
        s["lon"] = c.get("lon")
        if s["lat"] is None:
            missing += 1
    with open(STORES, "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    print(f"done. geocoded {len(stores)-missing}/{len(stores)}, missing {missing}", flush=True)


if __name__ == "__main__":
    main()