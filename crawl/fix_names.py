#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix store names that came back as 'エラー' (pre-open stores whose
storeDetail page errors). The ResultList pages carry the real name in
hidden inputs (name{N}) aligned by index with storeDetail.aspx?id= links.
Also cleans name annotations (※..., （県名）, 　周辺).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httputil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STORES = os.path.join(REPO, "web", "data", "all_stores.json")
CACHE = os.path.join(HERE, "crawl_cache.json")

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


def clean(name):
    if not name:
        return ""
    name = name.replace("　周辺", "").replace(" 周辺", "")
    name = re.sub(r"※.*$", "", name)               # drop ※ annotations
    name = re.sub(r"（[^）]*[都道府県][^）]*）", "", name)  # drop （〇県） parenthetical
    name = re.sub(r"\(\s*[^)]*[都道府県][^)]*\)", "", name)
    name = re.sub(r"\s+", "", name).strip()
    return name


def get(url):
    return httputil.get(url, want="body", ua=httputil.BROWSER_UA)


def rl_names(url):
    """Return {id: raw_name} from a ResultList page."""
    html = get(url)
    if not html:
        return {}
    ids = re.findall(r'storeDetail\.aspx\?id=(\d+)', html)
    names = re.findall(r'<input[^>]*id="name(\d+)"[^>]*value="([^"]*)"', html)
    nmap = {int(k): v for k, v in names}
    return {ids[i]: nmap.get(i, "") for i in range(min(len(ids), len(nmap)))}


def main():
    stores = json.load(open(STORES, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8"))
    # which ids are broken
    broken = [s for s in stores if not s["name"] or "エラー" in s["name"]]
    print(f"broken names: {len(broken)}", flush=True)
    # map id -> list of resultlist urls containing it
    id_urls = {}
    for url, ids in cache["store_ids_by_rl"].items():
        for sid in ids:
            id_urls.setdefault(sid, []).append(url)
    fixed = 0
    for s in broken:
        sid = s["id"]
        new_name = ""
        for url in id_urls.get(sid, []):
            nm = rl_names(url)
            if sid in nm and nm[sid] and "エラー" not in nm[sid]:
                new_name = nm[sid]
                break
        if new_name:
            s["name"] = clean(new_name)
            s["brand"] = brand_of(s["name"])
            fixed += 1
            print(f"  OK {sid}: {s['name']}", flush=True)
        else:
            print(f"  MISS {sid}: could not recover name", flush=True)
    # clean all names (annotations) even if not broken
    for s in stores:
        s["name"] = clean(s["name"])
        s["brand"] = brand_of(s["name"])
    json.dump(stores, open(STORES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    still = sum(1 for s in stores if not s["name"] or "エラー" in s["name"])
    print(f"\nfixed {fixed}/{len(broken)}; still broken: {still}", flush=True)


if __name__ == "__main__":
    main()