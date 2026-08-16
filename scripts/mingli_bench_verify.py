#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MingLi-Bench 排盘交叉验证 — BFFT v7.5.

把 BFFT 排盘引擎与 MingLi-Bench（全球算命师大赛官方题库，DestinyLinker 开源，
MIT）中 iztro 预计算的八字四柱逐题比对，给 BFFT 一个 160 例的外部排盘基准。

数据来源:
  data/mingli_bench/data.json                 160 道大赛真题（含出生信息/标准答案）
  data/mingli_bench/fortune_api_results.json  iztro 预计算盘（含 chineseDate 八字四柱）

方法说明:
  * iztro 是紫微斗数库，chineseDate 字段同时给出八字四柱，口径=北京时间(UTC+8)、
    标准时、未做真太阳时修正（iztro 按传入时间直接排盘）。
  * BFFT 侧对齐口径: tz=8, lon=None(不修正), day_boundary 用默认 zi。
  * 题目只有国家没有城市/经度，海外案例无法做真太阳时修正 —— 这正是本验证要
    量化的边界: 时区/经度信息缺失时排盘的一致性。
  * 海外案例另做 tz 敏感性分析: 换 tz 看四柱对齐率变化。

用法:
  python scripts/mingli_bench_verify.py            # 报告
  python scripts/mingli_bench_verify.py --json     # 逐题明细
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "mingli_bench")

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

COUNTRY_TZ = {  # 题目只有国家；iztro 默认北京时间, 这里给出各国的"常识时区"用于敏感性分析
    "中国": 8.0, "china": 8.0, "usa": -5.0, "japan": 9.0,
    "singapore": 8.0, "malaysia": 8.0,
}


def load():
    with open(os.path.join(DATA_DIR, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(DATA_DIR, "fortune_api_results.json"), encoding="utf-8") as f:
        results = json.load(f)
    by_case = {r["case_id"]: r for r in results}
    return data["questions"], by_case


def bazi_of_iztro(api_response) -> str | None:
    """从 iztro api_response 里取八字四柱，如 '甲寅 戊辰 己亥 壬申'。"""
    d = (api_response.get("data") or {}).get("data") or {}
    return d.get("chineseDate")


def pillars_of(bazi: str):
    if not bazi:
        return None
    parts = bazi.split()
    return tuple(parts) if len(parts) == 4 else None


def bfft_calc(q: dict, tz: float):
    b = q["birth_info"]
    dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"])
    r = pp.calc(dt, tz_hours=tz, lon=None, gender="male", day_boundary="zi",
                lucky_count=0, years_count=0)
    return (r["year_pillar"], r["month_pillar"], r["day_pillar"], r["hour_pillar"])


def compare_all(tz: float, questions, by_case):
    rows = []
    for q in questions:
        case = by_case.get(q.get("case_id") or q["id"])
        iz = pillars_of(bazi_of_iztro(case["api_response"])) if case else None
        if iz is None:
            continue
        try:
            bfft = bfft_calc(q, tz)
        except Exception as e:
            rows.append({"id": q["id"], "country": q["birth_info"]["country"],
                         "iztro": iz, "bfft": None, "err": str(e)})
            continue
        rows.append({"id": q["id"], "country": q["birth_info"]["country"],
                     "iztro": iz, "bfft": bfft,
                     "same": [iz[k] == bfft[k] for k in range(4)]})
    return rows


def report(rows, tz):
    n = len(rows)
    ok = sum(1 for r in rows if all(r["same"]))
    print(f"tz={tz:+g}  对比 {n} 例  四柱全同 {ok}  ({ok/n:.1%})" if n else "无样本")
    names = ["年柱", "月柱", "日柱", "时柱"]
    for k in range(4):
        c = sum(1 for r in rows if r.get("same") and r["same"][k])
        print(f"  {names[k]}一致 {c}/{n} ({c/n:.1%})")
    # 按国家
    by_country = {}
    for r in rows:
        by_country.setdefault(r["country"], []).append(r)
    for c, rs in sorted(by_country.items()):
        cok = sum(1 for r in rs if all(r["same"]))
        print(f"  [{c}] {cok}/{len(rs)} ({cok/len(rs):.1%})")
    return rows


def main():
    ap = argparse.ArgumentParser(description="MingLi-Bench 排盘交叉验证")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    questions, by_case = load()
    rows = compare_all(8.0, questions, by_case)

    if args.json:
        # 纯 JSON 明细（供机器消费）；报告走 --json 时不混入
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    report(rows, 8.0)

    # 海外案例 tz 敏感性: 用各自国家常识时区再比一次
    print()
    print("— 海外案例时区敏感性（国家常识时区 vs iztro 默认北京时间）—")
    overseas = [q for q in questions if q["birth_info"]["country"] not in ("中国", "china")]
    for c, tz in sorted(set((q["birth_info"]["country"], COUNTRY_TZ[q["birth_info"]["country"]])
                            for q in overseas)):
        sub = [q for q in overseas if q["birth_info"]["country"] == c]
        r2 = compare_all(tz, sub, by_case)
        n2 = len(r2)
        ok2 = sum(1 for r in r2 if all(r["same"]))
        print(f"  [{c}] tz={tz:+g}: {ok2}/{n2} ({ok2/n2:.1%} 全同)")


if __name__ == "__main__":
    main()
