#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MingLi-Bench 盲测评分 — BFFT v7.5.

把 LLM 逐题给出的答案与标准答案对比，报告准确率与随机基线(25%)差距。

用法:
  python scripts/mingli_bench_score.py dist/mingli-pack-ans.json \
      --answers A,B,C,D,A,B,... --label bfft-flash
  # --answers 与盲测包题序一致；也支持每行一个答案的文本文件
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser(description="盲测评分")
    ap.add_argument("pack", help="带答案的盲测包 JSON")
    ap.add_argument("--answers", help="逗号分隔答案，如 A,B,C")
    ap.add_argument("--answers-file", help="答案文本文件（每行一个）")
    ap.add_argument("--label", default="model")
    args = ap.parse_args()

    with open(args.pack, encoding="utf-8") as f:
        pack = json.load(f)
    items = pack["items"]

    if args.answers:
        answers = [a.strip().upper() for a in args.answers.split(",") if a.strip()]
    elif args.answers_file:
        with open(args.answers_file, encoding="utf-8") as f:
            answers = [ln.strip().upper() for ln in f if ln.strip()]
    else:
        ap.error("需要 --answers 或 --answers-file")

    n = min(len(items), len(answers))
    if n < len(items):
        print(f"警告: 答案数 {len(answers)} < 题数 {len(items)}，只评前 {n} 题", file=sys.stderr)

    correct = 0
    by_cat = {}
    detail = []
    for item, ans in zip(items[:n], answers[:n]):
        right = item["answer"].upper() == ans
        correct += int(right)
        by_cat.setdefault(item["category"], [0, 0])
        by_cat[item["category"]][0] += int(right)
        by_cat[item["category"]][1] += 1
        detail.append({"id": item["id"], "cat": item["category"], "answer": ans,
                       "truth": item["answer"], "correct": right})

    acc = correct / n if n else 0.0
    print(f"[{args.label}] {correct}/{n} = {acc:.1%}  (随机基线 25%)")
    if n >= 8:
        import math
        se = math.sqrt(0.25 * 0.75 / n)
        print(f"  与随机线差距: {acc - 0.25:+.1%}  (±{se:.1%} 标准误)")
    for cat, (c, t) in sorted(by_cat.items()):
        print(f"  [{cat}] {c}/{t} ({c/t:.0%})" if t else "")

    out = os.path.splitext(args.pack)[0] + f".{args.label}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"label": args.label, "n": n, "correct": correct,
                   "accuracy": acc, "random_baseline": 0.25, "detail": detail},
                  f, ensure_ascii=False, indent=2)
    print(f"明细写盘 {out}")


if __name__ == "__main__":
    main()
