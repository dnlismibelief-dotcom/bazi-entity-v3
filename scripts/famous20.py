#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20 位明确出生时刻（A/AA 级）名人批量排盘与参照比对 — BFFT v7.5.

数据：data/famous20_times.json
  - 每位名人含出生地钟表时间、历史时区（已核夏令时/战时时间/LMT）、经度、
    来源 URL 与 Rodden 风格评级（A=自传/新闻，AA=出生证）。
  - reference 字段由 scripts/famous20_reference.mjs 用独立实现
    lunar-javascript 生成（生成命令与口径见该文件头部）。

用法:
  python scripts/famous20.py                    # 打印排盘表
  python scripts/famous20.py --json             # 输出 JSON
  python scripts/famous20.py --check            # 与独立参照逐柱比对（有差异时退出码 1）
  python scripts/famous20.py --sensitivity 乔布斯  # 某人 ±3h 时辰敏感性

口径说明：本脚本只检验**排盘引擎正确性**；事后用名人做命理拟合无信息量，
见 references/famous20-validation.md。占位时辰盘（评级 C/DD）已从数据集剔除。
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
DATA_DEFAULT = os.path.join(ROOT, "data", "famous20_times.json")

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

PILLAR_KEYS = ("year_pillar", "month_pillar", "day_pillar", "hour_pillar")
PILLAR_LABELS = ("年柱", "月柱", "日柱", "时柱")


