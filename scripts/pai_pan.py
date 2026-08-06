#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四柱八字排盘工具 (BaZi chart calculator) for the bazi-game-v3 skill.

Pure Python 3 stdlib, no external dependencies. Computes:
  - 年柱/月柱/日柱/时柱 (节气 boundary via a truncated solar-longitude model,
    ~5 minute accuracy for 1900-2100; suitable for BaZi practice)
  - 纳音、藏干、十神、十二长生、常用神煞、五行统计
  - 大运方向 (default: 阳年男/阴年女顺排; --gender female switches),
    起运时间 (3 天 = 1 年), 大运干支, 流年干支

Usage:
  python pai_pan.py "2024-05-23 10:00" [--name 鸣潮] [--tz 8]
                    [--gender male|female] [--lucky 10] [--years 8] [--json]

Notes:
  - Day changes at 23:00 (子初换日), a common 子平 convention.
  - Timezone default +08:00 (Asia/Shanghai). Pass UTC offset in hours.
  - For games/products use the 公测/上线 datetime; see SKILL.md for anchors.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
YANG_GAN = set("甲丙戊庚壬")

WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}

CANG = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

NAYIN_30 = [
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火", "涧下水",
    "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土", "霹雳火", "松柏木",
    "长流水", "砂中金", "山下火", "平地木", "壁上土", "金箔金", "覆灯火",
    "天河水", "大驿土", "钗钏金", "桑柘木", "大溪水", "沙中土", "天上火",
    "石榴木", "大海水",
]

# 节气黄经目标值: 0=小寒 ... 23=冬至 (太阳视黄经度数)
TERM_DEG = [285, 300, 315, 330, 345, 0, 15, 30, 45, 60, 75, 90, 105, 120,
            135, 150, 165, 180, 195, 210, 225, 240, 255, 270]
TERM_NAME = ["小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
             "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑",
             "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"]
# 月支锚定的"节": 立春->寅 ... 大雪->子; 小寒(次年)->丑
JIE_IDX = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 0]
JIE_ZHI = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]  # ZHI index

SHENGSHEN = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
             "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}
CHANGSHENG = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死",
              "墓", "绝", "胎", "养"]

# 天乙贵人: 日干 -> 贵人支 (ZHI index)
TIANYI = {"甲": [12, 7], "戊": [12, 7], "庚": [12, 7],
          "乙": [0, 8], "己": [0, 8],
          "丙": [11, 9], "丁": [11, 9],
          "壬": [3, 5], "癸": [3, 5],
          "辛": [1, 6]}
LU = {"甲": 2, "乙": 3, "丙": 5, "丁": 6, "戊": 5, "己": 6,
      "庚": 8, "辛": 9, "壬": 11, "癸": 0}
WENCHANG = {"甲": 5, "乙": 6, "丙": 8, "丁": 9, "戊": 8, "己": 9,
            "庚": 11, "辛": 0, "壬": 2, "癸": 3}
YANGREN = {"甲": 3, "丙": 6, "戊": 6, "庚": 9, "壬": 0}
QUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}

# 三合局: 以支的"局首"映射 桃花/驿马/将星/华盖/劫煞/亡神
JU = {"申子辰": 0, "巳酉丑": 1, "寅午戌": 2, "亥卯未": 3}
TAOHUA = {0: 9, 1: 6, 2: 3, 3: 0}       # 申子辰->酉 ...
YIMA = {0: 2, 1: 11, 2: 8, 3: 5}        # 申子辰->寅 ...
JIANGXING = {0: 0, 1: 9, 2: 6, 3: 3}    # 申子辰->子 ...
HUAGAI = {0: 4, 1: 1, 2: 10, 3: 7}      # 申子辰->辰 ...
JIESHA = {0: 5, 1: 2, 2: 11, 3: 8}      # 申子辰->巳 ...
WANGSHEN = {0: 11, 1: 8, 2: 5, 3: 2}    # 申子辰->亥 ...

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def wuxing(gan_or_zhi: str) -> str:
    return WUXING[gan_or_zhi]


def is_yang(gan: str) -> bool:
    return gan in YANG_GAN


def idx60(gan: str, zhi: str) -> int:
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for n in range(60):
        if n % 10 == gi and n % 12 == zi:
            return n
    raise ValueError(f"invalid pillar {gan}{zhi}")


