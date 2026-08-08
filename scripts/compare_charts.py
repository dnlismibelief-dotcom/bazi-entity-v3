#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同盘/两盘对比工具 — BFFT v7.1.

把两张盘的模型内可观察差异全部列出：四柱、真太阳时、历法、交运、大运表、
命宫、胎元两派、五行统计，以及时辰敏感性提示（±1 小时内四柱变化）。

用途：
  1. 同盘异命分析（如林肯/达尔文）：确认模型内哪些变量相同、哪些不同；
  2. 校准登记前的输入复核：同一盘不同时刻/经度会怎样变化。

用法:
  python scripts/compare_charts.py A --p1-dt "1809-02-12 12:00" --p1-tz -6 --p1-lon -85.7
                                   B --p2-dt "1809-02-12 12:00" --p2-tz 0 --p2-lon -2.8
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)


def chart(cfg: dict) -> dict:
    dt = datetime.strptime(cfg["dt"], "%Y-%m-%d %H:%M")
    r = pp.calc(
        dt,
        tz_hours=cfg.get("tz", 8.0),
        lon=cfg.get("lon"),
        gender=cfg.get("gender", "male"),
        day_boundary=cfg.get("day_boundary", "zi"),
        calendar=cfg.get("calendar", "auto"),
        lucky_count=cfg.get("lucky", 10),
    )
    return {
        "label": cfg.get("label", cfg["dt"]),
        "four_pillars": " ".join(
            [r["year_pillar"], r["month_pillar"], r["day_pillar"], r["hour_pillar"]]
        ),
        "solar_time": r["solar_time"]["true_solar_time"],
        "jiao_time": r["jiao_time"],
        "jiao_age": r["jiao_age"],
        "minggong": r["minggong"],
        "taiyuan_primary": r["taiyuan"]["primary"],
        "taiyuan_alt": r["taiyuan"]["alt"],
        "lucky": [{"ganzhi": l["ganzhi"], "start": l["start"]} for l in r["lucky"]],
        "warnings": r["warnings"],
    }


def sensitivity(cfg: dict) -> dict:
    """把输入时刻前后各 3 小时按 1 小时步长重排，统计四柱组合数。"""
    base = datetime.strptime(cfg["dt"], "%Y-%m-%d %H:%M")
    seen = {}
    for h in range(-3, 4):
        dt = base + timedelta(hours=h)
        c = dict(cfg)
        c["dt"] = dt.strftime("%Y-%m-%d %H:%M")
        try:
            r = pp.calc(
                dt,
                tz_hours=c.get("tz", 8.0),
                lon=c.get("lon"),
                day_boundary=c.get("day_boundary", "zi"),
                calendar=c.get("calendar", "auto"),
            )
            gz = " ".join([r["year_pillar"], r["month_pillar"], r["day_pillar"], r["hour_pillar"]])
            seen.setdefault(gz, []).append(dt.strftime("%H:%M"))
        except Exception:
            pass
    return {"distinct_charts": len(seen), "by_hour": seen}


def compare(cfg1: dict, cfg2: dict) -> dict:
    c1, c2 = chart(cfg1), chart(cfg2)
    s1, s2 = sensitivity(cfg1), sensitivity(cfg2)
    return {
        "chart_a": c1,
        "chart_b": c2,
        "same_four_pillars": c1["four_pillars"] == c2["four_pillars"],
        "same_lucky": [l["ganzhi"] for l in c1["lucky"]] == [l["ganzhi"] for l in c2["lucky"]],
        "jiao_time_diff_days": abs(
            (datetime.strptime(c1["jiao_time"], "%Y-%m-%d")
             - datetime.strptime(c2["jiao_time"], "%Y-%m-%d")).days
        ),
        "sensitivity_a": s1,
        "sensitivity_b": s2,
    }


def render(result: dict) -> str:
    lines = []
    a, b = result["chart_a"], result["chart_b"]
    lines.append(f"盘A {a['label']}: {a['four_pillars']}  真太阳时 {a['solar_time']}"
                 f"  交运 {a['jiao_time']} ({a['jiao_age']})  命宫 {a['minggong']}"
                 f"  胎元 {a['taiyuan_primary']}/{a['taiyuan_alt']}")
    lines.append(f"盘B {b['label']}: {b['four_pillars']}  真太阳时 {b['solar_time']}"
                 f"  交运 {b['jiao_time']} ({b['jiao_age']})  命宫 {b['minggong']}"
                 f"  胎元 {b['taiyuan_primary']}/{b['taiyuan_alt']}")
    lines.append(f"四柱相同: {result['same_four_pillars']}   大运序列相同: {result['same_lucky']}"
                 f"   交运日差: {result['jiao_time_diff_days']} 天")
    lines.append("")
    lines.append("盘A 时辰敏感性(±3h 每小时重排):")
    for gz, hs in result["sensitivity_a"]["by_hour"].items():
        lines.append(f"  {gz}  <- {hs}")
    lines.append("盘B 时辰敏感性(±3h 每小时重排):")
    for gz, hs in result["sensitivity_b"]["by_hour"].items():
        lines.append(f"  {gz}  <- {hs}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="两盘对比 (BFFT)")
    for p in ("1", "2"):
        ap.add_argument(f"--p{p}-dt", required=True, help='YYYY-MM-DD HH:MM')
        ap.add_argument(f"--p{p}-tz", type=float, default=8.0)
        ap.add_argument(f"--p{p}-lon", type=float, default=None)
        ap.add_argument(f"--p{p}-cal", default="auto", choices=["auto", "julian", "gregorian"])
        ap.add_argument(f"--p{p}-name", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cfg1 = {"label": args.p1_name or "A", "dt": args.p1_dt, "tz": args.p1_tz,
            "lon": args.p1_lon, "calendar": args.p1_cal}
    cfg2 = {"label": args.p2_name or "B", "dt": args.p2_dt, "tz": args.p2_tz,
            "lon": args.p2_lon, "calendar": args.p2_cal}
    result = compare(cfg1, cfg2)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))


if __name__ == "__main__":
    main()
