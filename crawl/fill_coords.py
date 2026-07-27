#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fill missing coordinates in all_stores.json via Nominatim (small batch).
Only geocodes stores lacking lat/lon. Keyed by address in fill_cache.json.
Uses progressive address simplification + 429 backoff.
"""
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httputil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STORES = os.path.join(REPO, "web", "data", "all_stores.json")
CACHE = os.path.join(HERE, "fill_cache.json")


def nominatim(q):
    url = ("https://nominatim.openstreetmap.org/search?" +
           urllib.parse.urlencode({"q": q, "format": "json", "limit": 1, "countrycodes": "jp"}))
    body = httputil.get(url, want="body", ua=httputil.NOMINATIM_UA,
                        retries=5, backoff=30.0)
    if not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if data:
        d = data[0]
        return float(d["lat"]), float(d["lon"])
    return None


def simplify(addr):
    yield addr
    q = re.sub(r"\d+番地?\d*号?$", "", addr).strip()
    if q and q != addr: yield q
    q2 = re.sub(r"\d+号$", "", q or addr).strip()
    if q2 and q2 != (q or addr): yield q2
    base = re.split(r"\d+丁目", q or addr)[0].strip()
    if base and base != (q or addr): yield base
    m = re.match(r"^(.+?[市郡])", addr)
    if m: yield m.group(1)


def geocode(addr):
    seen = set()
    for q in simplify(addr):
        if not q or q in seen: continue
        seen.add(q)
        time.sleep(2.2)
        r = nominatim(q)
        if r:
            return r[0], r[1], q
    return None, None, addr


def main():
    stores = json.load(open(STORES, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    todo = [s for s in stores if s.get("lat") is None]
    print(f"total {len(stores)}, missing coords {len(todo)}", flush=True)
    for i, s in enumerate(todo, 1):
        addr = s["address"]
        if addr in cache:
            c = cache[addr]
        else:
            lat, lon, used = geocode(addr)
            cache[addr] = {"lat": lat, "lon": lon, "q": used}
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        c = cache[addr]
        if c["lat"] is not None:
            s["lat"], s["lon"] = c["lat"], c["lon"]
        st = "OK " if c["lat"] else "MISS"
        print(f"[{i}/{len(todo)}] {st} {s['id']} {addr[:30]} -> "
              f"{('%.4f,%.4f' % (c['lat'], c['lon'])) if c['lat'] else 'none'}", flush=True)
    json.dump(stores, open(STORES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    withc = sum(1 for s in stores if s.get("lat") is not None)
    print(f"DONE: {withc}/{len(stores)} with coords", flush=True)


if __name__ == "__main__":
    main()