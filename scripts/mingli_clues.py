#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 判据层（clues）生成器 — v7.19 优化：让 LLM 带着 BFFT 的规则读盘。

盲测包此前只给盘面数据（四柱/十神/大运），LLM 相当于裸猜；
本模块把 classics_extra 的 S 级判据函数与婚姻/财星/岁运线索
压缩成一段中文判据摘要，随包输出。

用法:
    from mingli_clues import build_clues
    clues = build_clues(pp.calc(...), gender="male", question="2009年发生何事？")
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
CE_PATH = os.path.join(ROOT, "classics_extra.py")
spec = importlib.util.spec_from_file_location("classics_extra", CE_PATH)
ce = importlib.util.module_from_spec(spec)
sys.modules["classics_extra"] = ce
spec.loader.exec_module(ce)

# 地支六合 / 三刑（clues 内联，与 classics_extra 无依赖）
HE_ZHI = {"子丑": "子丑合土", "丑子": "子丑合土", "寅亥": "寅亥合木", "亥寅": "寅亥合木",
          "卯戌": "卯戌合火", "戌卯": "卯戌合火", "辰酉": "辰酉合金", "酉辰": "辰酉合金",
          "巳申": "巳申合水", "申巳": "巳申合水", "午未": "午未合土", "未午": "午未合土"}
XING_ZHI = {"寅巳": "寅巳相刑", "巳申": "巳申相刑", "申寅": "寅申相刑",
            "丑戌": "丑戌相刑", "戌未": "戌未相刑", "未丑": "丑未相刑",
            "子卯": "子卯相刑", "辰辰": "辰自刑", "午午": "午自刑",
            "酉酉": "酉自刑", "亥亥": "亥自刑"}

SHI_TO_GE = {"官杀": "官杀格", "财": "财格", "印": "印格", "食伤": "食伤格", "比劫": "建禄/月劫"}


def _pillars_of(r: dict) -> list[dict]:
    """从 pai_pan 输出提取四柱（gan/zhi/canggan）。"""
    out = []
    for p in r.get("pillars", []):
        out.append({
            "gan": p.get("gan"),
            "zhi": p.get("zhi"),
            "canggan": list(p.get("canggan", [])),
        })
    return out


def _counts_of(r: dict, pillars: list[dict]) -> dict:
    """五行计数：优先 r['wuxing_counts']，否则自算（含藏干）。"""
    counts = {k: int(v) for k, v in (r.get("wuxing_counts") or {}).items()}
    if counts:
        return counts
    for p in pillars:
        counts[ce.WX[p["gan"]]] = counts.get(ce.WX[p["gan"]], 0) + 1
        for g in p["canggan"]:
            counts[ce.WX[g]] = counts.get(ce.WX[g], 0) + 1
    return counts


def _shishen_tally(day_gan: str, pillars: list[dict]) -> dict:
    tally = {"比劫": 0, "食伤": 0, "财": 0, "官杀": 0, "印": 0}
    for p in pillars:
        for g in [p["gan"]] + p["canggan"]:
            group = ce.SHI_GROUP[ce._shishen(day_gan, g)]
            tally[group] += 1
    return tally


def _marriage_clue(day_gan: str, pillars: list[dict], gender: str, tally: dict) -> str:
    day_zhi = pillars[2]["zhi"]
    other = [p["zhi"] for i, p in enumerate(pillars) if i != 2]
    relations = []
    for z in other:
        if frozenset((day_zhi, z)) in ce.CHONG_PAIRS:
            relations.append(f"日支{day_zhi}冲{z}")
        pair = day_zhi + z
        if pair in HE_ZHI:
            relations.append(HE_ZHI[pair])
        if pair in XING_ZHI:
            relations.append(XING_ZHI[pair])
    spouse = "财星(妻星)" if gender == "male" else "官杀(夫星)"
    spouse_count = tally["财"] if gender == "male" else tally["官杀"]
    spouse_vis = []
    for p in pillars:
        for g in [p["gan"]] + p["canggan"]:
            group = ce.SHI_GROUP[ce._shishen(day_gan, g)]
            if group == ("财" if gender == "male" else "官杀"):
                spouse_vis.append(g)
    return (f"夫妻宫日支{day_zhi}: " + ("、".join(relations) if relations else "无冲合刑") +
            f"; {spouse}共{spouse_count}见" + (f"，明现: {'/'.join(spouse_vis)}" if spouse_vis else "，不透不藏"))


