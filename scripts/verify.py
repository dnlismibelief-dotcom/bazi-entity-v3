#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校准统计与事前性核验 — BFFT v5.

回答三个问题:
  1. 这些判据是不是**事前**写的？    → 用 git 首次提交时间对比预测窗口起点
  2. 命中率多少？                    → 只统计 A 级、已到期、且非 low_information 的判据
  3. 比瞎猜强吗？                    → Brier 分数与基线 Brier 对比, 给出技巧分数

技巧分数 (Brier Skill Score) = 1 - BS_model / BS_base
  > 0  模型优于"照基线概率报数"
  = 0  与基线无差别（模型没有提供信息）
  < 0  比基线更差

用法:
  python scripts/verify.py                 # 全部
  python scripts/verify.py --strict        # schema 或事前性有问题时以退出码 1 失败(用于 CI)
  python scripts/verify.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_DIR = os.path.join(ROOT, "predictions")

REQUIRED = ["id", "window", "claim", "probability", "base_rate",
            "falsify", "deadline", "evidence_grade", "verdict"]
VALID_VERDICT = {"hit", "miss", "pending", "void"}


def git_first_commit_iso(path: str) -> str | None:
    """文件首次进入版本库的时间（作为"事前"证明）。"""
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", path],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
        return lines[-1] if lines else None
    except Exception:
        return None


def load_files():
    if not os.path.isdir(PRED_DIR):
        return []
    files = sorted(f for f in os.listdir(PRED_DIR) if f.endswith(".json"))
    out = []
    for f in files:
        p = os.path.join(PRED_DIR, f)
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        out.append((f, p, data))
    return out


def check_schema(fname, data):
    problems = []
    for key in ("entity", "entity_type", "anchor", "predictions"):
        if key not in data:
            problems.append(f"{fname}: 缺字段 {key}")
    for pred in data.get("predictions", []):
        pid = pred.get("id", "?")
        for key in REQUIRED:
            if key not in pred:
                problems.append(f"{fname}#{pid}: 缺字段 {key}")
        if pred.get("verdict") not in VALID_VERDICT:
            problems.append(f"{fname}#{pid}: verdict 非法 {pred.get('verdict')!r}")
        for key in ("probability", "base_rate"):
            v = pred.get(key)
            if isinstance(v, (int, float)) and not 0.0 <= v <= 1.0:
                problems.append(f"{fname}#{pid}: {key} 应在 0..1")
        w = pred.get("window")
        if not (isinstance(w, list) and len(w) == 2):
            problems.append(f"{fname}#{pid}: window 应为 [起, 止]")
    return problems


def check_priority(fname, path, data):
    """事前性: git 首次提交须早于窗口起点。"""
    first = git_first_commit_iso(path)
    rows = []
    for pred in data.get("predictions", []):
        w = pred.get("window") or [None, None]
        start = w[0]
        if first is None:
            rows.append((pred.get("id"), "unknown", "尚未提交到 git，无法证明事前"))
            continue
        committed = first[:10]
        if start and committed <= start:
            rows.append((pred.get("id"), "ok", f"提交于 {committed} ≤ 窗口起 {start}"))
        else:
            rows.append((pred.get("id"), "late",
                         f"提交于 {committed} 晚于窗口起 {start}，不能计 A 级"))
    return rows


def stats(all_preds):
    """只统计 A 级、已判定、非低信息量的判据。"""
    scored = [p for p in all_preds
              if p.get("evidence_grade") == "A"
              and p.get("verdict") in ("hit", "miss")
              and not p.get("low_information")]
    n = len(scored)
    if n == 0:
        return {"scored": 0}
    hits = sum(1 for p in scored if p["verdict"] == "hit")
    bs = sum((p["probability"] - (1.0 if p["verdict"] == "hit" else 0.0)) ** 2
             for p in scored) / n
    bs_base = sum((p["base_rate"] - (1.0 if p["verdict"] == "hit" else 0.0)) ** 2
                  for p in scored) / n
    skill = None if bs_base == 0 else 1.0 - bs / bs_base
    return {
        "scored": n,
        "hits": hits,
        "hit_rate": hits / n,
        "mean_probability": sum(p["probability"] for p in scored) / n,
        "mean_base_rate": sum(p["base_rate"] for p in scored) / n,
        "brier": bs,
        "brier_base": bs_base,
        "skill_score": skill,
    }


