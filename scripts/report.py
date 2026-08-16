#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键命理报告生成器 — BFFT v7.14（前端；引擎与模板分居后端/参考层）。

输入出生信息（或现成八字），输出两件产物：
  1. 命盘数据 JSON（四柱/十神/藏干/完整关系/命宫/胎元/人元/大运流年）
  2. 报告骨架 Markdown（按 references/report-template.md 的五板块模板，
     分析段落留给 Agent 填充；骨架自带纪律提示）

用法:
  # 完整模式（推荐）：出生时间 + 性别 + 经度
  python scripts/report.py --name 示例 --dt "1990-01-01 10:00" --tz 8 \\
      --lon 116.4 --gender male --out dist/report

  # 仅八字模式（只有四柱时）：可推十神/关系/命宫/胎元/大运序列，
  # 起运岁数与真太阳时不可算，报告显式标注缺口
  python scripts/report.py --name 示例 --pillars "庚子 丁亥 庚午 壬午" \\
      --gender male --out dist/report
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

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)


def chart_from_datetime(args) -> dict:
    try:
        dt = datetime.strptime(args.dt, "%Y-%m-%d %H:%M")
    except ValueError:
        raise SystemExit('时间格式应为 "YYYY-MM-DD HH:MM"')
    r = pp.calc(dt, tz_hours=args.tz, lon=args.lon, gender=args.gender,
                day_boundary="zi", calendar=args.calendar,
                lucky_count=args.lucky, years_count=args.years)
    r["input_mode"] = "datetime"
    r["gaps"] = []
    return r


