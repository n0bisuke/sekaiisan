#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文化庁の情報源ページ（世界遺産一覧・暫定リスト候補・国宝建造物）を定期チェックし、
前回スナップショットとの差分があれば GitHub Issue を作成/更新する。

データそのものを自動書き換えはしない（世界遺産か暫定候補かの判断や国宝建造物の
facility単位への整理は人手のレビューが必要なため）。あくまで「変更があったので
確認してください」という通知に留める。

ローカル動作確認: python3 crawl/check_source_updates.py --dry-run
"""
import argparse, difflib, hashlib, html, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(HERE, "source_snapshots")
HASH_PATH = os.path.join(HERE, "source_hashes.json")
UA = "SekaiIsanMap/1.0 (source update checker; contact: n0bisuke)"

SOURCES = [
    {
        "slug": "world_heritage_list",
        "label": "世界遺産一覧",
        "url": "https://www.bunka.go.jp/seisaku/bunkazai/shokai/sekai_isan/ichiran/",
    },
    {
        "slug": "tentative_list_candidates",
        "label": "世界遺産暫定リスト記載候補（審議結果）",
        "url": "https://www.bunka.go.jp/seisaku/bunkashingikai/bunkazai/sekaitokubetsu/shingi_kekka/besshi_8.html",
    },
    {
        "slug": "national_treasure_buildings",
        "label": "国宝建造物",
        "url": "https://www.bunka.go.jp/seisaku/bunkazai/shokai/yukei_kenzobutsu/kokuho_bunkazai.html",
    },
]

ISSUE_LABEL = "data-source-update"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")


def normalize_html(raw):
    """タグ・スクリプト・コメントを除去して本文テキストだけを抽出、空白を正規化する。"""
    t = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    lines = [ln.strip() for ln in t.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def load_hashes():
    if os.path.exists(HASH_PATH):
        with open(HASH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(h):
    with open(HASH_PATH, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


def snapshot_path(slug):
    return os.path.join(SNAP_DIR, f"{slug}.txt")


def gh(args, input_text=None):
    return subprocess.run(["gh"] + args, input=input_text, text=True,
                           capture_output=True, check=False)


def find_existing_issue(title_prefix, repo):
    r = gh(["issue", "list", "--repo", repo, "--label", ISSUE_LABEL,
            "--state", "open", "--json", "number,title", "--limit", "50"])
    if r.returncode != 0:
        print(f"  gh issue list failed: {r.stderr}", file=sys.stderr)
        return None
    try:
        issues = json.loads(r.stdout)
    except Exception:
        return None
    for it in issues:
        if it["title"].startswith(title_prefix):
            return it["number"]
    return None


def create_or_update_issue(source, diff_text, repo, dry_run):
    title_prefix = f"情報源更新チェック: {source['label']}"
    title = f"{title_prefix}"
    body = (
        f"文化庁のページ「{source['label']}」の内容に変更を検知しました。\n\n"
        f"- URL: {source['url']}\n"
        f"- このマップのデータ（`crawl/national_treasures.json` / `crawl/build_heritage.py` 内のシード）が"
        f"最新の指定・登録状況と食い違っていないか確認し、必要なら更新してください。\n"
        f"- 世界遺産/暫定リストの区分や国宝建造物のfacility分類は自動判定していません。人が本文を読んで判断してください。\n\n"
        f"### 差分（旧 → 新、抜粋）\n```diff\n{diff_text}\n```\n"
    )
    if dry_run:
        print(f"  [dry-run] would create/update issue: {title}")
        print(body)
        return

    num = find_existing_issue(title_prefix, repo)
    if num:
        r = gh(["issue", "comment", str(num), "--repo", repo, "--body", body])
        if r.returncode != 0:
            print(f"  gh issue comment failed: {r.stderr}", file=sys.stderr)
        else:
            print(f"  updated existing issue #{num}")
    else:
        r = gh(["issue", "create", "--repo", repo, "--title", title,
                "--body", body, "--label", ISSUE_LABEL])
        if r.returncode != 0:
            print(f"  gh issue create failed: {r.stderr}", file=sys.stderr)
        else:
            print(f"  created issue: {r.stdout.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Issue作成/コミットをせず結果を表示するのみ")
    args = ap.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not args.dry_run and not repo:
        print("GITHUB_REPOSITORY が未設定です（--dry-run で確認してください）", file=sys.stderr)
        sys.exit(1)

    os.makedirs(SNAP_DIR, exist_ok=True)
    hashes = load_hashes()
    any_changed = False

    for src in SOURCES:
        slug = src["slug"]
        print(f"checking: {src['label']} ({src['url']})")
        try:
            raw = fetch(src["url"])
        except Exception as e:
            print(f"  fetch failed: {e}", file=sys.stderr)
            continue
        text = normalize_html(raw)
        new_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        old_hash = hashes.get(slug)

        if old_hash is None:
            print("  first run — no snapshot to compare against yet"
                  + (" (dry-run: not saving)" if args.dry_run else ""))
        elif old_hash != new_hash:
            any_changed = True
            print("  CHANGED")
            old_path = snapshot_path(slug)
            old_text = ""
            if os.path.exists(old_path):
                with open(old_path, "r", encoding="utf-8") as f:
                    old_text = f.read()
            diff_lines = list(difflib.unified_diff(
                old_text.splitlines(), text.splitlines(),
                lineterm="", n=1))[:120]
            diff_text = "\n".join(diff_lines) or "(差分の詳細を表示できませんでした)"
            create_or_update_issue(src, diff_text, repo, args.dry_run)
        else:
            print("  no change")

        if not args.dry_run:
            with open(snapshot_path(slug), "w", encoding="utf-8") as f:
                f.write(text)
            hashes[slug] = new_hash

    if not args.dry_run:
        save_hashes(hashes)

    if not any_changed:
        print("すべての情報源に変更なし")


if __name__ == "__main__":
    main()
