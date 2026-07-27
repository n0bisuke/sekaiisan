#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse Komeri store list HTML into JSON. Prefecture derived from address."""
import json
import re
from html.parser import HTMLParser

SRC = "/tmp/komeri.html"
OUT = "/Users/nobisuke/ds/2_playground/komeri/stores.json"

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

REGIONS = {
    "北海道": "北海道地方", "青森県": "東北地方", "岩手県": "東北地方",
    "宮城県": "東北地方", "秋田県": "東北地方", "山形県": "東北地方",
    "福島県": "東北地方", "茨城県": "関東地方", "栃木県": "関東地方",
    "群馬県": "関東地方", "埼玉県": "関東地方", "千葉県": "関東地方",
    "東京都": "関東地方", "神奈川県": "関東地方",
    "新潟県": "東海・甲信越地方", "山梨県": "東海・甲信越地方",
    "長野県": "東海・甲信越地方", "岐阜県": "東海・甲信越地方",
    "静岡県": "東海・甲信越地方", "愛知県": "東海・甲信越地方",
    "富山県": "北陸地方", "石川県": "北陸地方", "福井県": "北陸地方",
    "三重県": "近畿地方", "滋賀県": "近畿地方", "京都府": "近畿地方",
    "大阪府": "近畿地方", "兵庫県": "近畿地方", "奈良県": "近畿地方",
    "和歌山県": "近畿地方",
    "鳥取県": "中国地方", "島根県": "中国地方", "岡山県": "中国地方",
    "広島県": "中国地方", "山口県": "中国地方",
    "徳島県": "四国地方", "香川県": "四国地方", "愛媛県": "四国地方",
    "高知県": "四国地方",
    "福岡県": "九州地方", "佐賀県": "九州地方", "長崎県": "九州地方",
    "熊本県": "九州地方", "大分県": "九州地方", "宮崎県": "九州地方",
    "鹿児島県": "九州地方", "沖縄県": "九州地方",
}


def prefecture_of(address):
    for p in PREFS:
        if address.startswith(p):
            return p
    return ""


class StoreParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stores = []
        self.in_shop_title = False
        self.in_info = False
        self.cur = None
        self.title_parts = []
        self.info_text = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "section" and "shopListBox" in cls:
            self.cur = {"name": "", "address": "", "tel": "", "id": "", "url": ""}
            self.title_parts = []
        elif tag == "h4" and "shopListBoxTitle" in cls:
            self.in_shop_title = True
            self.title_parts = []
        elif tag == "a" and self.in_shop_title:
            href = d.get("href", "")
            m = re.search(r"[Ii][Dd]=(\d+)", href)
            if m and self.cur:
                self.cur["id"] = m.group(1)
                self.cur["url"] = href
        elif tag == "p" and "shopListInfo02Text01" in cls:
            self.in_info = True
            self.info_text = []
        elif tag == "br" and self.in_shop_title:
            self.title_parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "h4" and self.in_shop_title:
            self.in_shop_title = False
            if self.cur:
                name = re.sub(r"\s+", " ", "".join(self.title_parts)).strip()
                self.cur["name"] = name
        elif tag == "p" and self.in_info:
            self.in_info = False
            text = "".join(self.info_text).strip()
            if self.cur:
                if text.startswith("住所"):
                    self.cur["address"] = re.sub(r"^住所[：:]", "", text).strip()
                elif text.startswith("電話番号"):
                    self.cur["tel"] = re.sub(r"\D", "", re.sub(r"^電話番号[：:]", "", text))
        elif tag == "section" and self.cur is not None:
            if self.cur.get("address") and self.cur.get("name"):
                self.stores.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.in_shop_title:
            self.title_parts.append(data)
        elif self.in_info:
            self.info_text.append(data)


def main():
    with open(SRC, encoding="utf-8") as f:
        html = f.read()
    p = StoreParser()
    p.feed(html)
    seen = set()
    cleaned = []
    for s in p.stores:
        s["prefecture"] = prefecture_of(s["address"])
        s["region"] = REGIONS.get(s["prefecture"], "")
        # name: strip the chain "コメリパワー..." keep as is
        key = (s["id"], s["name"], s["address"])
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    print(f"parsed {len(cleaned)} stores -> {OUT}")
    from collections import Counter
    c = Counter(s["prefecture"] for s in cleaned)
    for k in sorted(c, key=lambda x: PREFS.index(x) if x in PREFS else 99):
        print(f"  {k}: {c[k]}")
    no_pref = [s for s in cleaned if not s["prefecture"]]
    if no_pref:
        print(f"!! {len(no_pref)} stores with unknown prefecture:")
        for s in no_pref:
            print("   ", s["address"])


if __name__ == "__main__":
    main()