def main():
    ap = argparse.ArgumentParser(description="校准统计与事前性核验 (v5)")
    ap.add_argument("--strict", action="store_true",
                    help="schema 错误或事前性缺失时以退出码 1 结束（CI 用）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = load_files()
    if not files:
        print("predictions/ 下没有 .json 登记文件")
        return 0

    problems, priority, all_preds, per_entity = [], [], [], []
    for fname, path, data in files:
        problems += check_schema(fname, data)
        priority += [(fname,) + r for r in check_priority(fname, path, data)]
        preds = data.get("predictions", [])
        all_preds += preds
        per_entity.append({
            "file": fname,
            "entity": data.get("entity"),
            "entity_type": data.get("entity_type"),
            "total": len(preds),
            "pending": sum(1 for p in preds if p.get("verdict") == "pending"),
            "a_grade": sum(1 for p in preds if p.get("evidence_grade") == "A"),
            "low_info": sum(1 for p in preds if p.get("low_information")),
        })

    summary = stats(all_preds)
    today = date.today().isoformat()
    overdue = [p for p in all_preds
               if p.get("verdict") == "pending" and str(p.get("deadline", "")) < today]

    if args.json:
        print(json.dumps({"entities": per_entity, "summary": summary,
                          "schema_problems": problems,
                          "priority": [list(r) for r in priority],
                          "overdue": [p["id"] for p in overdue]},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 66)
        print("BFFT 校准报告")
        print("=" * 66)
        for e in per_entity:
            print(f"[{e['entity']}] {e['entity_type']}  判据 {e['total']} 条"
                  f"（A级 {e['a_grade']}，待判 {e['pending']}，低信息量 {e['low_info']}）"
                  f"  <- {e['file']}")
        print()
        print("— 事前性核验（git 首次提交 vs 窗口起点）—")
        for fname, pid, status, msg in priority:
            mark = {"ok": "✓", "late": "✗", "unknown": "?"}[status]
            print(f"  {mark} {pid}: {msg}")
        print()
        if summary["scored"] == 0:
            print("— 命中统计 —")
            print("  暂无已判定的 A 级判据。首个回填截止日："
                  + min((str(p.get('deadline')) for p in all_preds), default="n/a"))
        else:
            s = summary
            print("— 命中统计（仅 A 级、已判定、非低信息量）—")
            print(f"  样本 {s['scored']}  命中 {s['hits']}  命中率 {s['hit_rate']:.0%}")
            print(f"  模型均概率 {s['mean_probability']:.2f}  基线均概率 {s['mean_base_rate']:.2f}")
            print(f"  Brier {s['brier']:.4f}  基线 Brier {s['brier_base']:.4f}")
            if s["skill_score"] is not None:
                verdict = ("优于基线" if s["skill_score"] > 0 else
                           "与基线无差别" if s["skill_score"] == 0 else "劣于基线")
                print(f"  技巧分数 {s['skill_score']:+.3f} → {verdict}")
        if overdue:
            print()
            print("— 已过回填截止仍为 pending —")
            for p in overdue:
                print(f"  ! {p['id']} 截止 {p['deadline']}")
        if problems:
            print()
            print("— schema 问题 —")
            for p in problems:
                print(f"  ! {p}")

    if args.strict:
        late = [r for r in priority if r[2] != "ok"]
        if problems or late:
            print("\nstrict: 存在 schema 问题或事前性未通过", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
