#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻排盘引擎 — BFFT v7.15（六爻平行模块，前后端分离：本文件为后端）。

来源与许可：
  - 64 卦表/卦宫/世应（guagong.py）：xiongdun8/liuyao，MIT License
  - 纳甲/六亲/六神/旬空/旺衰（装卦逻辑）：xiongdun8/liuyao，MIT License
    （本文件吸收其算法并以 BFFT 引擎替代固定节气日期表）
  - 格局检测（游魂/归魂/六冲/六合/三合三会/伏吟反吟）：思路参照
    Seanding1998/liuyao-frv（个人免费·商业授权许可证——本模块仅限个人/学习/
    研究使用；商业使用请联系原作者 Seanding 获取授权）
  - 月建/日辰/日干：BFFT pai_pan 引擎（精确节气，三重独立参照已验证），
    替代原 liuyao 的固定日期近似表（原表节气日期年际可偏 ±1 天）

六爻与四柱是**平行体系**：本模块只做排盘与格局标注，解卦结论一律按 BFFT
纪律输出（事前判据、禁伪精确、断语分级），不因换体系而放松。

用法:
  from liuyao.paipan import liuyao_calc
  r = liuyao_calc([1,2,3,1,2,1], "2026-08-16 23:00", tz=8, lon=116.4)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import scripts.liuyao.guagong as guagong  # noqa: E402
import scripts.liuyao.wangshuai as ws  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "pai_pan", os.path.join(_ROOT, "scripts", "pai_pan.py"))
_pp = importlib.util.module_from_spec(_spec)
sys.modules["pai_pan"] = _pp
_spec.loader.exec_module(_pp)

# 纳甲装支（宫 → 六爻地支，初爻至上爻）
HEXAGRAM_EARTHLY_BRANCH = {
    "乾宫": ["子", "寅", "辰", "午", "申", "戌"],
    "坤宫": ["未", "巳", "卯", "丑", "亥", "酉"],
    "震宫": ["子", "寅", "辰", "午", "申", "戌"],
    "巽宫": ["丑", "亥", "酉", "未", "巳", "卯"],
    "坎宫": ["寅", "辰", "午", "申", "戌", "子"],
    "离宫": ["卯", "丑", "亥", "酉", "未", "巳"],
    "艮宫": ["辰", "午", "申", "戌", "子", "寅"],
    "兑宫": ["巳", "卯", "丑", "亥", "酉", "未"],
}

BRANCH_WUXING = ws.BRANCH_WUXING
LIUSHOU = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
LIUSHEN_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
                 "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}

GONG_WUXING = {"乾宫": "金", "兑宫": "金", "离宫": "火", "震宫": "木",
               "巽宫": "木", "坎宫": "水", "艮宫": "土", "坤宫": "土"}

XUN_KONG = {
    "甲子": ["戌", "亥"], "甲戌": ["申", "酉"], "甲申": ["午", "未"],
    "甲午": ["辰", "巳"], "甲辰": ["寅", "卯"], "甲寅": ["子", "丑"],
}

# 六冲卦（八纯 + 天雷无妄 + 雷天大壮）与六合卦（标准十/八卦）
LIUCHONG_GUA = {"乾为天", "坤为地", "震为雷", "巽为风", "坎为水", "离为火",
                "艮为山", "兑为泽", "天雷无妄", "雷天大壮"}
LIUHE_GUA = {"天地否", "地天泰", "泽水困", "水泽节", "山火贲", "火山旅",
             "地雷复", "雷地豫"}

YAO_POS = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]


def _get_liuqin(wo: str, target: str) -> str:
    if not wo or not target:
        return ""
    if target == wo:
        return "兄弟"
    if ws.GENERATE_WUXING.get(target) == wo:
        return "父母"
    if ws.GENERATE_WUXING.get(wo) == target:
        return "子孙"
    if ws.CONQUER_WUXING.get(target) == wo:
        return "官鬼"
    if ws.CONQUER_WUXING.get(wo) == target:
        return "妻财"
    return ""


def _xunkong(day_gz: str) -> list[str]:
    """旬空：按日柱 60 甲子序号定旬（甲子..癸酉 等六旬）。"""
    n = _pp.idx60(day_gz[0], day_gz[1])
    for xun in ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"):
        s = _pp.idx60(xun[0], xun[1])
        if s <= n <= s + 9:
            return XUN_KONG[xun]
    return ["", ""]


