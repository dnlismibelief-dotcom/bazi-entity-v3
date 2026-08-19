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
# 三合局（用于流年/大运与原局成局、开库的应期判断）
SAN_HE = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}

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


def _roots_of(day_gan: str, pillars: list[dict]) -> tuple[int, int]:
    """日主根气：本气藏干=强根，余气=弱根（与 classics_extra 同口径）。"""
    d_wx = ce.WX[day_gan]
    strong = weak = 0
    for p in pillars:
        cang = p.get("canggan", ce.CANG[p["zhi"]])
        for i, g in enumerate(cang):
            g_wx = ce.WX[g]
            if g_wx == d_wx or ce.SHENG[g_wx] == d_wx:
                if i == 0:
                    strong += 1
                else:
                    weak += 1
    return strong, weak


def _strength_hint(day_gan: str, pillars: list[dict], tally: dict) -> str:
    """日主强弱提示：得令/根气/党众三要素，输出事实+倾向（不臆断）。"""
    d_wx = ce.WX[day_gan]
    month_zhi = pillars[1]["zhi"]
    month_wx = ce.WX[ce.CANG[month_zhi][0]]
    ling = "生扶" if (month_wx == d_wx or ce.SHENG[month_wx] == d_wx) else "克泄耗"
    strong, weak = _roots_of(day_gan, pillars)
    support = tally["比劫"] + tally["印"]
    drain = tally["财"] + tally["官杀"] + tally["食伤"]
    if ling == "生扶" and (strong >= 1 or support >= drain):
        verdict = "身强"
    elif ling != "生扶" and strong == 0 and drain > support:
        verdict = "身弱"
    else:
        verdict = "中和"
    return (f"日主{day_gan}: 月令{month_zhi}{ling}, 根{strong}强{weak}弱, "
            f"比印{support} vs 财官食伤{drain} → {verdict}")


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


