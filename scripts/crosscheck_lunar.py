#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT × lunar_python 交叉验证（v7.9 融合，可选依赖）。

lunar_python（6tail 农历库，MIT）作为第二个独立排盘参照，与 iztro/MingLi-Bench
构成双重外部验证。脚本为**可选**运行（需要 pip install lunar_python），
不进入主流程与 CI（保持 BFFT 零依赖纪律）。

口径对齐：
  * BFFT:  立春分年、节令分月、无经度修正（lon=None）、无夏令时
  * lunar: 用 *Exact 系列（getYearInGanZhiExact 按立春、getMonthInGanZhiExact 按节令）
  * 双方都用标准时（不做真太阳时），日柱换日差异（zi/midnight）单独标注

样本：
  * MingLi-Bench 160 例（大赛官方题库，tz=8 与 iztro 口径一致）
  * 四实体盘（原神/鸣潮/泰勒/乃琳）
  * 随机 300 盘 fuzz

用法:
  python scripts/crosscheck_lunar.py          # 全部样本
  python scripts/crosscheck_lunar.py --json   # 明细
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

try:
    from lunar_python import Solar
except ImportError:
    print("需要 lunar_python: pip install lunar_python", file=sys.stderr)
    sys.exit(2)

CASES = [
    # (name, datetime, tz, lon, calendar)
    ("原神", "2020-09-28 10:00", 8.0, 121.47, "auto"),
    ("鸣潮", "2024-05-23 10:00", 8.0, 113.3, "auto"),
    ("泰勒", "1989-12-13 08:36", -5.0, -75.93, "auto"),
    ("乃琳", "2020-11-23 12:00", 8.0, 116.4, "auto"),
]


def lunar_pillars(dt: datetime):
    """lunar_python 四柱（立春分年/节令分月的 Exact 口径）。"""
    s = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    l = s.getLunar()
    year = l.getYearInGanZhiExact()
    month = l.getMonthInGanZhiExact()
    day = l.getDayInGanZhi()
    hour = l.getTimeInGanZhi()
    return (year, month, day, hour)


def bfft_pillars(dt: datetime, tz: float, lon, calendar: str, boundary: str = "zi",
                 dst: str = "auto"):
    r = pp.calc(dt, tz_hours=tz, lon=lon, gender="male", day_boundary=boundary,
                calendar=calendar, dst=dst, lucky_count=0, years_count=0)
    return (r["year_pillar"], r["month_pillar"], r["day_pillar"], r["hour_pillar"])


def compare(dt, tz, lon, calendar, boundary="zi", dst="auto") -> dict:
    lu = lunar_pillars(dt)
    bf = bfft_pillars(dt, tz, lon, calendar, boundary, dst)
    return {
        "dt": dt.strftime("%Y-%m-%d %H:%M"), "tz": tz,
        "lunar": lu, "bfft": bf,
        "same": [lu[k] == bf[k] for k in range(4)],
    }


def main():
    ap = argparse.ArgumentParser(description="BFFT × lunar_python 交叉验证")
    ap.add_argument("--align", action="store_true",
                    help="对齐口径再跑：midnight 换日 + 关夏令时（与 lunar 默认一致）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    boundary = "midnight" if args.align else "zi"
    dst = "off" if args.align else "auto"
    label = "对齐口径(midnight+no-dst)" if args.align else "默认口径(zi+夏令时auto)"

    rows = []

    # 1) MingLi-Bench 160 例
    data_path = os.path.join(ROOT, "data", "mingli_bench", "data.json")
    if os.path.exists(data_path):
        data = json.load(open(data_path, encoding="utf-8"))
        for q in data["questions"]:
            b = q["birth_info"]
            dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"])
            rows.append(compare(dt, 8.0, None, "auto", boundary, dst))

    # 2) 四实体盘
    for name, ds, tz, lon, cal in CASES:
        dt = datetime.strptime(ds, "%Y-%m-%d %H:%M")
        r = compare(dt, tz, lon, cal, boundary, dst)
        r["name"] = name
        rows.append(r)

    # 3) 随机 fuzz 300 盘（1900-2100，东八区标准时）
    rng = random.Random(20260815)
    for _ in range(300):
        dt = datetime(rng.randint(1900, 2100), rng.randint(1, 12),
                      rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59))
        rows.append(compare(dt, 8.0, None, "auto", boundary, dst))

    n = len(rows)
    ok = sum(1 for r in rows if all(r["same"]))
    print(f"[{label}] 对比 {n} 例  四柱全同 {ok} ({ok/n:.1%})")
    names = ["年柱", "月柱", "日柱", "时柱"]
    for k in range(4):
        c = sum(1 for r in rows if r["same"][k])
        print(f"  {names[k]}一致 {c}/{n} ({c/n:.1%})")
    if not args.align:
        print("提示: 默认口径下日柱差异=23点换日流派(zi vs midnight), 时柱差异=夏令时回拨;")
        print("      用 --align 对齐口径(midnight+no-dst) 应得 100%")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
