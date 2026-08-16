#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 前端 CLI — 四柱八字排盘命令行入口（v7.13 前后端分离）。

后端引擎：scripts/pai_pan.py（纯库，零 CLI 代码）。
本文件只做参数解析与输出渲染；所有计算走 pai_pan.calc。

用法:
  python scripts/cli.py "2024-05-23 10:00" --name 鸣潮 --lon 113.3 --json
  兼容: python scripts/pai_pan.py "2024-05-23 10:00"  # 自动转发到本文件
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import pai_pan as pp  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="四柱八字排盘 (BFFT)")
    ap.add_argument("datetime", help='当地钟表时间, e.g. "2024-05-23 10:00"')
    ap.add_argument("--name", default="")
    ap.add_argument("--tz", type=float, default=8.0, help="UTC 偏移小时, 默认 8")
    ap.add_argument("--lon", type=float, default=None,
                    help="出生地经度(东正西负), 用于真太阳时修正; 人盘强烈建议提供")
    ap.add_argument("--gender", choices=["male", "female"], default="male",
                    help="大运顺逆用; game/product 默认 male")
    ap.add_argument("--day-boundary", choices=["zi", "midnight"], default="zi",
                    help="换日流派: zi=23时换日(默认), midnight=00时换日")
    ap.add_argument("--dst", choices=["auto", "on", "off"], default="auto",
                    help="中国 1986—1991 夏令时处理, 默认 auto")
    ap.add_argument("--calendar", choices=["auto", "julian", "gregorian"],
                    default="auto",
                    help="输入日期的历法。auto=1582-10-15 前按儒略历(史料惯例), 默认 auto")
    ap.add_argument("--lucky", type=int, default=10)
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    return ap


def run(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    if args.lucky < 1 or args.years < 0:
        ap.error("--lucky 需 >=1, --years 需 >=0")
    if args.lon is not None and not -180.0 <= args.lon <= 180.0:
        ap.error("--lon 需在 -180..180")

    try:
        dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ap.error('时间格式应为 "YYYY-MM-DD HH:MM"')

    result = pp.calc(dt, tz_hours=args.tz, gender=args.gender,
                     lucky_count=args.lucky, years_count=args.years,
                     lon=args.lon, day_boundary=args.day_boundary, dst=args.dst,
                     calendar=args.calendar)
    if args.name:
        result["name"] = args.name
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.name:
            print(f"名称: {args.name}")
        print(pp.render(result))
    return 0


if __name__ == "__main__":
    sys.exit(run())