def shishen(day_gan: str, other_gan: str) -> str:
    """十神 of other_gan relative to day_gan (天干)."""
    if other_gan == day_gan:
        return "比肩"
    d, o = wuxing(day_gan), wuxing(other_gan)
    same_parity = is_yang(day_gan) == is_yang(other_gan)
    if o == d:
        return "劫财"
    if SHENG[d] == o:  # 我生
        return "食神" if same_parity else "伤官"
    if KE[d] == o:  # 我克
        return "偏财" if same_parity else "正财"
    if SHENG[o] == d:  # 生我
        return "偏印" if same_parity else "正印"
    # 克我
    return "七杀" if same_parity else "正官"


def changsheng_pos(day_gan: str, zhi: str) -> str:
    sheng = SHENGSHEN[day_gan]
    si, mi = ZHI.index(sheng), ZHI.index(zhi)
    offset = (mi - si) % 12 if is_yang(day_gan) else (si - mi) % 12
    return CHANGSHENG[offset]


def jd_from_gregorian(y: int, m: int, d: int, h: float = 0.0) -> float:
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return (math.floor(365.25 * (y + 4716)) +
            math.floor(30.6001 * (m + 1)) + d + b - 1524.5 + h / 24.0)


def solar_longitude(jd: float) -> float:
    """Low-precision apparent solar longitude (Meeus), degrees [0,360)."""
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m) +
         (0.019993 - 0.000101 * t) * math.sin(2 * m) +
         0.000289 * math.sin(3 * m))
    omega = math.radians(125.04 - 1934.136 * t)
    return (l0 + c - 0.00569 - 0.00478 * math.sin(omega)) % 360.0


def jd_to_gregorian(jd: float):
    jd += 0.5
    z = int(jd)
    f = jd - z
    a = z
    if z >= 2299161:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - int(alpha / 4)
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    hh = int((day - int(day)) * 24)
    mm = int(((day - int(day)) * 24 - hh) * 60)
    return year, month, int(day), hh, mm


def term_utc(year: int, idx: int) -> float:
    """UTC Julian day when solar longitude crosses TERM_DEG[idx]."""
    target = TERM_DEG[idx]
    t0 = jd_from_gregorian(year, 1, 6) + idx * 15.2184

    def f(t: float) -> float:
        return ((solar_longitude(t) - target + 180.0) % 360.0) - 180.0

    lo, hi = t0 - 1.0, t0 + 1.0
    for _ in range(3):
        if f(lo) * f(hi) <= 0:
            break
        lo -= 1.0
        hi += 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def term_local(year: int, idx: int, tz_hours: float) -> datetime:
    jd = term_utc(year, idx) + tz_hours / 24.0
    y, m, d, hh, mm = jd_to_gregorian(jd)
    return datetime(y, m, d, hh, mm)


def jie_list(year: int, tz_hours: float):
    """All 12 节 (月令边界) for the given calendar year, local time."""
    out = []
    for idx in JIE_IDX:
        # JIE_IDX 0 (小寒) belongs to the NEXT year in month-cycle terms
        yy = year + 1 if idx == 0 else year
        out.append((TERM_NAME[idx], idx, term_local(yy, idx, tz_hours)))
    return out


def pillar60(n: int):
    return GAN[n % 10] + ZHI[n % 12]


def add_months(dt: datetime, months: float) -> datetime:
    whole = int(months)
    frac_days = (months - whole) * 30.0
    m = dt.month - 1 + whole
    y = dt.year + m // 12
    m = m % 12 + 1
    day = min(dt.day, 28)
    return datetime(y, m, day) + timedelta(days=frac_days)