def chart_from_pillars(args) -> dict:
    """仅八字模式：四柱字符串 '庚子 丁亥 庚午 壬午'（干前支后）。"""
    parts = args.pillars.replace("，", " ").replace(",", " ").split()
    if len(parts) != 4 or any(len(p) != 2 for p in parts):
        raise SystemExit("--pillars 需四组干支, 如 \"庚子 丁亥 庚午 壬午\"（干前支后）")
    yg, yz, mg, mz, dg, dz, hg, hz = (c for p in parts for c in p)
    for c in yg + mg + dg + hg:
        if c not in pp.GAN:
            raise SystemExit(f"非法天干: {c}")
    for c in yz + mz + dz + hz:
        if c not in pp.ZHI:
            raise SystemExit(f"非法地支: {c}")

    pillars = [
        {"label": "年柱", "gan": yg, "zhi": yz},
        {"label": "月柱", "gan": mg, "zhi": mz},
        {"label": "日柱", "gan": dg, "zhi": dz},
        {"label": "时柱", "gan": hg, "zhi": hz},
    ]
    for p in pillars:
        n = pp.idx60(p["gan"], p["zhi"])
        p["nayin"] = pp.NAYIN_30[n // 2]
        p["canggan"] = pp.CANG[p["zhi"]]
        p["shishen_gan"] = pp.shishen(dg, p["gan"]) if p["label"] != "日柱" else "日主"
        p["shishen_cang"] = [pp.shishen(dg, g) for g in p["canggan"]]

    # 关系（v7.12 全表）
    labels = ["年柱", "月柱", "日柱", "时柱"]
    gan_pairs, zhi_pairs = [], []
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = pillars[i], pillars[j]
            gan_pairs.append({"a": f"{labels[i]}干{a['gan']}", "b": f"{labels[j]}干{b['gan']}",
                              "rel": pp.gan_pair_relations(a["gan"], b["gan"])})
            zhi_pairs.append({"a": f"{labels[i]}支{a['zhi']}", "b": f"{labels[j]}支{b['zhi']}",
                              "rel": pp.zhi_pair_relations(a["zhi"], b["zhi"])})
    sanhe = pp.sanhe_groups([p["zhi"] for p in pillars])

    # 命宫/胎元（可推：只依赖年月时干支）
    month_zhi_i = pp.ZHI.index(mz)
    minggong_gz = pp.minggong(yg, month_zhi_i, hz)

    # 大运序列（方向需性别；起运岁数不可算）
    yang_year = pp.is_yang(yg)
    forward = (yang_year and args.gender == "male") or (not yang_year and args.gender == "female")
    month_n = pp.idx60(mg, mz)
    step = 1 if forward else -1
    lucky = [pp.pillar60((month_n + step * k) % 60) for k in range(1, args.lucky + 1)]

    # 流年（起运点不可算，只给干支序列）
    liunian = []
    for y in range(args.liunian_start, args.liunian_start + args.years):
        liunian.append({"year": y, "ganzhi": pp.GAN[(y - 4) % 10] + pp.ZHI[(y - 4) % 12]})

    gaps = [
        "仅提供四柱, 出生日期未知: 起运岁数/交运年份不可计算, 大运只有干支序列",
        "仅提供四柱, 出生地未知: 真太阳时未修正, 若原盘时辰未经真太阳时校正请人工复核",
    ]
    return {
        "version": pp.calc.__globals__.get("VERSION", "v7"),
        "input_mode": "pillars",
        "year_pillar": yg + yz, "month_pillar": mg + mz,
        "day_pillar": dg + dz, "hour_pillar": hg + hz,
        "day_master": dg,
        "gender": args.gender,
        "pillars": pillars,
        "relations": {"gan_pairs": gan_pairs, "zhi_pairs": zhi_pairs, "sanhe": sanhe},
        "minggong": minggong_gz,
        "dayun_direction": "顺排" if forward else "逆排",
        "lucky_sequence": lucky,
        "liunian": liunian,
        "gaps": gaps,
    }


def render_skeleton(name: str, chart: dict, out_base: str) -> None:
    fm = chart["four_pillars"] if "four_pillars" in chart else " ".join(
        [chart["year_pillar"], chart["month_pillar"],
         chart["day_pillar"], chart["hour_pillar"]])
    lines = [
        f"# {name} 命理报告（BFFT v7.14）",
        "",
        f"命盘: {fm} ｜ 日主: {chart['day_master']} ｜ 输入模式: {chart.get('input_mode')}",
        "",
    ]
    if chart.get("gaps"):
        lines.append("## 数据缺口（必读）")
        for g in chart["gaps"]:
            lines.append(f"- ⚠ {g}")
        lines.append("")
    lines += [
        "> 文化娱乐性质，不作为投资/医疗/婚恋决策依据。",
        "> 分析段落由 Agent 按 references/report-template.md 填充；",
        "> 关键事件不做事后拟合，改事前判据登记（predictions/）。",
        "",
        "## 1. 三盘交叉",
        "- 主盘=四柱（自研引擎）；紫微/星盘 BFFT 未实现，需接入外部排盘并独立标注。",
        "- 相貌/体表特征：只给五行体质倾向（C 级），**不预测胎记/痣**。",
        "- 关键事件：改为 2-3 条未来时间窗判据（含 base_rate/falsify/deadline），回填制。",
        "",
        "## 2. 命局核心",
        "- 身强身弱：_待填充（依据: 月令+根气+得势, 人元司令作定性参考）_",
        "- 喜忌（病药八法）：_待填充_",
        "- 十神/体用/关系：_待填充（关系表已在上方 JSON）_",
        "- 事业/财富/情感建议：_待填充（方向区间, 不给具体标的）_",
        "",
        "## 3. 格局",
        "- 成格判定：_待填充（月令定格→顺逆→成败救应→相神→纯杂）_",
        "- 从格嫌疑：_待填充（双轨并列, 不强行二选一）_",
        "- 格局缺陷与规避：_待填充_",
        "",
        "## 4. 大运（每步 10 年）",
        "- _待填充: 干支/起止/进取或稳健/警惕项（健康仅体质倾向, 不输出疾病诊断）_",
        "",
        "## 5. 七维度",
        "- 父母家庭：_待填充（宫位+星位倾向）_",
        "- 事业：_待填充（十神组合+方位; 吉凶年份判据化）_",
        "- 婚姻：_待填充（特质倾向 C 级; 前世羁绊=文学表达, 显式标注不可验证）_",
        "- 财富：_待填充（生财路径/破财点/理财方向）_",
        "- 个人特质：_待填充（十神性格 S 级; 不输出 MBTI 类标签）_",
        "- 健康：_待填充（五行体质倾向 C 级, 非医疗建议）_",
        "- 子女+宠物：_待填充（子女缘强弱倾向; 不给精确子女数; 宠物=文化娱乐）_",
        "",
        "## 附: 判据清单",
        "- _待填充: ≥2 条 A 级事前预测, 登记 predictions/<name>.json_",
        "",
    ]
    md_path = out_base + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"写盘 {md_path}")


def main():
    ap = argparse.ArgumentParser(description="一键命理报告生成 (BFFT)")
    ap.add_argument("--name", default="命主")
    ap.add_argument("--dt", help='出生时间 "YYYY-MM-DD HH:MM"（完整模式）')
    ap.add_argument("--pillars", help='四柱 "庚子 丁亥 庚午 壬午"（仅八字模式）')
    ap.add_argument("--tz", type=float, default=8.0)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--gender", choices=["male", "female"], default="male")
    ap.add_argument("--calendar", choices=["auto", "julian", "gregorian"], default="auto")
    ap.add_argument("--lucky", type=int, default=8)
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--liunian-start", type=int, default=2026, help="仅八字模式的流年起年")
    ap.add_argument("--out", default="dist/report")
    args = ap.parse_args()

    if args.dt and args.pillars:
        ap.error("--dt 与 --pillars 二选一")
    if args.lon is not None and not -180.0 <= args.lon <= 180.0:
        ap.error("--lon 需在 -180..180")
    if args.lucky < 1 or args.years < 0:
        ap.error("--lucky 需 >=1, --years 需 >=0")
    if args.dt:
        chart = chart_from_datetime(args)
    elif args.pillars:
        chart = chart_from_pillars(args)
    else:
        ap.error("需提供 --dt（出生时间）或 --pillars（现成四柱）")

    chart["name"] = args.name
    json_path = args.out + ".json"
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    print(f"写盘 {json_path}")
    render_skeleton(args.name, chart, args.out)


if __name__ == "__main__":
    main()
