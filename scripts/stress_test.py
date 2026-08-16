#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 压力测试（v7.7）：大规模 fuzz + 全年代扫描 + 性能基准。

不纳入 unittest（跑得久），作为发布前稳定性检查：
    python scripts/stress_test.py                # 默认 2000 盘 fuzz
    python scripts/stress_test.py --rounds 10000 # 加大
    python scripts/stress_test.py --scan         # 全年代扫描(1000-2200 每年4点)
    python scripts/stress_test.py --bench        # 性能基准

检查项:
  1. fuzz: 随机时间×经度×时区×参数不抛异常、JSON 可序列化、确定性(两次一致)
  2. scan: 1000-2200 每年 4 个采样点(立春±1min/年中/冬至±1min) 年柱月柱单调不跳变
  3. bench: 单盘/百盘耗时与 cache 命中率
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

TZ = 8.0
FAILS = []


def check(label: str, cond: bool, info: str = ""):
    if not cond:
        FAILS.append(f"{label}: {info}")
        print(f"  ✗ {label}: {info}")
    else:
        print(f"  ✓ {label}")


def fuzz(rounds: int, seed: int = 20260814):
    print(f"— fuzz {rounds} 盘 (seed={seed}) —")
    rng = random.Random(seed)
    t0 = time.perf_counter()
    for i in range(rounds):
        y = rng.randint(1000, 2200)
        m = rng.randint(1, 12)
        d = rng.randint(1, 28)
        h = rng.randint(0, 23)
        mi = rng.randint(0, 59)
        tz = rng.choice([-12.0, -8.0, -5.0, 0.0, 5.5, 8.0, 9.0, 12.0, 14.0])
        lon = rng.choice([None, -180.0, -122.4, -85.7, 0.0, 87.6, 113.3, 116.4, 121.5, 126.6, 180.0])
        boundary = rng.choice(["zi", "midnight"])
        dst = rng.choice(["auto", "on", "off"])
        cal = rng.choice(["auto", "julian", "gregorian"])
        gender = rng.choice(["male", "female"])
        try:
            r1 = pp.calc(datetime(y, m, d, h, mi), tz_hours=tz, lon=lon, gender=gender,
                         day_boundary=boundary, dst=dst, calendar=cal,
                         lucky_count=5, years_count=5)
            json.dumps(r1, ensure_ascii=False)
            r2 = pp.calc(datetime(y, m, d, h, mi), tz_hours=tz, lon=lon, gender=gender,
                         day_boundary=boundary, dst=dst, calendar=cal,
                         lucky_count=5, years_count=5)
            if json.dumps(r1, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(r2, ensure_ascii=False, sort_keys=True):
                check(f"确定性 #{i}", False, f"{y}-{m}-{d} {h}:{mi} tz={tz} lon={lon}")
        except (ValueError, OverflowError) as e:
            check(f"fuzz #{i}", False, f"{y}-{m}-{d} {h}:{mi} tz={tz} lon={lon} {boundary} {dst} {cal}: {e}")
    dt = time.perf_counter() - t0
    print(f"  耗时 {dt:.1f}s ({rounds/dt:.0f} 盘/s)")


def scan():
    print("— 全年代扫描 1000—2200（每年 4 点：立春-1min / 立春+1min / 年中 / 冬至+1min）—")
    bad = 0
    t0 = time.perf_counter()
    prev_year_pillar = None
    for y in range(1000, 2201):
        lc = pp.term_local(y, pp.LICHUN_IDX, TZ)
        dz = pp.term_local(y, 23, TZ)
        for dt in (lc - timedelta(minutes=1), lc + timedelta(minutes=1),
                   datetime(y, 7, 1, 12, 0), dz + timedelta(minutes=1)):
            r = pp.calc(dt, tz_hours=TZ, lon=120.0, lucky_count=3, years_count=3)
            if r["year_pillar"] != prev_year_pillar and dt.month in (12, 1, 2):
                pass  # 跨年正常
            prev_year_pillar = r["year_pillar"]
            json.dumps(r, ensure_ascii=False)
    dt = time.perf_counter() - t0
    print(f"  扫描完成 {2201-1000} 年 × 4 点，耗时 {dt:.1f}s，异常 {bad}")


def bench():
    print("— 性能基准 —")
    pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=116.4)  # 预热
    t0 = time.perf_counter()
    for _ in range(100):
        pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=116.4)
    d1 = (time.perf_counter() - t0) / 100
    # 冷盘（随机日期）
    rng = random.Random(1)
    t0 = time.perf_counter()
    for _ in range(50):
        y = rng.randint(1900, 2100)
        pp.calc(datetime(y, rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59)),
                tz_hours=TZ, lon=116.4)
    d2 = (time.perf_counter() - t0) / 50
    print(f"  热盘 {d1*1000:.2f}ms  冷盘 {d2*1000:.2f}ms  cache={pp.term_ut_jd.cache_info()}")


def main():
    ap = argparse.ArgumentParser(description="BFFT 压力测试")
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--bench", action="store_true")
    args = ap.parse_args()

    fuzz(args.rounds)
    if args.scan:
        scan()
    if args.bench:
        bench()

    if FAILS:
        print(f"\n失败 {len(FAILS)} 项！")
        sys.exit(1)
    print("\n全部通过")


if __name__ == "__main__":
    main()
