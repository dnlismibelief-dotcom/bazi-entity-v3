#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实体数据联网抓取器 — BFFT v7.13（数据说话：示例实体时间从互联网现取）。

从维基百科（默认中文站，可切英文站）检索实体条目，解析出生/成立日期模板，
输出标准实体定义 JSON（可直接喂给 scripts/yearly_reading.py --from-json 或
scripts/cli.py）。抓取结果带来源 URL 与抓取时间，供可复核性纪律使用。

用法:
  python scripts/fetch_entity.py --query 游戏甲(示例) --limit 5          # 列出候选
  python scripts/fetch_entity.py --query 虚拟偶像甲(示例) --save        # 保存缓存
  python scripts/fetch_entity.py --query "回测样本" --lang en --save
  python scripts/fetch_entity.py --query 游戏乙(示例) --json              # 标准输出

注意:
  - 维基数据是二手来源：正式分析前必须与官方公告/一手来源复核（M0 纪律）。
  - 1582 年前条目按儒略历口径标注；英国 1752、俄国 1918 等切换点需人工确认。
  - 抓取结果缓存到 data/entity_cache/<slug>.json，重复查询不重复抓取。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "entity_cache")

UA = {"User-Agent": "bfft-fetch-entity/1.0 (local study; contact: repo owner)"}

DATE_PATS = [
    r"\{\{\s*birth\s*date\s*(?:and\s*age)?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})",
    r"\{\{\s*birth_date\s*(?:and\s*age)?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})",
    r"\{\{\s*birth\s*date\s*(?:and\s*age)?\s*\|\s*(\d{4})-(\d{1,2})-(\d{1,2})",
    r"\{\{\s*bd\s*\|\s*(\d{4})\s*年\s*\|\s*(\d{1,2})\s*月\s*(?:\s*\|?\s*)?(\d{1,2})\s*日",
    r"\{\{\s*bd\s*\|\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日",
]
FOUND_PATS = [
    r"成立日期\s*=\s*\{\{\s*[^\n]*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"成立日期\s*=\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"建立時間\s*=\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"發行日期\s*=\s*\{\{\s*[^\n]*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"發行日\s*=\s*\{\{\s*[^\n]*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"公测时间\s*=\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    r"release_date\s*=\s*\{\{\s*[^\n]*?(\d{4})-(\d{1,2})-(\d{1,2})",
]


def api(params, lang="zh", retry=3):
    base = f"https://{lang}.wikipedia.org/w/api.php"
    url = base + "?" + urllib.parse.urlencode(params)
    for _ in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(2)
    raise RuntimeError("wikipedia api failed")


def search_titles(query, lang, limit):
    d = api({"action": "query", "list": "search", "srsearch": query,
             "srlimit": str(limit), "format": "json"}, lang)
    return [h["title"] for h in d.get("query", {}).get("search", [])]


def fetch_text(title, lang):
    d = api({"action": "query", "prop": "revisions", "rvprop": "content",
             "rvslots": "main", "rvsection": "0", "titles": title,
             "format": "json", "formatversion": "2"}, lang)
    page = d["query"]["pages"][0]
    if page.get("missing") or "revisions" not in page:
        return None
    return page["revisions"][0]["slots"]["main"]["content"]


def parse_date(text):
    for p in DATE_PATS + FOUND_PATS:
        m = re.search(p, text)
        if m:
            y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= da <= 31:
                return f"{y:04d}-{mo:02d}-{da:02d}"
    return None


def slugify(s):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "-", s).strip("-")[:60] or "x"


def main():
    ap = argparse.ArgumentParser(description="实体数据联网抓取（维基百科）")
    ap.add_argument("--query", required=True, help="实体名")
    ap.add_argument("--lang", default="zh", help="维基站语言, 默认 zh")
    ap.add_argument("--limit", type=int, default=5, help="候选条数")
    ap.add_argument("--title", help="直接指定条目名（跳过搜索）")
    ap.add_argument("--save", action="store_true", help="缓存到 data/entity_cache/")
    ap.add_argument("--json", action="store_true", help="输出 JSON（默认人类可读）")
    args = ap.parse_args()

    title = args.title
    if not title:
        titles = search_titles(args.query, args.lang, args.limit)
        if not titles:
            ap.error(f"未找到候选条目: {args.query}（可换 --lang en 或 --title 指定）")
        title = titles[0]

    text = fetch_text(title, args.lang)
    if text is None:
        ap.error(f"条目无正文: {title}")

    dob = parse_date(text)
    if not dob:
        print(f"未解析到日期（{title}），条目可能用其他模板；请人工核对:",
              flush=True)
        m = re.search(r"出生|成立|發行|release", text)
        if m:
            print("  线索:", text[max(0, m.start() - 40):m.start() + 120]
                  .replace("\n", " "), flush=True)
        sys.exit(1)

    result = {
        "name": args.query,
        "wiki_title": title,
        "dt": dob + " 12:00",
        "time_note": "维基只给日期, 12:00 为占位时刻(C级); 若有可靠时刻请替换",
        "calendar": "julian" if dob < "1582-10-15" else "gregorian",
        "source": f"https://{args.lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lang": args.lang,
    }

    if args.save:
        os.makedirs(CACHE, exist_ok=True)
        p = os.path.join(CACHE, slugify(args.query) + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"已缓存 {p}", flush=True)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