def format_delta(days: float) -> str:
    years = int(days // 3)
    rem_days = days - years * 3
    months = int(rem_days * 4)
    return f"{years}年{months}个月"


def calc(dt: datetime, tz_hours: float = 8.0, gender: str = "male",
         lucky_count: int = 10, years_count: int = 8) -> dict:
    birth = dt
    # ---- 年柱 (立春为界) ----
    lichun = term_local(birth.year, 2, tz_hours)
    gy = birth.year if birth >= lichun else birth.year - 1
    year_gan, year_zhi = GAN[(gy - 4) % 10], ZHI[(gy - 4) % 12]

    # ---- 月柱 (12 节为界) ----
    jies = jie_list(birth.year - 1, tz_hours) + jie_list(birth.year, tz_hours)
    jies.sort(key=lambda x: x[2])
    cur = None
    for name, idx, t in jies:
        if t <= birth:
            cur = (name, idx, t)
    assert cur is not None
    _, cur_idx, _ = cur
    month_zhi_i = JIE_ZHI[JIE_IDX.index(cur_idx)]
    month_zhi = ZHI[month_zhi_i]
    first = {"甲": 2, "乙": 4, "丙": 6, "丁": 8, "戊": 0,
             "己": 2, "庚": 4, "辛": 6, "壬": 8, "癸": 0}[year_gan]
    month_gan = GAN[(first + (month_zhi_i - 2) % 12) % 10]

    # ---- 日柱 (2000-01-01 = 戊午; 23:00 换日) ----
    days_since = (birth.date() - datetime(2000, 1, 1).date()).days
    day_n = (54 + days_since) % 60
    if birth.hour >= 23:
        day_n = (day_n + 1) % 60
    day_gan, day_zhi = GAN[day_n % 10], ZHI[day_n % 12]

    # ---- 时柱 (五鼠遁) ----
    hour_zhi_i = ((birth.hour + 1) // 2) % 12
    first_hour = {"甲": 0, "乙": 2, "丙": 4, "丁": 6, "戊": 8,
                  "己": 0, "庚": 2, "辛": 4, "壬": 6, "癸": 8}[day_gan]
    hour_gan = GAN[(first_hour + hour_zhi_i) % 10]
    hour_zhi = ZHI[hour_zhi_i]

    pillars = [
        {"label": "年柱", "gan": year_gan, "zhi": year_zhi},
        {"label": "月柱", "gan": month_gan, "zhi": month_zhi},
        {"label": "日柱", "gan": day_gan, "zhi": day_zhi},
        {"label": "时柱", "gan": hour_gan, "zhi": hour_zhi},
    ]
    for p in pillars:
        n = idx60(p["gan"], p["zhi"])
        p["nayin"] = NAYIN_30[n // 2]
        p["canggan"] = CANG[p["zhi"]]
        p["shishen_gan"] = shishen(day_gan, p["gan"]) if p["label"] != "日柱" else "日主"
        p["shishen_cang"] = [shishen(day_gan, g) for g in p["canggan"]]

    # ---- 十二长生 (日主对月支/日支/时支) ----
    changsheng = {
        "月支": changsheng_pos(day_gan, month_zhi),
        "日支": changsheng_pos(day_gan, day_zhi),
        "时支": changsheng_pos(day_gan, ZHI[hour_zhi_i]),
    }

    # ---- 五行统计 ----
    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for p in pillars:
        counts[wuxing(p["gan"])] += 1
        for g in p["canggan"]:
            counts[wuxing(g)] += 1

    # ---- 神煞 (以日干/日支为主; 天乙贵人另注年干) ----
    shensha = {}
    for p in pillars:
        tags = []
        if ZHI.index(p["zhi"]) in TIANYI.get(day_gan, []):
            tags.append("天乙贵人(日)")
        if ZHI.index(p["zhi"]) in TIANYI.get(year_gan, []):
            tags.append("天乙贵人(年)")
        if p["label"] != "日柱" and p["zhi"] == ZHI[LU[day_gan]]:
            tags.append("禄")
        if p["zhi"] == ZHI[WENCHANG[day_gan]]:
            tags.append("文昌")
        if day_gan in YANGREN and p["zhi"] == ZHI[YANGREN[day_gan]]:
            tags.append("羊刃")
        if p["label"] == "日柱" and (p["gan"] + p["zhi"]) in QUIGANG:
            tags.append("魁罡")
        for zhi_key, table in (("日支", None), ("年支", None)):
            pass
        # 三合类神煞: 以日支与年支分别查
        for base_label, base_zhi in (("日支", day_zhi), ("年支", year_zhi)):
            for members, j in JU.items():
                if base_zhi in members:
                    if p["zhi"] == ZHI[TAOHUA[j]]:
                        tags.append(f"桃花({base_label})")
                    if p["zhi"] == ZHI[YIMA[j]]:
                        tags.append(f"驿马({base_label})")
                    if p["zhi"] == ZHI[JIANGXING[j]]:
                        tags.append(f"将星({base_label})")
                    if p["zhi"] == ZHI[HUAGAI[j]]:
                        tags.append(f"华盖({base_label})")
                    if p["zhi"] == ZHI[JIESHA[j]]:
                        tags.append(f"劫煞({base_label})")
                    if p["zhi"] == ZHI[WANGSHEN[j]]:
                        tags.append(f"亡神({base_label})")
        if tags:
            shensha[p["label"]] = list(dict.fromkeys(tags))

    # ---- 大运 ----
    yang_year = is_yang(year_gan)
    forward = (yang_year and gender == "male") or (not yang_year and gender == "female")
    month_n = idx60(month_gan, month_zhi)
    jies_sorted = sorted(jie_list(birth.year - 1, tz_hours) +
                         jie_list(birth.year, tz_hours) +
                         jie_list(birth.year + 1, tz_hours), key=lambda x: x[2])
    if forward:
        anchor = next(t for _, _, t in jies_sorted if t > birth)
    else:
        anchor = max(t for _, _, t in jies_sorted if t < birth)
    gap_days = abs((anchor - birth).total_seconds()) / 86400.0
    jiao_time = add_months(birth, gap_days * 4.0)
    step = 1 if forward else -1
    lucky = []
    for k in range(lucky_count):
        n = (month_n + step * (k + 1)) % 60
        start = add_months(jiao_time, k * 120)
        lucky.append({"ganzhi": pillar60(n), "start": start.strftime("%Y-%m"),
                      "age": round(gap_days / 3.0 + k * 10, 1)})

    # ---- 流年 ----
    liunian = []
    for y in range(birth.year, birth.year + years_count + 1):
        liunian.append({
            "year": y,
            "ganzhi": GAN[(y - 4) % 10] + ZHI[(y - 4) % 12],
        })

    return {
        "input": birth.strftime("%Y-%m-%d %H:%M"),
        "tz_hours": tz_hours,
        "gender": gender,
        "year_pillar": year_gan + year_zhi,
        "month_pillar": month_gan + month_zhi,
        "day_pillar": day_gan + day_zhi,
        "hour_pillar": hour_gan + hour_zhi,
        "day_master": day_gan,
        "pillars": pillars,
        "changsheng": changsheng,
        "wuxing_counts": counts,
        "shensha": shensha,
        "dayun_direction": "顺排" if forward else "逆排",
        "jiao_time": jiao_time.strftime("%Y-%m-%d"),
        "jiao_age": format_delta(gap_days),
        "lucky": lucky,
        "liunian": liunian,
    }


def render(result: dict) -> str:
    lines = []
    lines.append(f"输入: {result['input']} (UTC{result['tz_hours']:+g}) 性别设定: {result['gender']}")
    lines.append(f"四柱: {result['year_pillar']} {result['month_pillar']} {result['day_pillar']} {result['hour_pillar']}")
    nayin = " ".join(p["nayin"] for p in result["pillars"])
    lines.append(f"纳音: {nayin}")
    dm = result['day_master']
    lines.append(f"日主: {dm}{wuxing(dm)} ({'阳' if is_yang(dm) else '阴'})")
    lines.append("")
    for p in result["pillars"]:
        cang = " ".join(f"{g}({s})" for g, s in zip(p["canggan"], p["shishen_cang"]))
        lines.append(f"{p['label']} {p['gan']}{p['zhi']}: 干={p['shishen_gan']} 藏干={cang}")
    lines.append("")
    lines.append("十二长生: " + " ".join(f"{k}={v}" for k, v in result["changsheng"].items()))
    lines.append("五行统计: " + " ".join(f"{k}{v}" for k, v in result["wuxing_counts"].items()))
    if result["shensha"]:
        lines.append("神煞: " + "; ".join(f"{k}:{','.join(v)}" for k, v in result["shensha"].items()))
    lines.append("")
    lines.append(f"大运: {result['dayun_direction']}  起运约 {result['jiao_age']} (交运 {result['jiao_time']})")
    for l in result["lucky"]:
        lines.append(f"  {l['ganzhi']}  起于 {l['start']} (约{l['age']}岁)")
    lines.append("")
    lines.append("流年: " + " ".join(f"{y} {g}" for y, g in
                  [(x["year"], x["ganzhi"]) for x in result["liunian"]]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="四柱八字排盘 (bazi-game-v3)")
    ap.add_argument("datetime", help="本地时间, e.g. 2024-05-23 10:00")
    ap.add_argument("--name", default="")
    ap.add_argument("--tz", type=float, default=8.0, help="UTC 偏移小时, 默认 8")
    ap.add_argument("--gender", choices=["male", "female"], default="male",
                    help="大运顺逆用性别, 游戏/产品默认 male (阳男顺排)")
    ap.add_argument("--lucky", type=int, default=10)
    ap.add_argument("--years", type=int, default=8)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()
    dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    result = calc(dt, tz_hours=args.tz, gender=args.gender,
                  lucky_count=args.lucky, years_count=args.years)
    if args.name:
        result["name"] = args.name
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.name:
            print(f"名称: {args.name}")
        print(render(result))


if __name__ == "__main__":
    main()
