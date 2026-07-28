#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
世界遺産マップ用データビルダ。
- 世界遺産(27) / 暫定リスト記載候補(27) は座標付きシード（公式暫定リストは2026年7月時点で空 = 飛鳥・藤原の宮都が世界遺産登録されたため）
- 国宝建造物(facility単位) は national_treasures.json から読み込み Nominatim で座標補完
- tier / category / point / overlap を付与し web/data/heritage.json を生成
"""
import json, os, time, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DATA = os.path.join(HERE, "..", "web", "data")
os.makedirs(WEB_DATA, exist_ok=True)
GEOCACHE = os.path.join(HERE, "geocode_cache.json")

UA = "SekaiIsanMap/1.0 (heritage map builder; contact: n0bisuke)"

# ---- point table (higher tier dominates on overlap) ----
TIER = {
    "world":              {"point": 3, "color": "#ffc400", "label": "世界遺産",        "order": 0},
    "tentative_official": {"point": 2, "color": "#7d8da1", "label": "公式暫定リスト",  "order": 1},
    "tentative":          {"point": 2, "color": "#b9c0c9", "label": "暫定リスト候補",  "order": 2},
    "national_treasure":  {"point": 1, "color": "#8a4b2e", "label": "国宝建造物",      "order": 3},
}

# ============================================================
# 世界遺産 (登録済) — 文化/自然/混合
# multi-prefecture の代表座標1点 + prefectures リスト
# ============================================================
WORLD_HERITAGE = [
    # name, [prefectures], category, year, lat, lon, note
    ("法隆寺地域の仏教建造物", ["奈良県"], "文化遺産", 1993, 34.6143, 135.7356, "法隆寺"),
    ("姫路城", ["兵庫県"], "文化遺産", 1993, 34.8394, 134.6939, ""),
    ("屋久島", ["鹿児島県"], "自然遺産", 1993, 30.3533, 130.5061, ""),
    ("白神山地", ["青森県", "秋田県"], "自然遺産", 1993, 40.4500, 140.0500, ""),
    ("古都京都の文化財", ["京都府", "滋賀県"], "文化遺産", 1994, 35.0116, 135.7681, "京都市・宇治市・大津市"),
    ("白川郷・五箇山の合掌造り集落", ["岐阜県", "富山県"], "文化遺産", 1995, 36.2539, 136.9020, "白川村"),
    ("原爆ドーム", ["広島県"], "文化遺産", 1996, 34.3955, 132.4536, ""),
    ("厳島神社", ["広島県"], "文化遺産", 1996, 34.2959, 132.3196, ""),
    ("古都奈良の文化財", ["奈良県"], "文化遺産", 1998, 34.6890, 135.8398, "東大寺"),
    ("日光の社寺", ["栃木県"], "文化遺産", 1999, 36.7575, 139.5990, "日光東照宮"),
    ("琉球王国のグスク及び関連遺産群", ["沖縄県"], "文化遺産", 2000, 26.2170, 127.7194, "首里城"),
    ("紀伊山地の霊場と参詣道", ["三重県", "奈良県", "和歌山県"], "文化遺産", 2004, 33.8729, 135.7823, "熊野本宮大社"),
    ("知床", ["北海道"], "自然遺産", 2005, 44.1500, 145.0500, ""),
    ("石見銀山遺跡とその文化的景観", ["島根県"], "文化遺産", 2007, 35.2667, 132.4333, "大森銀山"),
    ("小笠原諸島", ["東京都"], "自然遺産", 2011, 27.0600, 142.2100, "父島"),
    ("平泉―仏国土（浄土）を表す建築・庭園及び考古学的遺跡群―", ["岩手県"], "文化遺産", 2011, 38.9867, 141.1080, "中尊寺"),
    ("富士山―信仰の対象と芸術の源泉―", ["山梨県", "静岡県"], "文化遺産", 2013, 35.3606, 138.7274, ""),
    ("富岡製糸場と絹産業遺産群", ["群馬県"], "文化遺産", 2014, 36.2569, 138.8876, "富岡製糸場"),
    ("明治日本の産業革命遺産 製鉄・製鋼、造船、石炭産業",
     ["福岡県", "佐賀県", "長崎県", "熊本県", "鹿児島県", "山口県", "岩手県", "静岡県"],
     "文化遺産", 2015, 32.6280, 129.7256, "端島（軍艦島）代表"),
    ("ル・コルビュジエの建築作品―近代建築運動への顕著な貢献―", ["東京都"], "文化遺産", 2016, 35.7198, 139.7764, "国立西洋美術館"),
    ("「神宿る島」宗像・沖ノ島と関連遺産群", ["福岡県"], "文化遺産", 2017, 33.7989, 130.0826, "沖ノ島"),
    ("長崎と天草地方の潜伏キリシタン関連遺産", ["長崎県", "熊本県"], "文化遺産", 2018, 32.7432, 129.8730, "大浦天主堂"),
    ("百舌鳥・古市古墳群―古代日本の墳墓群―", ["大阪府"], "文化遺産", 2019, 34.5645, 135.4878, "仁徳天皇陵"),
    ("奄美大島、徳之島、沖縄島北部及び西表島", ["鹿児島県", "沖縄県"], "自然遺産", 2021, 28.3700, 129.4800, "奄美大島代表"),
    ("北海道・北東北の縄文遺跡群", ["北海道", "青森県", "岩手県", "秋田県"], "文化遺産", 2021, 40.7967, 140.7400, "三内丸山遺跡代表"),
    ("佐渡島の金山", ["新潟県"], "文化遺産", 2024, 37.7833, 138.2667, "相川金山"),
    ("飛鳥・藤原の宮都とその関連資産群", ["奈良県"], "文化遺産", 2026, 34.4772, 135.8180, "明日香村・橿原市・桜井市"),
]

# ============================================================
# 公式暫定リスト (UNESCO Tentative List) — 現在の推薦候補
# ============================================================
TENTATIVE_OFFICIAL = [
    # name, [prefectures], category, lat, lon, note
]

# ============================================================
# 暫定リスト記載候補 (文化庁 審議 besshi_8) 27件
# ============================================================
TENTATIVE_CANDIDATES = [
    # name, [prefectures], category, lat, lon, note
    ("北海道東部の窪みで残る大規模竪穴住居跡群", ["北海道"], "文化遺産", 43.6700, 144.9300, "標津町代表"),
    ("最上川の文化的景観", ["山形県"], "文化遺産", 38.6500, 140.0500, ""),
    ("松島－貝塚群に見る縄文の原風景", ["宮城県"], "文化遺産", 38.3700, 141.0000, ""),
    ("水戸藩の学問・教育遺産群", ["茨城県"], "文化遺産", 36.3656, 140.4744, "弘道館"),
    ("足尾銅山", ["栃木県"], "文化遺産", 36.6200, 139.4200, "日光市足尾"),
    ("足利学校と足利氏の遺産", ["栃木県"], "文化遺産", 36.4470, 139.4490, ""),
    ("埼玉古墳群", ["埼玉県"], "文化遺産", 36.1267, 139.4536, "行田市"),
    ("近世高岡の文化遺産群", ["富山県"], "文化遺産", 36.7486, 137.0225, "高岡市"),
    ("立山・黒部", ["富山県"], "文化遺産", 36.4200, 137.5500, "立山"),
    ("城下町金沢の文化遺産群と文化的景観", ["石川県"], "文化遺産", 36.5944, 136.6256, "金沢市"),
    ("霊峰白山と山麓の文化的景観", ["石川県", "福井県", "岐阜県"], "文化遺産", 36.1500, 136.4000, "白山"),
    ("若狭の社寺建造物群と文化的景観", ["福井県"], "文化遺産", 35.4639, 135.7342, "小浜市"),
    ("日本製糸業近代化遺産", ["長野県"], "文化遺産", 36.0339, 138.0536, "岡谷市"),
    ("善光寺と門前町", ["長野県"], "文化遺産", 36.7006, 138.1908, "長野市"),
    ("松本城", ["長野県"], "文化遺産", 36.2397, 137.9694, ""),
    ("妻籠宿・馬籠宿と中山道", ["長野県", "岐阜県"], "文化遺産", 35.4900, 137.5800, "妻籠宿代表"),
    ("飛騨高山の町並みと祭礼の場", ["岐阜県"], "文化遺産", 36.1407, 137.2522, "高山市"),
    ("天橋立", ["京都府"], "文化遺産", 35.5472, 135.1856, "宮津市"),
    ("近世岡山の文化・土木遺産群", ["岡山県"], "文化遺産", 34.6552, 133.9195, "岡山市"),
    ("三徳山", ["鳥取県"], "文化遺産", 35.4033, 133.8842, "三朝町・三佛寺投入堂"),
    ("萩", ["山口県"], "文化遺産", 34.4081, 131.3944, "萩市"),
    ("錦帯橋と岩国の町割", ["山口県"], "文化遺産", 34.1672, 132.1661, "岩国市"),
    ("山口に花開いた大内文化の遺産", ["山口県"], "文化遺産", 34.1857, 131.4736, "山口市"),
    ("四国八十八箇所霊場と遍路道", ["徳島県", "高知県", "愛媛県", "香川県"], "文化遺産", 34.0716, 134.5594, "第1番霊山寺代表"),
    ("宇佐・国東", ["大分県"], "文化遺産", 33.4972, 131.3722, "宇佐神宮"),
    ("阿蘇", ["熊本県"], "文化遺産", 32.9400, 130.9900, "阿蘇山"),
    ("竹富島・波照間島の文化的景観", ["沖縄県"], "文化遺産", 24.3300, 124.1600, "竹富島"),
]


def load_cache():
    if os.path.exists(GEOCACHE):
        with open(GEOCACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(c):
    with open(GEOCACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)


def geocode(query):
    """Nominatim で緯度経度を取得（1 req/sec の礼儀）。キャッシュ付き。"""
    c = load_cache()
    if query in c:
        v = c[query]
        return v[0], v[1]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "accept-language": "ja", "countrycodes": "jp",
    })
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            c[query] = [lat, lon]
            save_cache(c)
            time.sleep(1.0)
            return lat, lon
    except Exception as e:
        print(f"  geocode fail: {query} -> {e}", file=sys.stderr)
    c[query] = [None, None]
    save_cache(c)
    time.sleep(1.0)
    return None, None


import re
def clean_facility(name):
    """Nominatim が探しやすいよう括弧内の注記を削除し、先頭の「旧」も外す。"""
    n = re.sub(r"（[^）]*）", "", name)
    n = re.sub(r"\([^)]*\)", "", n)
    n = n.strip()
    if n.startswith("旧"):
        n = n[1:]
    return n.strip()


def entry(name, prefs, category, tier, lat, lon, note, sub=None, year=None, buildings=None, wh_site=None):
    return {
        "id": None,  # set later
        "name": name,
        "prefectures": prefs,
        "category": category,        # 文化遺産 / 自然遺産 / 混合遺産
        "tier": tier,
        "point": TIER[tier]["point"],
        "lat": lat, "lon": lon,
        "note": note or "",
        "sub": sub or "",            # 補足（代表点など）
        "year": year,
        "buildings": buildings or [],
        "wh_site": wh_site or "",     # 国宝が世界遺産構成要素の場合その名
        "overlap": False,            # 上位tierに吸収される場合 True (point=0)
    }


def main():
    items = []
    # 世界遺産
    for name, prefs, cat, year, lat, lon, note in WORLD_HERITAGE:
        items.append(entry(name, prefs, cat, "world", lat, lon, note, year=year))
    # 公式暫定
    for name, prefs, cat, lat, lon, note in TENTATIVE_OFFICIAL:
        items.append(entry(name, prefs, cat, "tentative_official", lat, lon, note))
    # 暫定候補
    for name, prefs, cat, lat, lon, note in TENTATIVE_CANDIDATES:
        items.append(entry(name, prefs, cat, "tentative", lat, lon, note))

    # 暫定リスト（候補+公式）の施設名集合 — 国宝と同名なら上位(暫定2pt)に吸収
    tentative_names = set()
    for e in items:
        if e["tier"] in ("tentative", "tentative_official"):
            tentative_names.add(e["name"])

    # 国宝建造物 (facility単位) を読み込み
    nt_path = os.path.join(HERE, "national_treasures.json")
    if os.path.exists(nt_path):
        with open(nt_path, "r", encoding="utf-8") as f:
            nt = json.load(f)
        print(f"国宝建造物: {len(nt)} 施設")
        for fac in nt:
            facility = fac["facility"]
            pref = fac["prefecture"]
            muni = fac.get("municipality", "")
            buildings = fac.get("buildings", [])
            in_wh = fac.get("in_world_heritage", False)
            wh_site = fac.get("world_heritage_site", "")
            # 座標: 施設名(+市町村) でジオコード。括弧注記を外したクリーン名も試す。
            cf = clean_facility(facility)
            queries = []
            if muni:
                queries.append(f"{facility} {muni}")
                queries.append(f"{cf} {muni}")
            queries.append(f"{facility} {pref}")
            queries.append(f"{cf} {pref}")
            if cf != facility:
                queries.append(f"{cf}")
            lat, lon = None, None
            for q in queries:
                lat, lon = geocode(q)
                if lat is not None:
                    break
            # overlap: 世界遺産構成要素 OR 暫定リスト候補と同名（松本城など）
            overlap = bool(in_wh) or (facility in tentative_names)
            e = entry(facility, [pref], "文化遺産", "national_treasure", lat, lon, "",
                      sub="、".join(buildings[:6]) + ("…" if len(buildings) > 6 else ""),
                      buildings=buildings, wh_site=wh_site)
            e["overlap"] = overlap
            items.append(e)
    else:
        print("national_treasures.json が見つかりません（国宝なしでビルド）", file=sys.stderr)

    # overlap の point を 0 に（上位tierが同じ場所で既に加点済みのため）
    for e in items:
        if e["overlap"]:
            e["point"] = 0

    # id 採番
    for i, e in enumerate(items):
        e["id"] = f"h{i:03d}"

    out = {
        "generated": "hand-curated + Nominatim geocoded",
        "tiers": {k: {"point": v["point"], "color": v["color"], "label": v["label"]}
                  for k, v in TIER.items()},
        "items": items,
    }
    dest = os.path.join(WEB_DATA, "heritage.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with_coord = sum(1 for e in items if e["lat"] is not None)
    print(f"生成: {len(items)} 件 / 座標あり {with_coord} 件 -> {dest}")


if __name__ == "__main__":
    main()