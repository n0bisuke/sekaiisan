#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared HTTP helper for the crawl scripts.

Uses httpx with per-thread connection pools (keep-alive) instead of spawning
curl per request — eliminates process-spawn + TLS re-handshake overhead.
"""
import threading
import time

import httpx

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
NOMINATIM_UA = "KomeriStoreMap/1.0"

_local = threading.local()


def _client(ua, accept_lang):
    clients = getattr(_local, "clients", None)
    if clients is None:
        clients = {}
        _local.clients = clients
    key = (ua, accept_lang)
    c = clients.get(key)
    if c is None:
        headers = {"User-Agent": ua}
        if accept_lang:
            headers["Accept-Language"] = accept_lang
        c = httpx.Client(headers=headers, timeout=30.0, follow_redirects=False)
        clients[key] = c
    return c


def get(url, want="body", ua=BROWSER_UA, accept_lang="ja",
        retries=3, backoff=3.0):
    """Fetch url.

    want='body'     -> GET with redirects followed; returns text on 200 else None.
    want='redirect' -> GET without following; returns the Location header value.
    Retries on 429/503 with linear backoff; on transport errors after a short sleep.
    """
    cli = _client(ua, accept_lang)
    for attempt in range(retries):
        try:
            r = cli.get(url, follow_redirects=(want != "redirect"))
        except httpx.HTTPError:
            time.sleep(1.5)
            continue
        if r.status_code in (429, 503):
            time.sleep(backoff * (attempt + 1))
            continue
        if want == "redirect":
            return r.headers.get("location", "") or ""
        if r.status_code == 200:
            return r.text
        return None
    return None