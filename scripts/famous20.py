#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20 位名人 V7 排盘复现脚本 — BFFT v7.1.

用法:
  python scripts/famous20.py            # 打印排盘表
  python scripts/famous20.py --json     # 输出 JSON

数据说明：出生时刻可靠度分级见 references/famous20-validation.md；
占位时辰（C 级）只用于排盘正确性演示，不得进入命运结论。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

PEOPLE = [
    {"name": "达芬奇", "dt": "1452-04-15 22:00", "tz": 1.0, "lon": 10.9, "cal": "julian", "note": "B-"},
    {"name": "牛顿", "dt": "1643-01-04 02:00", "tz": 0.0, "lon": -0.6, "cal": "gregorian", "note": "C占位"},
    {"name": "华盛顿", "dt": "1732-02-22 10:00", "tz": -5.0, "lon": -77.0, "cal": "gregorian", "note": "C占位"},
    {"name": "莫扎特", "dt": "1756-01-27 20:00", "tz": 1.0, "lon": 13.0, "cal": "gregorian", "note": "A-"},
    {"name": "歌德", "dt": "1749-08-28 12:00", "tz": 1.0, "lon": 8.7, "cal": "gregorian", "note": "C占位"},
    {"name": "拿破仑", "dt": "1769-08-15 12:00", "tz": 1.0, "lon": 8.7, "cal": "gregorian", "note": "B-"},
    {"name": "贝多芬", "dt": "1770-12-16 12:00", "tz": 1.0, "lon": 7.1, "cal": "gregorian", "note": "C占位"},
    {"name": "林肯", "dt": "1809-02-12 12:00", "tz": -6.0, "lon": -85.7, "cal": "gregorian", "note": "C占位"},
    {"name": "达尔文", "dt": "1809-02-12 12:00", "tz": 0.0, "lon": -2.8, "cal": "gregorian", "note": "C占位"},
    {"name": "特斯拉", "dt": "1856-07-10 00:00", "tz": 1.0, "lon": 15.4, "cal": "gregorian", "note": "B-"},
    {"name": "爱因斯坦", "dt": "1879-03-14 11:30", "tz": 1.0, "lon": 10.0, "cal": "gregorian", "note": "A-"},
    {"name": "鲁迅", "dt": "1881-09-25 08:00", "tz": 8.0, "lon": 120.6, "cal": "gregorian", "note": "B-"},
    {"name": "蒋介石", "dt": "1887-10-31 12:00", "tz": 8.0, "lon": 121.4, "cal": "gregorian", "note": "B+"},
    {"name": "希特勒", "dt": "1889-04-20 18:30", "tz": 1.0, "lon": 13.0, "cal": "gregorian", "note": "A-"},
    {"name": "毛泽东", "dt": "1893-12-26 07:00", "tz": 8.0, "lon": 112.5, "cal": "gregorian", "note": "B+"},
    {"name": "周恩来", "dt": "1898-03-05 08:00", "tz": 8.0, "lon": 119.1, "cal": "gregorian", "note": "B-"},
    {"name": "张爱玲", "dt": "1920-09-30 12:00", "tz": 8.0, "lon": 121.5, "cal": "gregorian", "note": "C占位"},
    {"name": "乔布斯", "dt": "1955-02-24 19:15", "tz": -8.0, "lon": -122.4, "cal": "gregorian", "note": "A"},
    {"name": "比尔·盖茨", "dt": "1955-10-28 22:00", "tz": -8.0, "lon": -122.3, "cal": "gregorian", "note": "B-"},
    {"name": "马斯克", "dt": "1971-06-28 10:35", "tz": 2.0, "lon": 28.2, "cal": "gregorian", "note": "B-"},
]


def main():
    ap = argparse.ArgumentParser(description="20 位名人 V7 排盘 (BFFT)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for p in PEOPLE:
        dt = datetime.strptime(p["dt"], "%Y-%m-%d %H:%M")
        r = pp.calc(dt, tz_hours=p["tz"], lon=p["lon"], gender="male",
                    day_boundary="zi", calendar=p["cal"], lucky_count=3)
        results.append({
            "name": p["name"], "note": p["note"], "input": p["dt"],
            "tz": p["tz"], "lon": p["lon"], "calendar": p["cal"],
            "four_pillars": " ".join([r["year_pillar"], r["month_pillar"],
                                      r["day_pillar"], r["hour_pillar"]]),
            "solar": r["solar_time"]["true_solar_time"],
            "jiao_time": r["jiao_time"], "jiao_age": r["jiao_age"],
            "minggong": r["minggong"],
            "taiyuan_primary": r["taiyuan"]["primary"],
            "taiyuan_alt": r["taiyuan"]["alt"],
            "lucky": [l["ganzhi"] for l in r["lucky"]],
        })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"{'姓名':<6}{'四柱':<24}{'真太阳时':<21}{'交运':<12}{'命宫':<5}{'首3运'}")
    for r in results:
        print(f"{r['name']:<6}{r['four_pillars']:<24}{r['solar']:<21}"
              f"{r['jiao_time']:<12}{r['minggong']:<5}{' '.join(r['lucky'])}")


if __name__ == "__main__":
    main()
