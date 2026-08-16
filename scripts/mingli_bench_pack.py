#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MingLi-Bench 盲测包生成 — BFFT v7.5.

从 data/mingli_bench/data.json 抽取若干题，为每题生成 BFFT 盘面摘要
（四柱/十神/五行/大运/流年表），输出为可供 LLM 推理的 JSON 盲测包。

答案只在 --with-answer 时写入（用于评分脚本）；默认不写答案，
保证盲测时模型看不到标准答案。

用法:
  python scripts/mingli_bench_pack.py --count 20 --seed 7 --out dist/mingli-pack.json
  python scripts/mingli_bench_pack.py --with-answer ...   # 评分用
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
DATA_DIR = os.path.join(ROOT, "data", "mingli_bench")

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

# 已知口径差异案例（夏令时/农历年流派），盲测时排除，避免把口径差异算成推理错误
SKIP_IDS = {f"ftb_{i:04d}" for i in range(11, 16)} | {f"ftb_{i:04d}" for i in range(151, 156)}


def chart_summary(q: dict) -> dict:
    b = q["birth_info"]
    dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"])
    r = pp.calc(dt, tz_hours=8.0, lon=None, gender="male" if b["gender"] == "男" else "female",
                day_boundary="zi", lucky_count=4, years_count=25)
    return {
        "four_pillars": " ".join([r["year_pillar"], r["month_pillar"], r["day_pillar"], r["hour_pillar"]]),
        "day_master": r["day_master"],
        "warnings": r["warnings"],
        "pillars": [
            {"label": p["label"], "ganzhi": p["gan"] + p["zhi"], "shishen": p["shishen_gan"],
             "canggan": p["canggan"]}
            for p in r["pillars"]
        ],
        "wuxing_counts": r["wuxing_counts"],
        "changsheng": r["changsheng"],
        "dayun_direction": r["dayun_direction"],
        "jiao_age": r["jiao_age"],
        "lucky": [{"ganzhi": l["ganzhi"], "start": l["start"], "age": l["age"]} for l in r["lucky"]],
        "liunian": [{"year": x["year"], "ganzhi": x["ganzhi"]} for x in r["liunian"]],
    }


def main():
    ap = argparse.ArgumentParser(description="生成 MingLi-Bench 盲测包")
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="dist/mingli-pack.json")
    ap.add_argument("--with-answer", action="store_true", help="写入标准答案（评分用）")
    args = ap.parse_args()

    with open(os.path.join(DATA_DIR, "data.json"), encoding="utf-8") as f:
        data = json.load(f)

    pool = [q for q in data["questions"] if q["id"] not in SKIP_IDS]
    rng = random.Random(args.seed)
    sample = rng.sample(pool, min(args.count, len(pool)))

    pack = []
    for q in sample:
        item = {
            "id": q["id"],
            "category": q["category"],
            "birth_raw": q["birth_info"]["raw"],
            "question": q["question"],
            "options": [{"letter": o["letter"], "text": o["text"]} for o in q["options"]],
            "chart": chart_summary(q),
        }
        if args.with_answer:
            item["answer"] = q["answer"]
        pack.append(item)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": {"count": len(pack), "seed": args.seed, "with_answer": args.with_answer},
                   "items": pack}, f, ensure_ascii=False, indent=2)
    print(f"写盘 {args.out}: {len(pack)} 题")


if __name__ == "__main__":
    main()
