#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐年命盘生成 — BFFT v7.8.

对实体逐年输出「原局四柱 + 当年主运 + 流年干支 + 十神关系 + 岁运冲合」，
供逐年推断使用。复用 yearly_bazi 的岁运关系规则（同一 rulebook，口径一致）。

用法:
  python scripts/yearly_reading.py                # 全部实体 → dist/yearly-reading.json
  python scripts/yearly_reading.py --md           # 同时输出 Markdown 骨架
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location("yearly_bazi", os.path.join(ROOT, "scripts", "yearly_bazi.py"))
yb = importlib.util.module_from_spec(spec)
sys.modules["yearly_bazi"] = yb
spec.loader.exec_module(yb)
pp = yb.pp

ENTITIES = [
    {
        "name": "原神", "dt": "2020-09-28 10:00", "tz": 8.0, "lon": 121.47,
        "gender": "male", "from": 2020, "to": 2035,
        "note": "庚子 乙酉 甲戌 己巳 | 甲木日主身弱官杀重，用印比，喜火制杀；丙戌运主程",
    },
    {
        "name": "鸣潮", "dt": "2024-05-23 10:00", "tz": 8.0, "lon": 113.3,
        "gender": "male", "from": 2024, "to": 2040,
        "note": "甲辰 己巳 丁亥 乙巳 | 丁火日主帝旺双巳，体旺用财官；巳亥冲为变革引擎",
    },
    {
        "name": "Taylor Swift", "dt": "1989-12-13 08:36", "tz": -5.0, "lon": -75.93,
        "gender": "female", "from": 1989, "to": 2031,
        "note": "己巳 丙子 丁未 甲辰 | 丁火日主，月令子水官星；逐年事业高峰规则已回测(+0.224)",
    },
    {
        "name": "乃琳Queen", "dt": "2020-11-23 12:00", "tz": 8.0, "lon": 116.4,
        "gender": "male", "from": 2020, "to": 2036,
        "note": "庚子 丁亥 庚午 壬午 | 庚金日主亥月，食神吐秀；时辰为占位(C级)，只论年月+大运",
    },
]


def build(ent: dict) -> dict:
    dt = datetime.strptime(ent["dt"], "%Y-%m-%d %H:%M")
    chart = pp.calc(dt, tz_hours=ent["tz"], lon=ent["lon"], gender=ent["gender"],
                    day_boundary="zi", calendar="auto", lucky_count=10, years_count=0)
    rows = yb.yearly_rows(chart, ent["from"], ent["to"])
    years = []
    for r in rows:
        years.append({
            "year": r["year"],
            "liunian": r["liunian"],
            "liunian_gan_relation": r["liunian_gan_relation"],
            "liunian_zhi_vs_dayzhi": r["day_zhi_relation"],
            "dayun": r["dayun"],
            "dayun_gan_relation": r["dayun_gan_relation"],
            "dayun_zhi_relation": r["dayun_zhi_relation"],
            "dayun_change": r["dayun_change"],
            "suiyun": r["suiyun"],
        })
    return {
        "entity": ent["name"],
        "four_pillars": " ".join([chart["year_pillar"], chart["month_pillar"],
                                  chart["day_pillar"], chart["hour_pillar"]]),
        "day_master": chart["day_master"],
        "note": ent["note"],
        "jiao_time": chart["jiao_time"],
        "lucky": [{"ganzhi": l["ganzhi"], "start": l["start"]} for l in chart["lucky"]],
        "years": years,
    }


def to_md(data: list[dict]) -> str:
    out = []
    for ent in data:
        out.append(f"## {ent['entity']}　{ent['four_pillars']}　{ent['day_master']}日主")
        out.append(f"> {ent['note']}　交运 {ent['jiao_time']}")
        out.append("")
        out.append("| 年 | 流年 | 大运 | 流年干十神 | 流年支vs日支 | 大运支vs日支 | 岁运 | 交运 |")
        out.append("|---|---|---|---|---|---|---|---|")
        for y in ent["years"]:
            out.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
                y["year"], y["liunian"], y["dayun"], y["liunian_gan_relation"],
                y["liunian_zhi_vs_dayzhi"], y["dayun_zhi_relation"],
                "；".join(y["suiyun"]) if y["suiyun"] else "—",
                "✓" if y["dayun_change"] else ""))
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="逐年命盘生成")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--out", default="dist/yearly-reading.json")
    args = ap.parse_args()

    data = [build(e) for e in ENTITIES]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"写盘 {args.out}")
    if args.md:
        md_path = os.path.splitext(args.out)[0] + ".md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(to_md(data))
        print(f"写盘 {md_path}")


if __name__ == "__main__":
    main()