def _wealth_clue(day_gan: str, pillars: list[dict], tally: dict) -> str:
    cai = [g for p in pillars for g in [p["gan"]] + p["canggan"]
           if ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财"]
    bijie = tally["比劫"]
    rob = "比劫重(夺财)" if bijie >= 4 and tally["财"] >= 1 else ""
    return f"财星{len(cai)}见" + (f"({'/'.join(cai)})" if cai else "(不透不藏)") + \
        f"，比劫{bijie}见" + (f"，{rob}" if rob else "")


def _year_clue(r: dict, question: str) -> str:
    years = re.findall(r"(19\d\d|20\d\d)\s*年", question or "")
    clues = []
    day_gz = r.get("day_pillar") or (r.get("pillars") or [])[2].get("gan") + (r.get("pillars") or [])[2].get("zhi")
    day_zhi = (r.get("pillars") or [])[2].get("zhi")
    for y in sorted(set(years)):
        for x in r.get("liunian", []):
            if str(x.get("year")) != y:
                continue
            parts = []
            # 流年 vs 年柱 / 日柱（伏吟反吟）
            rel = ce.suiyun_relation(x["ganzhi"], r["year_pillar"])
            if rel.get("read"):
                parts.append(f"与年柱{r['year_pillar']}{rel['read'][:24]}")
            if x["ganzhi"] == day_gz:
                parts.append(f"流年{x['ganzhi']}与日柱伏吟(本命重复, 自身/婚姻多动)")
            else:
                dz = ce.suiyun_relation(x["ganzhi"], day_gz)
                if dz.get("read") and ("战" in dz["read"] or "冲" in dz["read"]):
                    parts.append(f"流年{x['ganzhi']}对日柱{day_gz}: {dz['read'][:24]}")
            # 流年 vs 夫妻宫
            pair = x["ganzhi"][1] + day_zhi
            if pair in XING_ZHI:
                parts.append(XING_ZHI[pair] + "(动夫妻宫)")
            if frozenset((x["ganzhi"][1], day_zhi)) in ce.CHONG_PAIRS:
                parts.append(f"流年支{x['ganzhi'][1]}冲夫妻宫{day_zhi}")
            # 岁运并临（流年=大运）
            for lu in r.get("lucky", []):
                if lu.get("ganzhi") == x["ganzhi"]:
                    parts.append(f"岁运并临(流年=大运{x['ganzhi']})")
            clues.append(f"{y}年{x['ganzhi']}: " + "；".join(parts))
    return "；".join(clues) if clues else ""


def focused_clue(r: dict, gender: str, category: str, question: str) -> str:
    """按题目类别给最强 2-3 条线索（放在完整判据之前）。"""
    pillars = _pillars_of(r)
    day_gan = r.get("day_master")
    day_zhi = pillars[2]["zhi"]
    tally = _shishen_tally(day_gan, pillars)
    out = []
    if category in ("婚姻", "家庭"):
        out.append(_marriage_clue(day_gan, pillars, gender, tally))
        yc = _year_clue(r, question)
        if yc:
            out.append("应期: " + yc)
    elif category == "财运":
        out.append(_wealth_clue(day_gan, pillars, tally))
        yc = _year_clue(r, question)
        if yc:
            out.append("应期: " + yc)
    elif category == "健康":
        cnt = _counts_of(r, pillars)
        weak = sorted(cnt.items(), key=lambda kv: kv[1])
        out.append(f"五行最弱: {weak[0][0]}{weak[0][1]}、{weak[1][0]}{weak[1][1]}；旺极而折、弱极而病，岁运冲旺克弱为应期")
        yc = _year_clue(r, question)
        if yc:
            out.append("应期: " + yc)
    elif category == "性格":
        cnt = _counts_of(r, pillars)
        top = sorted(cnt.items(), key=lambda kv: -kv[1])[:2]
        out.append(f"五行主导: {top[0][0]}、{top[1][0]}")
        sf = ce.source_flow(cnt)
        out.append(f"源流: 源头{sf.get('source', '')} → 流经{'/'.join(sf.get('chain', []))} → 汇{sf.get('sink', '')}")
    elif category == "事业":
        month_zhi = pillars[1]["zhi"]
        month_shi = ce._shishen(day_gan, ce.CANG[month_zhi][0])
        out.append(f"月令用神: {SHI_TO_GE.get(ce.SHI_GROUP[month_shi], '杂格')}（{month_zhi}本气{ce.CANG[month_zhi][0]}）")
        yc = _year_clue(r, question)
        if yc:
            out.append("应期: " + yc)
    return "；".join(out)


def build_clues(r: dict, gender: str = "male", question: str = "") -> str:
    """输出一段紧凑中文判据摘要（供 LLM 做题时参考）。"""
    pillars = _pillars_of(r)
    day_gan = r.get("day_master")
    month_zhi = pillars[1]["zhi"]
    counts = _counts_of(r, pillars)
    tally = _shishen_tally(day_gan, pillars)

    parts = []
    # 1. 强弱源流
    sf = ce.source_flow(counts)
    parts.append(f"五行计数{counts}; 源流: 源头{'/'.join(sf.get('source', '').split()) or '无'} → 流经{'/'.join(sf.get('chain', [])) or '无'} → 汇{'/'.join(sf.get('sink', '').split()) or '无'}")
    # 2. 从化
    ch = ce.cong_hua_judge(day_gan, month_zhi, pillars, counts)
    parts.append(f"从化:{ch['verdict']}({ch['basis'][0][:60] if ch['basis'] else ''})")
    # 3. 清浊/众寡/真神
    qz = ce.qingzhuo_check(day_gan, pillars)
    zg = ce.zhonggua_read(day_gan, counts)
    zj = ce.zhenjia_check(month_zhi, pillars)
    parts.append(f"清浊:{qz.get('grade')}; 众寡:{zg.get('read', '')[:40]}; 真神:{zj.get('read', '')[:40]}")
    # 4. 月令格局与吉凶
    month_shi = ce._shishen(day_gan, ce.CANG[month_zhi][0])
    ge_group = ce.SHI_GROUP[month_shi]
    ge = SHI_TO_GE.get(ge_group, "杂格")
    jx = ce.jixiong_ge_check(day_gan, pillars, "官" if ge_group == "官杀" else
                             "财" if ge_group == "财" else "印" if ge_group == "印" else "食")
    parts.append(f"月令用神:{ge}(月支{month_zhi}本气{ce.CANG[month_zhi][0]}{month_shi}); 格局吉凶:{jx.get('read', '')[:60]}")
    # 5. 婚姻 / 财星（最短板，重点给线索）
    parts.append(_marriage_clue(day_gan, pillars, gender, tally))
    parts.append(_wealth_clue(day_gan, pillars, tally))
    # 6. 岁运应期（从题目里挖年份）
    yc = _year_clue(r, question)
    if yc:
        parts.append(f"流年: {yc}")

    return " | ".join(p for p in parts if p)


if __name__ == "__main__":
    # 自检：示例盘
    spec2 = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "pai_pan.py"))
    pp = importlib.util.module_from_spec(spec2)
    sys.modules["pai_pan"] = pp
    spec2.loader.exec_module(pp)
    from datetime import datetime
    r = pp.calc(datetime(1972, 1, 8, 12, 0), tz_hours=8, lon=None,
                gender="male", day_boundary="zi", lucky_count=4, years_count=25)
    print(build_clues(r, "male", "命主事业上的特色？"))