def _wealth_clue(day_gan: str, pillars: list[dict], tally: dict,
                 question: str = "", verbose: bool = True) -> str:
    cai = [g for p in pillars for g in [p["gan"]] + p["canggan"]
           if ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财"]
    bijie = tally["比劫"]
    shishang = tally["食伤"]
    guansha = tally["官杀"]
    # 财星所在宫位（透干优先，藏干记宫）
    positions = []
    cai_gans = []
    for i, p in enumerate(pillars):
        label = ["年", "月", "日", "时"][i]
        for g in [p["gan"]] + p["canggan"]:
            if ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财":
                positions.append(label + ("透" if g == p["gan"] else "藏"))
                if g == p["gan"]:
                    cai_gans.append(g)
                break
    # 财库：财星五行对应的库支是否入命局、原局是否已冲库
    cai_wx = ce.WX[cai[0]] if cai else ""
    ku = {"木": "未", "火": "戌", "土": "戌", "金": "丑", "水": "辰"}.get(cai_wx, "")
    ku_zhi = [p["zhi"] for p in pillars]
    ku_hit = ""
    if ku and ku in ku_zhi:
        chong_ku = [z for z in ku_zhi if frozenset((ku, z)) in ce.CHONG_PAIRS]
        if chong_ku:
            ku_hit = f"财库{ku}入局且被{chong_ku[0]}冲开(财库已开)"
        else:
            ku_hit = f"财库{ku}入局未冲(财入库, 岁运逢冲方开)"
    # 财星明暗：透干=明财易露，全藏=暗财不显
    if cai_gans:
        mingan = f"财透干({'/'.join(cai_gans)}明财易露)"
    elif cai:
        mingan = "财全藏支(暗财不显, 不善露财)"
    else:
        mingan = "财星不透不藏"
    if not verbose:
        # 完整判据里的精简版：只给事实，不做身财论断，避免干扰非财运类题目
        return (f"财星{len(cai)}见" + (f"({'/'.join(cai)})" if cai else "(不透不藏)") +
                f"，宫位{''.join(positions) or '无'}" +
                (f"，{ku_hit}" if ku_hit else "") +
                f"，比劫{bijie}见" +
                (f"，比劫重(夺财)" if bijie >= 4 and tally["财"] >= 1 else "") +
                (f"，食伤{shishang}生财(有源)" if shishang >= 2 and tally["财"] >= 1 else ""))
    # 身财匹配与夺财/通关（子平常法；只认透干/旺众，不再给互相打架的并列吉凶）
    strength = _strength_hint(day_gan, pillars, tally)
    verdict = strength.split("→ ")[-1]
    bijie_other = max(0, bijie - 1)  # tally 含日主本身，夺财比劫看"他人"
    shi_gans = [p["gan"] for p in pillars if p["gan"] != day_gan]
    shishang_vis = any(ce.SHI_GROUP[ce._shishen(day_gan, g)] == "食伤" for g in shi_gans)
    guansha_vis = any(ce.SHI_GROUP[ce._shishen(day_gan, g)] == "官杀" for g in shi_gans)
    bijie_vis = any(ce.SHI_GROUP[ce._shishen(day_gan, g)] == "比劫" for g in shi_gans)
    relations = []
    if verdict == "身强" and tally["财"] >= 3:
        relations.append("身强能任财, 财旺为福" + ("(明财透干, 财运畅顺)" if cai_gans else ""))
    elif verdict == "身强":
        relations.append("身强财浅, 行财运食伤运方发")
    elif verdict == "身弱" and tally["财"] >= 3:
        relations.append("财多身弱(富屋贫人), 财来财去难守")
    elif verdict == "身弱":
        relations.append("身弱财为耗身之物, 财运平平")
    if bijie_other >= 3 and tally["财"] >= 1 and (bijie_vis or bijie_other >= 5):
        if shishang >= 3 or shishang_vis:
            relations.append("比劫众夺财但有食伤通关(技艺生财)")
        else:
            relations.append("比劫众夺财无通关(财被分夺/难聚)")
    if (not cai_gans and bijie_other >= 2 and tally["财"] >= 1
            and shishang < 3 and not shishang_vis):
        relations.append("财藏不显而比劫众(财难自掌, 易由人代管)")
    if guansha_vis and bijie_other >= 2 and verdict != "身弱":
        relations.append("官杀透干制劫护财")
    if any(p.endswith("时透") or p.endswith("时藏") for p in positions) and \
            re.search(r"房产|田宅|置业|公寓|屋|物业|住", question or ""):
        relations.append(f"财入时柱田宅宫(利房产, 财星{len(cai)}见可参房产之数)")
    return (f"财星{len(cai)}见" + (f"({'/'.join(cai)})" if cai else "") +
            f"，宫位{''.join(positions) or '无'}" +
            (f"，{ku_hit}" if ku_hit else "") +
            f"，{mingan}，比劫{bijie}见、食伤{shishang}、官杀{guansha}" +
            (f"，{';'.join(relations)}" if relations else "") +
            f"，{strength}")


def _study_clue(r: dict, day_gan: str, pillars: list[dict], tally: dict) -> str:
    yin_gans = [p["gan"] for p in pillars
                if ce.SHI_GROUP[ce._shishen(day_gan, p["gan"])] == "印"]
    yin_all = tally["印"]
    cai_all = tally["财"]
    shishang = tally["食伤"]
    guan = tally["官杀"]
    month_zhi = pillars[1]["zhi"]
    month_shi = ce._shishen(day_gan, ce.CANG[month_zhi][0])
    month_group = ce.SHI_GROUP[month_shi]
    # 金白水清（滴天髓）：金水两旺而清，主聪明清贵、利高学历（优先于印星明暗的常规读数）
    cnt = _counts_of(r, pillars)
    d_wx = ce.WX[day_gan]
    qz = ce.qingzhuo_check(day_gan, pillars)
    jbqs = qz.get("grade") == "清" and (
        (d_wx == "水" and cnt.get("金", 0) >= 2 and cnt.get("水", 0) >= cnt.get("金", 0)) or
        (d_wx == "金" and cnt.get("水", 0) >= 3 and cnt.get("金", 0) >= 4))
    parts = []
    # 印星明暗与数量（不再把"藏印"夸成"印旺"；金白水清时不因印藏而压学历）
    if yin_gans:
        parts.append(f"印{yin_all}见且透({'/'.join(yin_gans)})")
    elif yin_all:
        parts.append(f"印{yin_all}见全藏支")
    else:
        parts.append("印星全无")
    if jbqs:
        parts.append("金白水清(清贵聪明, 学历上限高, 可至博士)")
    # 月令是否印格（读书根基看月令印星当不当令）
    if month_group == "印":
        parts.append(f"月令印格({month_zhi})")
    # 财坏印：量化对比；印透=有救（专科/中专），印藏=止于中学
    cai_bad = cai_all >= 3 and yin_all >= 1
    if cai_all >= 3 and yin_all >= 1 and cai_all >= 2 * yin_all:
        if yin_gans:
            parts.append(f"财众坏印但印透有救(财{cai_all} vs 印{yin_all}, 学历受压制, 多在专科/中专)")
        else:
            parts.append(f"财众坏印且印藏(财{cai_all} vs 印{yin_all}, 学历止于中学/高中)")
    elif cai_bad and cai_all > yin_all:
        parts.append(f"财重坏印(财{cai_all} vs 印{yin_all}, 读书有阻, 易中途变卦/退学)")
    elif cai_bad and cai_all == yin_all:
        parts.append(f"财印相战两停(财{cai_all} vs 印{yin_all}, 学业有波动但根基未断)")
    elif cai_bad:
        parts.append(f"财来扰印(财{cai_all} vs 印{yin_all}, 印仍有力但学业受扰)")
    elif yin_gans and yin_all >= 2:
        parts.append("印透有气(读书有根底)")
    elif yin_gans:
        parts.append("印透单薄(学历中等)")
    elif yin_all and not jbqs:
        parts.append("印藏不显(学历中等偏下, 高中/专科)")
    # 真神不照（本项目判据）：印星再漂亮，格局困顿时学历上限也有限。
    # 但财坏印/金白水清已有明确读数，避免信号互相打架。
    zj = ce.zhenjia_check(month_zhi, pillars)
    if (not cai_bad and not jbqs and
            ("提纲不照" in zj.get("read", "") or "困顿" in zj.get("read", ""))):
        parts.append("真神不照(格局困顿, 学历上限有限)")
    # 食伤泄秀：有印制约才算"聪明可用"，无印则心散
    if shishang >= 3:
        parts.append("食伤泄秀" + ("有印制约(聪明可用)" if yin_all >= 1 else "无印(聪明但心散)"))
    # 官印相生只在印透且未遭财坏印时成立（财坏印优先，不并列吉凶）
    if guan >= 1 and yin_gans and not cai_bad:
        parts.append(f"官杀{guan}见, 官印相生(功名结构)")
    parts.append(_strength_hint(day_gan, pillars, tally))
    return "学业: " + "；".join(parts)


def _day_gz(r: dict) -> str:
    """日柱干支；缺失时安全返回空串（判据缺省，不让生成器崩）。"""
    if r.get("day_pillar"):
        return r["day_pillar"]
    pillars = r.get("pillars") or []
    if len(pillars) < 3:
        return ""
    return pillars[2].get("gan", "") + pillars[2].get("zhi", "")


JIAZI = [ce.GAN[i % 10] + ce.ZHI[i % 12] for i in range(60)]


def _luckies_extended(r: dict, n: int = 8) -> list[dict]:
    """大运序列按排运方向外推至 n 步（原 lucky 只有 4 步时，补出后续十年一运）。"""
    luck = [dict(lu) for lu in r.get("lucky", [])]
    if not luck:
        return []
    direction = 1 if r.get("dayun_direction") == "顺排" else -1
    last = luck[-1]
    gz = last.get("ganzhi", "")
    idx = ce._idx60(gz[0], gz[1]) if len(gz) == 2 else 0
    age = float(last.get("age", 0))
    sy0 = int(str(last.get("start", ""))[:4]) if last.get("start") else 0
    step = 1
    while len(luck) < n:
        idx = (idx + direction) % 60
        age += 10
        luck.append({"ganzhi": JIAZI[idx], "age": age,
                     "start": f"{sy0 + 10 * step}-01-01" if sy0 else None})
        step += 1
    return luck


def _gz_shi(gz: str, day_gan: str) -> tuple[str, str]:
    """干支 → (天干十神, 地支本气十神)。"""
    g, z = gz[0], gz[1]
    return ce._shishen(day_gan, g), ce._shishen(day_gan, ce.CANG[z][0])


def _active_luck(r: dict, year: int) -> dict | None:
    """该流年落在哪一步大运（按起运年份；大运序列已外推）。"""
    luck = _luckies_extended(r)
    active = None
    for lu in luck:
        sy = lu.get("start")
        if not sy or len(str(sy)) < 4:
            continue
        if int(str(sy)[:4]) <= year:
            active = lu
        else:
            break
    return active


def _year_tags(r: dict, x: dict, day_gan: str, pillars: list[dict],
               tally: dict, day_gz: str, day_zhi: str, cai_wx: str, ku: str,
               cai_win: bool = False) -> str:
    """单流年压缩标签：十神属性 + 冲合 + 财库/枭神等应期特征。"""
    gz = x["ganzhi"]
    g, z = gz[0], gz[1]
    sg, sz = _gz_shi(gz, day_gan)
    gg, zg = ce.SHI_GROUP[sg], ce.SHI_GROUP[sz]
    parts = [f"{gz}: 干{sg}/支本气{sz}"]
    if gg == "比劫" and tally["财"] >= 1:
        parts.append("比劫透干(夺财之年)")
    if gg == "财":
        parts.append("财星透干(明财之年)")
    if zg == "财":
        parts.append("财星坐支(得财之年)")
    if sg == "偏印" or sz == "偏印":
        parts.append("偏印(枭)值年(玄学/宗教/灵异通灵/孤僻)")
    if gg == "官杀" or zg == "官杀":
        parts.append("官杀值年(压力/官非)")
    if gg == "食伤":
        parts.append("食伤值年(投资/变动)")
    rel = ce.suiyun_relation(gz, r.get("year_pillar", ""))
    if rel.get("read"):
        parts.append(f"对年柱{rel['read'][:18]}")
    if gz == day_gz:
        parts.append("与日柱伏吟(自身/婚姻多动)")
    else:
        dz = ce.suiyun_relation(gz, day_gz)
        if dz.get("read") and ("战" in dz["read"] or "冲" in dz["read"]):
            parts.append(f"对日柱: {dz['read'][:18]}")
    if day_zhi:
        pair = z + day_zhi
        if pair in XING_ZHI:
            parts.append(XING_ZHI[pair] + "(动夫妻宫)")
        if frozenset((z, day_zhi)) in ce.CHONG_PAIRS:
            parts.append(f"流年支{z}冲夫妻宫{day_zhi}")
        if pair in HE_ZHI:
            parts.append(HE_ZHI[pair] + "(动夫妻宫)")
    # 流年支 vs 年月时柱（冲合刑，标动哪一柱）
    for i, p in enumerate(pillars):
        if i == 2:
            continue
        label = ["年柱", "月柱", "时柱"][i if i < 2 else 2]
        pz = p["zhi"]
        if frozenset((z, pz)) in ce.CHONG_PAIRS:
            parts.append(f"流年支{z}冲{label}{pz}")
        else:
            pair = z + pz
            if pair in XING_ZHI:
                parts.append(XING_ZHI[pair] + f"(动{label})")
            elif pair in HE_ZHI:
                parts.append(HE_ZHI[pair] + f"(合{label})")
    # 财库与三合/半合（流年支为财星支、冲合财库、成财局）
    zhi_list = [p["zhi"] for p in pillars]
    if ku:
        if z == ku:
            parts.append("流年值财库(财动)")
        if frozenset((z, ku)) in ce.CHONG_PAIRS:
            verdict = _strength_hint(day_gan, pillars, tally).split("→ ")[-1]
            parts.append(f"流年支{z}冲财库{ku}({'身弱冲库财动反散' if verdict == '身弱' else '开库得财'})")
        pair = z + ku
        if pair in HE_ZHI:
            parts.append(HE_ZHI[pair] + "(合财库)")
    for combo, wx in SAN_HE.items():
        if z not in combo:
            continue
        present = [m for m in combo if m in zhi_list and m != z]
        if len(present) == 2:
            parts.append(f"流年{z}与{''.join(present)}三合{wx}局")
        elif len(present) == 1 and (wx == cai_wx or present[0] == ku):
            parts.append(f"流年{z}与{present[0]}半合{wx}局" +
                         ("(财局得财)" if cai_win else "(财气动)"))
    active = _active_luck(r, int(x["year"]))
    if active:
        asg, asz = _gz_shi(active["ganzhi"], day_gan)
        parts.append(f"值大运{active['ganzhi']}({asg}/{asz})")
        if active["ganzhi"] == gz:
            parts.append("岁运并临")
    return "；".join(parts[:8])


def _year_clue(r: dict, question: str, options: list | None = None) -> str:
    q_years = set(re.findall(r"(19\d\d|20\d\d)", question or ""))
    # 只有"应期类"题目才把选项里的年份当候选流年：选项几乎全是年份，
    # 或题目明确问哪年/何时/发生——否则选项里的年份只是叙事，注入会变成噪声。
    q_timing = bool(re.search(r"哪年|哪一年|何时|何年|什么时候|发生|至今", question or ""))
    # "2020/2021年的经济状况"这类虽无"哪年"，但年份就是应期本身；
    # 排除"丙戌大运的财政状况(2009--2018)"这种年份只是背景的题。
    q_status = bool(re.search(r"状况|境况", question or "")) and "大运" not in (question or "")
    pure_years = sum(1 for o in options or []
                     if re.fullmatch(r"\s*(?:19|20)\d{2}(?:年)?\s*", o.get("text", "").strip()))
    if q_timing and q_years:
        years = sorted(q_years, key=int)
    elif (q_timing or q_status) and pure_years >= max(2, len(options or []) * 0.5):
        years = sorted(set(re.findall(r"(19\d\d|20\d\d)",
                                      " ".join(o.get("text", "") for o in options or []))), key=int)
    elif q_timing:
        years = []
    elif q_status and q_years:
        years = sorted(q_years, key=int)
    else:
        # 叙事题（如"某大运财政状况(2009--2018)"）：年份只是背景，不做流年应期
        years = []
    clues = []
    day_gan = r.get("day_master", "")
    pillars = _pillars_of(r)
    tally = _shishen_tally(day_gan, pillars)
    day_gz = _day_gz(r)
    day_zhi = day_gz[1:] if len(day_gz) == 2 else ""
    cai = [g for p in pillars for g in [p["gan"]] + p["canggan"]
           if ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财"]
    cai_wx = ce.WX[cai[0]] if cai else ""
    ku = {"木": "未", "火": "戌", "土": "戌", "金": "丑", "水": "辰"}.get(cai_wx, "")
    cai_win = bool(re.search(r"赚|发财|横发|得财|厚利|中奖|六合彩|买楼|买房|田宅|横财", question or ""))
    for y in years:
        x = next((x for x in r.get("liunian", []) if str(x.get("year")) == y), None)
        if x is None:
            # 盘面只带了 25 年流年，选项里的年份用六十甲子公式补算（不含起运之外的神煞）
            x = {"year": int(y), "ganzhi": JIAZI[(int(y) - 4) % 60]}
        clues.append(f"{y}年{_year_tags(r, x, day_gan, pillars, tally, day_gz, day_zhi, cai_wx, ku, cai_win)}")
    return "；".join(clues) if clues else ""


_AGE_RANGE_RE = re.compile(r"(\d{1,2})\s*(?:---|--|至|到|~|～|-)\s*(\d{1,2})\s*岁")


def _dayun_clue(r: dict, question: str, options: list | None, day_gan: str) -> str:
    """年龄区间类题（破财最重/田宅运等）→ 各区间对应的十年大运与特征。"""
    text = (question or "") + " " + " ".join(o.get("text", "") for o in options or [])
    ranges = []
    for lo, hi in _AGE_RANGE_RE.findall(text):
        pair = (int(lo), int(hi))
        if pair not in ranges:
            ranges.append(pair)
    if not ranges:
        return ""
    luck = _luckies_extended(r)
    pillars = _pillars_of(r)
    tally = _shishen_tally(day_gan, pillars)
    cai = [g for p in pillars for g in [p["gan"]] + p["canggan"]
           if ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财"]
    cai_wx = ce.WX[cai[0]] if cai else ""
    ku = {"木": "未", "火": "戌", "土": "戌", "金": "丑", "水": "辰"}.get(cai_wx, "")
    day_zhi = pillars[2]["zhi"]
    out = []
    for lo, hi in ranges:
        # 区间与各步大运的十年跨度求交集，跨运列出多步
        hits = []
        for lu in luck:
            a = float(lu.get("age", 0))
            if a < hi and a + 10 > lo:
                hits.append(lu)
        if not hits:
            continue
        segs = []
        verdict = _strength_hint(day_gan, pillars, tally).split("→ ")[-1]
        for active in hits:
            gz = active["ganzhi"]
            sg, sz = _gz_shi(gz, day_gan)
            gg, zg = ce.SHI_GROUP[sg], ce.SHI_GROUP[sz]
            tags = [f"大运{gz}({sg}/{sz})"]
            if gg == "比劫" and tally["财"] >= 1:
                tags.append("比劫帮身(身弱得助, 反利财)" if verdict == "身弱" else "比劫运夺财")
            if gg == "财" or zg == "财":
                tags.append("财运(财星当运)")
            else:
                cang_has_cai = any(ce.SHI_GROUP[ce._shishen(day_gan, g)] == "财"
                                   for g in ce.CANG[gz[1]])
                if cang_has_cai:
                    tags.append("大运支藏财星(财气入运)")
            if sg == "偏印" or sz == "偏印":
                tags.append("偏印运(玄学/孤僻)")
            if ku and frozenset((gz[1], ku)) in ce.CHONG_PAIRS:
                tags.append(f"大运支{gz[1]}冲财库{ku}({'身弱财库开反破财' if verdict == '身弱' else '开库得财'})")
            if day_zhi and frozenset((gz[1], day_zhi)) in ce.CHONG_PAIRS:
                tags.append(f"冲夫妻宫{day_zhi}(家宅变动)")
            segs.append("，".join(tags))
        out.append(f"{lo}-{hi}岁→" + "；".join(segs))
    return "；".join(out)


def focused_clue(r: dict, gender: str, category: str, question: str,
                 options: list | None = None) -> str:
    """按题目类别给最强 2-4 条线索（放在完整判据之前）。"""
    pillars = _pillars_of(r)
    day_gan = r.get("day_master")
    tally = _shishen_tally(day_gan, pillars)
    out = []
    if category in ("婚姻", "家庭"):
        out.append(_marriage_clue(day_gan, pillars, gender, tally))
        yc = _year_clue(r, question, None)
        if yc:
            out.append("应期: " + yc)
    elif category == "财运":
        out.append(_wealth_clue(day_gan, pillars, tally, question))
        if "父" in question:
            pian = [g for p in pillars for g in [p["gan"]] + p["canggan"]
                    if ce._shishen(day_gan, g) == "偏财"]
            yue_ben = ce.CANG[pillars[1]["zhi"]][0]
            nian_ben = ce.CANG[pillars[0]["zhi"]][0]
            if pian and ce._shishen(day_gan, yue_ben) == "偏财":
                out.append(f"父星偏财{len(pian)}见且得月令本气(父有根有财, 身家可期)")
            elif pian and ce._shishen(day_gan, nian_ben) == "偏财":
                out.append(f"父星偏财{len(pian)}见且坐年支本气(父有根有积蓄, 身家可期)")
            else:
                pian_vis = "透干" if any(ce._shishen(day_gan, p["gan"]) == "偏财" for p in pillars) else "藏支"
                out.append(f"父星偏财{len(pian)}见({pian_vis}, 父之财气以此参看)")
        dc = _dayun_clue(r, question, options, day_gan)
        if dc:
            out.append("大运区间: " + dc)
        yc = _year_clue(r, question, options)
        if yc:
            out.append("应期: " + yc)
    elif category == "学业":
        out.append(_study_clue(r, day_gan, pillars, tally))
        yc = _year_clue(r, question, None)
        if yc:
            out.append("应期: " + yc)
    elif category == "健康":
        cnt = _counts_of(r, pillars)
        weak = sorted(cnt.items(), key=lambda kv: kv[1])
        out.append(f"五行最弱: {weak[0][0]}{weak[0][1]}、{weak[1][0]}{weak[1][1]}；旺极而折、弱极而病，岁运冲旺克弱为应期")
        yc = _year_clue(r, question, None)
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
        dc = _dayun_clue(r, question, options, day_gan)
        if dc:
            out.append("大运区间: " + dc)
        yc = _year_clue(r, question, None)
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
    # 5. 婚姻 / 财星（最短板，重点给线索；完整判据用精简财星事实，详细身财论断只进财运聚焦）
    parts.append(_marriage_clue(day_gan, pillars, gender, tally))
    parts.append(_wealth_clue(day_gan, pillars, tally, verbose=False))
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