def load_people(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    people = data.get("people", [])
    if not people:
        raise SystemExit(f"{path}: people 为空")
    return people


def run_one(p: dict) -> dict:
    dt = datetime.strptime(p["dt"], "%Y-%m-%d %H:%M")
    r = pp.calc(dt, tz_hours=float(p["tz"]), lon=p.get("lon"), gender=p.get("gender", "male"),
                day_boundary="zi", calendar=p.get("calendar", "auto"), lucky_count=3)
    return {
        "id": p.get("id", ""),
        "name": p["name"],
        "name_en": p.get("name_en", ""),
        "occupation": p.get("occupation", ""),
        "rating": p.get("rating", ""),
        "input": p["dt"],
        "tz": float(p["tz"]),
        "lon": p.get("lon"),
        "calendar": p.get("calendar", "auto"),
        "four_pillars": " ".join(r[k] for k in PILLAR_KEYS),
        "pillars": {k: r[k] for k in PILLAR_KEYS},
        "day_pillar_alt": r["day_pillar_alt"],
        "solar_time": r["solar_time"]["true_solar_time"],
        "jiao_time": r["jiao_time"],
        "jiao_age": r["jiao_age"],
        "minggong": r["minggong"],
        "taiyuan_primary": r["taiyuan"]["primary"],
        "taiyuan_alt": r["taiyuan"]["alt"],
        "lucky": [l["ganzhi"] for l in r["lucky"]],
        "warnings": r["warnings"],
    }


def check(results: list[dict], people: list[dict]) -> dict:
    """逐柱比对独立参照。

    时柱有一个设计使然的差异源：本引擎时柱用**真太阳时**（v5 起），而独立参照
    按出生地钟表时刻取时支。真太阳修正把钟表时刻拖过时辰边界时（本批 6 人），
    两方都"对"，只是口径不同。这里用「独立参照日干 + 引擎真太阳时时支」重推
    五鼠遁时柱：引擎时柱与它一致即判定为 explained_by_solar，不计为错误。
    """
    ref_by_id = {p["id"]: p.get("reference", {}) for p in people}
    rows = []
    for r in results:
        ref = ref_by_id.get(r["id"], {})
        row = {"name": r["name"], "engine": r["four_pillars"],
               "reference": ref.get("four_pillars", "N/A")}
        match = {}
        note = {}
        for key, label in zip(PILLAR_KEYS, PILLAR_LABELS):
            ok = r["pillars"][key] == ref.get(key)
            match[label] = ok
            note[label] = ""
        # 时柱：真太阳时口径复算，识别"设计差异"
        solar_hour = int(r["solar_time"][11:13])
        solar_min = int(r["solar_time"][14:16])
        if not match["时柱"] and ref.get("day_pillar"):
            hz_i = ((solar_hour + 1) // 2) % 12
            eg = pp.GAN[(pp.WUSHU[ref["day_pillar"][0]] + hz_i) % 10] + pp.ZHI[hz_i]
            if r["pillars"]["hour_pillar"] == eg:
                match["时柱"] = True
                note["时柱"] = (f"真太阳时 {solar_hour:02d}:{solar_min:02d} 跨时辰，"
                                f"引擎时柱 {r['pillars']['hour_pillar']} 与设计口径一致")
        row["match"] = match
        row["note"] = note
        row["all_ok"] = all(match.values()) if match else False
        rows.append(row)

    per_pillar = {label: sum(1 for row in rows if row["match"][label])
                  for label in PILLAR_LABELS}
    n = len(rows)
    return {
        "total_people": n,
        "all_ok": sum(1 for row in rows if row["all_ok"]),
        "per_pillar": per_pillar,
        "per_pillar_total": n,
        "mismatches": [row for row in rows if not row["all_ok"]],
        "rows": rows,
    }


def sensitivity(p: dict, hours: int = 3) -> dict:
    base = datetime.strptime(p["dt"], "%Y-%m-%d %H:%M")
    seen = {}
    for h in range(-hours, hours + 1):
        dt = base + timedelta(hours=h)
        q = dict(p)
        q["dt"] = dt.strftime("%Y-%m-%d %H:%M")
        r = run_one(q)
        seen.setdefault(r["four_pillars"], []).append(dt.strftime("%H:%M"))
    return {"name": p["name"], "distinct_charts": len(seen), "by_hour": seen}


def render_table(results: list[dict]) -> str:
    lines = [f"{'姓名':<7}{'评级':<4}{'四柱':<22}{'真太阳时':<20}{'交运':<12}{'命宫':<5}首3运"]
    for r in results:
        lines.append(f"{r['name']:<7}{r['rating']:<4}{r['four_pillars']:<22}"
                     f"{r['solar_time']:<20}{r['jiao_time']:<12}{r['minggong']:<5}"
                     f"{' '.join(r['lucky'])}")
    return "\n".join(lines)


def render_check(report: dict) -> str:
    lines = []
    lines.append("逐柱比对（引擎 vs lunar-javascript 独立参照；✓* = 时柱因真太阳时口径差异，复算后一致）")
    lines.append(f"{'姓名':<8}{'引擎四柱':<22}{'参照四柱':<22}年  月  日  时")
    for row in report["rows"]:
        marks = "  ".join(
            ("✓*" if row["match"][lab] and row["note"][lab] else
             "✓" if row["match"][lab] else "✗")
            for lab in PILLAR_LABELS)
        lines.append(f"{row['name']:<8}{row['engine']:<22}{row['reference']:<22}{marks}")
    lines.append("")
    lines.append(f"合计 {report['total_people']} 人；四柱全对 {report['all_ok']}/{report['total_people']}")
    lines.append("  分柱: " + "  ".join(
        f"{lab} {report['per_pillar'][lab]}/{report['per_pillar_total']}"
        for lab in PILLAR_LABELS))
    notes = [(row["name"], row["note"]["时柱"]) for row in report["rows"] if row["note"]["时柱"]]
    if notes:
        lines.append("")
        lines.append("真太阳时口径说明:")
        for name, n in notes:
            lines.append(f"  {name}: {n}")
    if report["mismatches"]:
        lines.append("")
        lines.append("未解释的不一致样本:")
        for row in report["mismatches"]:
            lines.append(f"  {row['name']}: 引擎 {row['engine']} vs 参照 {row['reference']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="20 位明确出生时刻名人批量排盘 (BFFT v7.5)")
    ap.add_argument("--data", default=DATA_DEFAULT, help="数据文件路径")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="与独立参照四柱逐柱比对")
    ap.add_argument("--sensitivity", metavar="NAME", help="对某位名人做 ±3h 时辰敏感性")
    ap.add_argument("--hours", type=int, default=3, help="敏感性步长范围，默认 ±3")
    args = ap.parse_args()

    people = load_people(args.data)
    results = [run_one(p) for p in people]

    if args.sensitivity:
        hit = next((p for p in people if p["name"] == args.sensitivity), None)
        if hit is None:
            ap.error(f"找不到 {args.sensitivity}；可用: {', '.join(p['name'] for p in people)}")
        s = sensitivity(hit, args.hours)
        if args.json:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        else:
            print(f"{s['name']} ±{args.hours}h 时辰敏感性: {s['distinct_charts']} 种四柱")
            for gz, hs in s["by_hour"].items():
                print(f"  {gz}  <- {hs}")
        return

    if args.check:
        report = check(results, people)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(render_check(report))
        return 1 if report["mismatches"] else 0

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render_table(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
