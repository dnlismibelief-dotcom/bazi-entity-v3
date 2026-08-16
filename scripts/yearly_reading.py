#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐年命盘生成 — BFFT v7.13（前后端分离·去硬编码实体）。

v7.13 起不再内置任何实体（原神/鸣潮/泰勒/乃琳等案例数据已从代码中移除，
示例移至 examples/entities.json 供显式引用）。实体时间必须由调用方提供：
要么命令行参数现给，要么 --from-json 读实体定义文件，要么用
scripts/fetch_entity.py 联网现取（数据说话，不依赖仓库内置案例）。

用法:
  # 单实体（命令行参数）
  python scripts/yearly_reading.py --name 鸣潮 --dt "2024-05-23 10:00" \
      --tz 8 --lon 113.3 --from 2024 --to 2040 --md

  # 批量（实体定义文件，格式见 examples/entities.json）
  python scripts/yearly_reading.py --from-json examples/entities.json --md

复用 yearly_bazi 的岁运关系规则（同一 rulebook，口径一致）。
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

spec = importlib.util.spec_from_file_location("yearly_bazi", os.path.join(ROOT, "scripts", "yearly_bazi.py"))
yb = importlib.util.module_from_spec(spec)
sys.modules["yearly_bazi"] = yb
spec.loader.exec_module(yb)
pp = yb.pp


def build(ent: dict) -> dict:
    dt = datetime.strptime(ent["dt"], "%Y-%m-%d %H:%M")
    chart = pp.calc(dt, tz_hours=ent["tz"], lon=ent.get("lon"), gender=ent["gender"],
                    day_boundary="zi", calendar=ent.get("calendar", "auto"),
                    lucky_count=10, years_count=0)
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
        "note": ent.get("note", ""),
        "source": ent.get("source", ""),
        "jiao_time": chart["jiao_time"],
        "lucky": [{"ganzhi": l["ganzhi"], "start": l["start"]} for l in chart["lucky"]],
        "years": years,
    }


def to_md(data: list[dict]) -> str:
    out = []
    for ent in data:
        out.append(f"## {ent['entity']}　{ent['four_pillars']}　{ent['day_master']}日主")
        out.append(f"> {ent['note']}　交运 {ent['jiao_time']}"
                   + (f"　来源: {ent['source']}" if ent.get("source") else ""))
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
    ap = argparse.ArgumentParser(description="逐年命盘生成（实体数据须显式提供）")
    ap.add_argument("--name", help="实体名（单实体模式）")
    ap.add_argument("--dt", help='出生/成立时间 "YYYY-MM-DD HH:MM"（单实体模式）')
    ap.add_argument("--tz", type=float, default=8.0)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--gender", choices=["male", "female"], default="male")
    ap.add_argument("--calendar", choices=["auto", "julian", "gregorian"], default="auto")
    ap.add_argument("--from", dest="from_year", type=int, help="起年（单实体模式）")
    ap.add_argument("--to", dest="to_year", type=int, help="止年（单实体模式）")
    ap.add_argument("--note", default="", help="实体备注")
    ap.add_argument("--source", default="", help="数据来源标注（必填鼓励）")
    ap.add_argument("--from-json", help="实体定义文件（批量模式，格式见 examples/entities.json）")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--out", default="dist/yearly-reading.json")
    args = ap.parse_args()

    if args.from_json:
        with open(args.from_json, encoding="utf-8") as f:
            entities = json.load(f)
    elif args.name and args.dt and args.from_year is not None and args.to_year is not None:
        entities = [{
            "name": args.name, "dt": args.dt, "tz": args.tz, "lon": args.lon,
            "gender": args.gender, "calendar": args.calendar,
            "from": args.from_year, "to": args.to_year,
            "note": args.note, "source": args.source,
        }]
    else:
        ap.error("须提供实体数据: --from-json <文件> 或 --name/--dt/--from/--to; "
                 "示例见 examples/entities.json（也可用 scripts/fetch_entity.py 联网现取）")

    data = [build(e) for e in entities]
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