def liuyao_calc(yao_codes: list[int], dt_s: str, tz: float = 8.0,
                lon: float | None = None, subject: str = "") -> dict:
    """六爻排盘。

    yao_codes: 6 位列表自初爻至上爻。1=少阴(--) 2=少阳(—) 3=老阳(—o 动) 4=老阴(--x 动)
    dt_s: 起卦时间 "YYYY-MM-DD HH:MM"
    """
    if len(yao_codes) != 6 or any(c not in (1, 2, 3, 4) for c in yao_codes):
        raise ValueError("yao_codes 需 6 位, 取值 1-4（自初爻至上爻）")
    dt = datetime.strptime(dt_s, "%Y-%m-%d %H:%M")

    # 月建/日辰/日干 —— BFFT 精确引擎
    chart = _pp.calc(dt, tz_hours=tz, lon=lon, day_boundary="zi",
                     calendar="auto", lucky_count=1, years_count=0)
    month_branch = chart["month_pillar"][1]
    day_gz = chart["day_pillar"]
    day_gan, day_zhi = day_gz[0], day_gz[1]

    # 本卦阴阳序列（阳=1 阴=0）
    yin_yang = [0 if c in (1, 4) else 1 for c in yao_codes]
    key = ",".join(str(x) for x in yin_yang)
    if key not in guagong.HEXAGRAMS:
        raise ValueError(f"无法识别卦象编码: {key}")
    info = guagong.HEXAGRAMS[key]
    gong = info["宫名"]
    branches = HEXAGRAM_EARTHLY_BRANCH[gong]
    gong_wx = GONG_WUXING[gong]

    # 动爻与变卦
    moving = [i for i, c in enumerate(yao_codes) if c in (3, 4)]
    changed_yy = list(yin_yang)
    for i in moving:
        changed_yy[i] = 1 - changed_yy[i]
    ckey = ",".join(str(x) for x in changed_yy)
    changed_info = guagong.HEXAGRAMS.get(ckey)
    changed_branches = None
    changed_gong = None
    if changed_info and moving:
        changed_gong = changed_info["宫名"]
        changed_branches = HEXAGRAM_EARTHLY_BRANCH[changed_gong]

    # 六亲 + 六神 + 旺衰
    liushou_start = LIUSHEN_START[day_gan]
    lines = []
    for i in range(6):
        wx = BRANCH_WUXING[branches[i]]
        strength = ws.batch_calculate_strength(
            yao_branches=branches, month_branch=month_branch, day_branch=day_zhi,
            changed_branches=changed_branches,
            is_moving_yaos=[c in (3, 4) for c in yao_codes])
        st = strength[i]
        status = list(st.get("status", []))
        if i in moving and changed_branches:
            cwx = BRANCH_WUXING[changed_branches[i]]
            if ws.GENERATE_WUXING.get(cwx) == wx:
                status.append("回头生")
            if ws.CONQUER_WUXING.get(cwx) == wx:
                status.append("回头克")
        lines.append({
            "pos": YAO_POS[i],
            "code": yao_codes[i],
            "symbol": "—" if yao_codes[i] in (2, 3) else "-- --",
            "moving": yao_codes[i] in (3, 4),
            "branch": branches[i],
            "wuxing": wx,
            "liuqin": _get_liuqin(gong_wx, wx),
            "liushen": LIUSHOU[(liushou_start + i) % 6],
            "changed_branch": changed_branches[i] if (i in moving and changed_branches) else None,
            "changed_liuqin": (_get_liuqin(GONG_WUXING[changed_gong],
                                           BRANCH_WUXING[changed_branches[i]])
                               if (i in moving and changed_branches and changed_gong) else None),
            "status": status,
            "score": st.get("score", 0),
        })

    # 格局（liuyao-frv 思路，自写实现）
    patterns = []
    if info["卦类型"] in ("游魂卦", "归魂卦"):
        patterns.append(info["卦类型"].replace("卦", ""))
    if info["卦名"] in LIUCHONG_GUA:
        patterns.append("六冲卦")
    if info["卦名"] in LIUHE_GUA:
        patterns.append("六合卦")
    if len(moving) == 1:
        patterns.append("独发")
    if len(moving) == 0:
        patterns.append("六静")
    # 三合局（动爻/变爻地支检测，吸收 liuyao-frv 三合三会思路）
    zhi_pool = [branches[i] for i in moving]
    for ju, label in _pp.ZHI_SANHE.items():
        if all(z in zhi_pool for z in ju):
            patterns.append(label.replace("局", ""))
    # 伏吟/反吟（本卦变卦同名/对冲——简化：本变卦名相同为伏吟）
    if changed_info and changed_info["卦名"] == info["卦名"]:
        patterns.append("伏吟")

    return {
        "version": "v7.15",
        "subject": subject,
        "cast_time": dt_s,
        "day_gz": day_gz,
        "month_branch": month_branch,
        "xunkong": _xunkong(day_gz),
        "original": {"name": info["卦名"], "gong": gong, "gong_wuxing": gong_wx,
                     "type": info["卦类型"], "shi": info["世爻索引"] + 1,
                     "ying": info["应爻索引"] + 1},
        "changed": ({"name": changed_info["卦名"], "gong": changed_gong,
                     "gong_wuxing": GONG_WUXING[changed_gong],
                     "type": changed_info["卦类型"]} if changed_info and moving else None),
        "lines": lines,
        "patterns": patterns,
        "moving_positions": [YAO_POS[i] for i in moving],
    }
