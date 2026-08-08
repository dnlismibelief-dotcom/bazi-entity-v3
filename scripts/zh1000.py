#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国名人三柱批量排盘与分布统计 — BFFT v7.2.

数据: data/zh_birthdates.json（中文维基百科职业分类采集，公历出生日期）。
方法: 全部按 12:00 占位时辰、UTC+8、无经度排盘——只使用年/月/日三柱；
      时柱、命宫、胎元、起运点不进入任何结论（时辰占位纪律）。
用途: 描述性分布研究 + 排盘正确性冒烟；不是命运拟合，不构成验证。

用法:
  python scripts/zh1000.py            # 统计摘要
  python scripts/zh1000.py --json     # 全量 JSON
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)


def main():
    ap = argparse.ArgumentParser(description="中国名人三柱分布 (BFFT)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(ROOT, "data", "zh_birthdates.json"), encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for rec in data:
        dt = datetime.strptime(rec["dob"] + " 12:00", "%Y-%m-%d %H:%M")
        r = pp.calc(dt, tz_hours=8.0, lon=None, gender="male",
                    day_boundary="zi", calendar="auto")
        results.append({
            "name": rec["name"], "cat": rec.get("cat", ""), "dob": rec["dob"],
            "year_pillar": r["year_pillar"], "month_pillar": r["month_pillar"],
            "day_pillar": r["day_pillar"], "day_master": r["day_master"],
        })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return

    years = [int(r["dob"][:4]) for r in results]
    dm = Counter(r["day_master"] for r in results)
    mz = Counter(r["month_pillar"][1] for r in results)
    dp = Counter(r["day_pillar"] for r in results)

    print(f"样本数: {len(results)}  年份范围: {min(years)}–{max(years)}")
    print("日主分布:", " ".join(f"{g}{dm.get(g,0)}" for g in "甲乙丙丁戊己庚辛壬癸"))
    print("月令分布:", " ".join(f"{z}{mz.get(z,0)}" for z in "子丑寅卯辰巳午未申酉戌亥"))
    print("日柱 TOP10:", " ".join(f"{k}{v}" for k, v in dp.most_common(10)))
    print("说明: 时柱为占位, 不参与统计与结论。")


if __name__ == "__main__":
    main()
