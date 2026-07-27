#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fill missing coordinates in all_stores.json via Nominatim (small batch).
Only geocodes stores lacking lat/lon. Keyed by address in fill_cache.json.
Uses progressive address simplification + 429 backoff.
"""
import json
import os
import re
import time
import subprocess

STORES = "/Users/nobisuke/ds/2_playground/komeri/all_stores.json"
CACHE = "/Users/nobisuke/ds/2_playground/komeri/fill_cache.json"
UA = "KomeriStoreMap/1.0"


def nominatim(q):
    cmd = ["curl", "-s", "--max-time", "30", "-w", "\n%{http_code}", "-A", UA,
           "-H", "Accept-Language: ja", "-G", "https://nominatim.openstreetmap.org/search",
           "--data-urlencode", f"q={q}", "--data", "format=json",
           "--data", "limit=1", "--data", "countrycodes=jp"]
    for attempt in range(5):
        out = subprocess.run(cmd, capture_output=True).stdout.decode("utf-8", "replace")
        body, _, code = out.rpartition("\n")
        try:
            c = int(code.strip())
        except ValueError:
            c = 0
        if c in (429, 403):
            time.sleep(30 * (attempt + 1)); continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None
        if data:
            d = data[0]
            return float(d["lat"]), float(d["lon"])
        return None
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