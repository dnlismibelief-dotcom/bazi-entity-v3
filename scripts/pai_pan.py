#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四柱八字排盘 (BaZi chart calculator) — BFFT v5.

Pure Python 3 stdlib, no external dependencies.

v5 相对 v4 的变化
-----------------
修正:
  * 流年干支改为以立春分界（v4 直接用公历年，与年柱逻辑不一致，跨年初的流年会错一位）
  * add_months 不再把日期压到 28 日（v4 的 min(day,28) 会让起运/交运日期偏差最多 3 天）
  * 节气时刻保留到秒并四舍五入到分（v4 直接 int() 截断，最多少 1 分钟）
  * 加入 ΔT (TT-UT) 修正：solar_longitude 吃的是 TT，v4 当成 UT 用，节气时刻约偏 1 分钟
  * 删除神煞段里的空循环死代码

新增:
  * 真太阳时：--lon 经度修正 + 均时差 (equation of time)。八字时柱依真太阳时，
    同在东八区，乌鲁木齐(87.6E)与上海(121.5E)真太阳时相差约 2h16m，足以整根错时柱。
  * 中国夏令时 1986—1991 自动识别（该期间出生证明上的钟表时间快 1 小时）
  * --day-boundary {zi,midnight}: 换日流派可切换，并在输出中并列另一派日柱
    （SKILL.md 的 guardrail 要求门派分歧并列，不作独断）

Usage:
  python pai_pan.py "2024-05-23 10:00" [--name 鸣潮] [--tz 8] [--lon 121.5]
                    [--gender male|female] [--day-boundary zi|midnight]
                    [--dst auto|on|off] [--lucky 10] [--years 12] [--json]

Notes:
  * 时区默认 +08:00。给了 --lon 才做真太阳时修正；没给则按时区中央经线，
    并在输出中标注"未做经度修正"。
  * game/product/company 用公测/上线时刻当生辰，见 SKILL.md。
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

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

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

# 节气视黄经目标: 0=小寒(285°) ... 23=冬至(270°)
TERM_DEG = [285, 300, 315, 330, 345, 0, 15, 30, 45, 60, 75, 90, 105, 120,
            135, 150, 165, 180, 195, 210, 225, 240, 255, 270]
TERM_NAME = ["小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
             "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑",
             "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"]
# 定月令的 12 个"节": 立春->寅 ... 大雪->子, 小寒(次年)->丑
JIE_IDX = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 0]
JIE_ZHI = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]
LICHUN_IDX = 2

SHENGSHEN = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
             "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}
CHANGSHENG = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死",
              "墓", "绝", "胎", "养"]

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

JU = {"申子辰": 0, "巳酉丑": 1, "寅午戌": 2, "亥卯未": 3}
TAOHUA = {0: 9, 1: 6, 2: 3, 3: 0}
YIMA = {0: 2, 1: 11, 2: 8, 3: 5}
JIANGXING = {0: 0, 1: 9, 2: 6, 3: 3}
HUAGAI = {0: 4, 1: 1, 2: 10, 3: 7}
JIESHA = {0: 5, 1: 2, 2: 11, 3: 8}
WANGSHEN = {0: 11, 1: 8, 2: 5, 3: 2}

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 五虎遁(年上起月) / 五鼠遁(日上起时)
WUHU = {"甲": 2, "乙": 4, "丙": 6, "丁": 8, "戊": 0,
        "己": 2, "庚": 4, "辛": 6, "壬": 8, "癸": 0}
WUSHU = {"甲": 0, "乙": 2, "丙": 4, "丁": 6, "戊": 8,
         "己": 0, "庚": 2, "辛": 4, "壬": 6, "癸": 8}

# 中国夏令时 1986—1991（起止均为当地 02:00）。日期依据公开资料，
# 用于人盘时若逢此区间会给出提示；如有档案差异请以出生地记录为准。
CN_DST = [
    (datetime(1986, 5, 4, 2), datetime(1986, 9, 14, 2)),
    (datetime(1987, 4, 12, 2), datetime(1987, 9, 13, 2)),
    (datetime(1988, 4, 10, 2), datetime(1988, 9, 11, 2)),
    (datetime(1989, 4, 16, 2), datetime(1989, 9, 17, 2)),
    (datetime(1990, 4, 15, 2), datetime(1990, 9, 16, 2)),
    (datetime(1991, 4, 14, 2), datetime(1991, 9, 15, 2)),
]

DAY_ANCHOR = datetime(2000, 1, 1)   # 2000-01-01 为戊午日
DAY_ANCHOR_N = 54


# --------------------------------------------------------------------------
# 基础换算
# --------------------------------------------------------------------------

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


def pillar60(n: int) -> str:
    return GAN[n % 10] + ZHI[n % 12]


def shishen(day_gan: str, other_gan: str) -> str:
    """十神：other_gan 相对 day_gan。"""
    if other_gan == day_gan:
        return "比肩"
    d, o = wuxing(day_gan), wuxing(other_gan)
    same_parity = is_yang(day_gan) == is_yang(other_gan)
    if o == d:
        return "劫财"
    if SHENG[d] == o:
        return "食神" if same_parity else "伤官"
    if KE[d] == o:
        return "偏财" if same_parity else "正财"
    if SHENG[o] == d:
        return "偏印" if same_parity else "正印"
    return "七杀" if same_parity else "正官"


def changsheng_pos(day_gan: str, zhi: str) -> str:
    """十二长生（阳干顺行、阴干逆行）。"""
    sheng = SHENGSHEN[day_gan]
    si, mi = ZHI.index(sheng), ZHI.index(zhi)
    offset = (mi - si) % 12 if is_yang(day_gan) else (si - mi) % 12
    return CHANGSHENG[offset]


# --------------------------------------------------------------------------
# 天文：儒略日、太阳视黄经、黄赤交角、均时差、ΔT
# --------------------------------------------------------------------------

def jd_from_gregorian(y: int, m: int, d: float, h: float = 0.0) -> float:
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return (math.floor(365.25 * (y + 4716)) +
            math.floor(30.6001 * (m + 1)) + d + b - 1524.5 + h / 24.0)


def jd_to_datetime(jd: float) -> datetime:
    """儒略日 → datetime（秒级，四舍五入到秒）。"""
    jd += 0.5
    z = math.floor(jd)
    f = jd - z
    a = z
    if z >= 2299161:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    base = datetime(year, month, int(day))
    return base + timedelta(seconds=round(f * 86400.0))


def delta_t_seconds(year: float) -> float:
    """ΔT = TT - UT，秒。NASA/Espenak-Meeus 分段近似（1900—2150 足够）。"""
    if year < 1920:
        t = year - 1900
        return (-2.79 + 1.494119 * t - 0.0598939 * t ** 2 +
                0.0061966 * t ** 3 - 0.000197 * t ** 4)
    if year < 1941:
        t = year - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if year < 1961:
        t = year - 1950
        return 29.07 + 0.407 * t - t ** 2 / 233.0 + t ** 3 / 2547.0
    if year < 1986:
        t = year - 1975
        return 45.45 + 1.067 * t - t ** 2 / 260.0 - t ** 3 / 718.0
    if year < 2005:
        t = year - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3 +
                0.000651814 * t ** 4 + 0.00002373599 * t ** 5)
    if year < 2050:
        t = year - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    if year < 2150:
        u = (year - 1820) / 100.0
        return -20 + 32 * u ** 2 - 0.5628 * (2150 - year)
    u = (year - 1820) / 100.0
    return -20 + 32 * u ** 2


def solar_longitude(jd_tt: float) -> float:
    """太阳视黄经（度, [0,360)）。输入为 TT 儒略日。Meeus 低精度式。"""
    t = (jd_tt - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m) +
         (0.019993 - 0.000101 * t) * math.sin(2 * m) +
         0.000289 * math.sin(3 * m))
    omega = math.radians(125.04 - 1934.136 * t)
    return (l0 + c - 0.00569 - 0.00478 * math.sin(omega)) % 360.0


def mean_solar_longitude(jd_tt: float) -> float:
    t = (jd_tt - 2451545.0) / 36525.0
    return (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360.0


def obliquity(jd_tt: float) -> float:
    """平黄赤交角（度）。"""
    t = (jd_tt - 2451545.0) / 36525.0
    return (23.439291 - 0.0130042 * t - 1.64e-7 * t * t + 5.04e-7 * t ** 3)


def equation_of_time(jd_ut: float) -> float:
    """均时差（分钟）：真太阳时 - 平太阳时。范围约 ±16 分钟。"""
    jd_tt = jd_ut + delta_t_seconds(2000.0 + (jd_ut - 2451545.0) / 365.25) / 86400.0
    lam = math.radians(solar_longitude(jd_tt))
    eps = math.radians(obliquity(jd_tt))
    l0 = mean_solar_longitude(jd_tt)
    # 赤经 α
    alpha = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360.0
    diff = ((l0 - 0.0057183 - alpha + 180.0) % 360.0) - 180.0
    return diff * 4.0


def term_ut_jd(year: int, idx: int) -> float:
    """太阳视黄经到达 TERM_DEG[idx] 的 UT 儒略日（含 ΔT 修正）。"""
    target = TERM_DEG[idx]
    t0 = jd_from_gregorian(year, 1, 6) + idx * 15.2184

    def f(jd_ut: float) -> float:
        y = 2000.0 + (jd_ut - 2451545.0) / 365.25
        jd_tt = jd_ut + delta_t_seconds(y) / 86400.0
        return ((solar_longitude(jd_tt) - target + 180.0) % 360.0) - 180.0

    lo, hi = t0 - 2.0, t0 + 2.0
    for _ in range(4):
        if f(lo) * f(hi) <= 0:
            break
        lo -= 2.0
        hi += 2.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def term_local(year: int, idx: int, tz_hours: float) -> datetime:
    """节气的当地标准时（秒级）。"""
    return jd_to_datetime(term_ut_jd(year, idx) + tz_hours / 24.0)


def jie_list(year: int, tz_hours: float):
    """给定公历年的 12 个节（月令边界），当地标准时。"""
    out = []
    for idx in JIE_IDX:
        yy = year + 1 if idx == 0 else year   # 小寒属次年
        out.append((TERM_NAME[idx], idx, term_local(yy, idx, tz_hours)))
    return out


# --------------------------------------------------------------------------
# 时间修正：夏令时 + 真太阳时
# --------------------------------------------------------------------------

def dst_offset_hours(dt: datetime, mode: str = "auto") -> float:
    """中国 1986—1991 夏令时。返回需要减去的小时数。"""
    if mode == "off":
        return 0.0
    if mode == "on":
        return 1.0
    for start, end in CN_DST:
        if start <= dt < end:
            return 1.0
    return 0.0


def to_true_solar(dt: datetime, tz_hours: float, lon: float | None):
    """钟表时间 → 真太阳时。返回 (真太阳时, 明细 dict)。"""
    detail = {
        "clock_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "lon_correction_min": 0.0,
        "eot_min": 0.0,
        "applied": False,
    }
    if lon is None:
        return dt, detail
    jd_ut = jd_from_gregorian(dt.year, dt.month, dt.day,
                              dt.hour + dt.minute / 60.0 + dt.second / 3600.0) - tz_hours / 24.0
    eot = equation_of_time(jd_ut)
    lon_corr = (lon - tz_hours * 15.0) * 4.0
    detail.update({"lon_correction_min": round(lon_corr, 4),
                   "eot_min": round(eot, 4), "applied": True})
    true_dt = dt + timedelta(minutes=lon_corr + eot)
    detail["true_solar_time"] = true_dt.strftime("%Y-%m-%d %H:%M:%S")
    return true_dt, detail


# --------------------------------------------------------------------------
# 日期工具
# --------------------------------------------------------------------------

def add_months(dt: datetime, months: float) -> datetime:
    """加 months 个月（保留日/时分，月末溢出则退到该月最后一天）。"""
    whole = int(months)
    frac_days = (months - whole) * 30.4375
    m = dt.month - 1 + whole
    y = dt.year + m // 12
    m = m % 12 + 1
    day = dt.day
    while True:
        try:
            base = datetime(y, m, day, dt.hour, dt.minute, dt.second)
            break
        except ValueError:
            day -= 1            # 2/29、31 日等溢出，退一天
    return base + timedelta(days=frac_days)


def format_delta(days: float) -> str:
    """三天折一年，一天折四个月。"""
    years = int(days // 3)
    rem = days - years * 3
    months = int(rem * 4)
    return f"{years}年{months}个月"


def day_pillar_n(dt: datetime, boundary: str) -> int:
    """日柱在 60 甲子中的序号。boundary: zi(23时换日) | midnight(00时换日)。"""
    n = (DAY_ANCHOR_N + (dt.date() - DAY_ANCHOR.date()).days) % 60
    if boundary == "zi" and dt.hour >= 23:
        n = (n + 1) % 60
    return n


def liunian_ganzhi(year: int, tz_hours: float):
    """流年干支（以立春分界）。返回 (干支, 立春时刻)。"""
    lichun = term_local(year, LICHUN_IDX, tz_hours)
    return GAN[(year - 4) % 10] + ZHI[(year - 4) % 12], lichun


# --------------------------------------------------------------------------
# 排盘
# --------------------------------------------------------------------------

def calc(dt: datetime, tz_hours: float = 8.0, gender: str = "male",
         lucky_count: int = 10, years_count: int = 12,
         lon: float | None = None, day_boundary: str = "zi",
         dst: str = "auto") -> dict:
    warnings = []

    # ---- 夏令时 ----
    dst_h = dst_offset_hours(dt, dst)
    if dst_h:
        warnings.append(
            f"命中中国夏令时区间（1986—1991），已将钟表时间回拨 {dst_h:g} 小时；"
            "若出生记录本身已是标准时，请用 --dst off")
    std = dt - timedelta(hours=dst_h)

    # ---- 真太阳时 ----
    solar, solar_detail = to_true_solar(std, tz_hours, lon)
    if lon is None:
        warnings.append(
            "未提供 --lon，按时区中央经线计算；东八区内经度偏差最大可达 ±2 小时，"
            "时柱可能整根错位，人盘务必补经度")
    birth = solar

    # ---- 年柱（立春为界）----
    lichun = term_local(birth.year, LICHUN_IDX, tz_hours)
    gy = birth.year if birth >= lichun else birth.year - 1
    year_gan, year_zhi = GAN[(gy - 4) % 10], ZHI[(gy - 4) % 12]

    # ---- 月柱（12 节为界）----
    jies = jie_list(birth.year - 1, tz_hours) + jie_list(birth.year, tz_hours)
    jies.sort(key=lambda x: x[2])
    cur = None
    for name, idx, t in jies:
        if t <= birth:
            cur = (name, idx, t)
    if cur is None:
        raise ValueError("无法定位月令，请检查输入时间")
    cur_name, cur_idx, cur_time = cur
    month_zhi_i = JIE_ZHI[JIE_IDX.index(cur_idx)]
    month_zhi = ZHI[month_zhi_i]
    month_gan = GAN[(WUHU[year_gan] + (month_zhi_i - 2) % 12) % 10]

    # 距节气过近时提示（低精度黄经式 + 历史授时差异）
    hours_to_jie = abs((birth - cur_time).total_seconds()) / 3600.0
    nxt = next((t for _, _, t in jies if t > birth), None)
    if nxt is not None:
        hours_to_jie = min(hours_to_jie, abs((nxt - birth).total_seconds()) / 3600.0)
    if hours_to_jie < 1.0:
        warnings.append(
            f"距节气交界不足 1 小时（{hours_to_jie*60:.0f} 分钟），"
            "月柱对算法精度敏感，请与权威万年历核对")

    # ---- 日柱 ----
    day_n = day_pillar_n(birth, day_boundary)
    day_gan, day_zhi = GAN[day_n % 10], ZHI[day_n % 12]
    alt_boundary = "midnight" if day_boundary == "zi" else "zi"
    alt_n = day_pillar_n(birth, alt_boundary)
    day_pillar_alt = pillar60(alt_n) if alt_n != day_n else None

    # ---- 时柱（五鼠遁）----
    hour_zhi_i = ((birth.hour + 1) // 2) % 12
    hour_gan = GAN[(WUSHU[day_gan] + hour_zhi_i) % 10]
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

    changsheng = {
        "月支": changsheng_pos(day_gan, month_zhi),
        "日支": changsheng_pos(day_gan, day_zhi),
        "时支": changsheng_pos(day_gan, hour_zhi),
    }

    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for p in pillars:
        counts[wuxing(p["gan"])] += 1
        for g in p["canggan"]:
            counts[wuxing(g)] += 1

    # ---- 神煞 ----
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
        for base_label, base_zhi in (("日支", day_zhi), ("年支", year_zhi)):
            for members, j in JU.items():
                if base_zhi not in members:
                    continue
                for name, table in (("桃花", TAOHUA), ("驿马", YIMA),
                                    ("将星", JIANGXING), ("华盖", HUAGAI),
                                    ("劫煞", JIESHA), ("亡神", WANGSHEN)):
                    if p["zhi"] == ZHI[table[j]]:
                        tags.append(f"{name}({base_label})")
        if tags:
            shensha[p["label"]] = list(dict.fromkeys(tags))

    # ---- 大运 ----
    yang_year = is_yang(year_gan)
    forward = (yang_year and gender == "male") or (not yang_year and gender == "female")
    month_n = idx60(month_gan, month_zhi)
    jies_all = sorted(jie_list(birth.year - 1, tz_hours) +
                      jie_list(birth.year, tz_hours) +
                      jie_list(birth.year + 1, tz_hours), key=lambda x: x[2])
    if forward:
        anchor = next(t for _, _, t in jies_all if t > birth)
    else:
        anchor = max(t for _, _, t in jies_all if t < birth)
    gap_days = abs((anchor - birth).total_seconds()) / 86400.0
    jiao_time = add_months(birth, gap_days * 4.0)
    step = 1 if forward else -1
    lucky = []
    for k in range(lucky_count):
        n = (month_n + step * (k + 1)) % 60
        start = add_months(jiao_time, k * 120)
        lucky.append({"ganzhi": pillar60(n), "start": start.strftime("%Y-%m-%d"),
                      "age": round(gap_days / 3.0 + k * 10, 1)})

    # ---- 流年（立春分界）----
    liunian = []
    for y in range(birth.year, birth.year + years_count + 1):
        gz, lc = liunian_ganzhi(y, tz_hours)
        liunian.append({"year": y, "ganzhi": gz,
                        "lichun": lc.strftime("%Y-%m-%d %H:%M")})

    return {
        "version": "v5",
        "input": dt.strftime("%Y-%m-%d %H:%M"),
        "tz_hours": tz_hours,
        "lon": lon,
        "gender": gender,
        "day_boundary": day_boundary,
        "dst_applied_hours": dst_h,
        "solar_time": solar_detail,
        "effective_time": birth.strftime("%Y-%m-%d %H:%M:%S"),
        "year_pillar": year_gan + year_zhi,
        "month_pillar": month_gan + month_zhi,
        "day_pillar": day_gan + day_zhi,
        "day_pillar_alt": day_pillar_alt,
        "hour_pillar": hour_gan + hour_zhi,
        "day_master": day_gan,
        "month_jie": cur_name,
        "month_jie_time": cur_time.strftime("%Y-%m-%d %H:%M:%S"),
        "pillars": pillars,
        "changsheng": changsheng,
        "wuxing_counts": counts,
        "shensha": shensha,
        "dayun_direction": "顺排" if forward else "逆排",
        "jiao_time": jiao_time.strftime("%Y-%m-%d"),
        "jiao_age": format_delta(gap_days),
        "lucky": lucky,
        "liunian": liunian,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------

def render(result: dict) -> str:
    lines = []
    lines.append(f"输入: {result['input']} (UTC{result['tz_hours']:+g})"
                 f" 性别设定: {result['gender']} 换日: {result['day_boundary']}")
    sd = result["solar_time"]
    if sd["applied"]:
        lines.append(f"真太阳时: {sd['true_solar_time']}"
                     f" (经度修正 {sd['lon_correction_min']:+.1f} 分, 均时差 {sd['eot_min']:+.1f} 分)")
    else:
        lines.append("真太阳时: 未修正（未提供 --lon）")
    if result["dst_applied_hours"]:
        lines.append(f"夏令时: 已回拨 {result['dst_applied_hours']:g} 小时")
    lines.append(f"四柱: {result['year_pillar']} {result['month_pillar']}"
                 f" {result['day_pillar']} {result['hour_pillar']}")
    if result["day_pillar_alt"]:
        lines.append(f"  （另一换日流派日柱为 {result['day_pillar_alt']}，并列供参）")
    lines.append("纳音: " + " ".join(p["nayin"] for p in result["pillars"]))
    dm = result["day_master"]
    lines.append(f"日主: {dm}{wuxing(dm)} ({'阳' if is_yang(dm) else '阴'})"
                 f"   月令: {result['month_jie']} 交节 {result['month_jie_time']}")
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
    lines.append(f"大运: {result['dayun_direction']}  起运约 {result['jiao_age']}"
                 f" (交运 {result['jiao_time']})")
    for l in result["lucky"]:
        lines.append(f"  {l['ganzhi']}  起于 {l['start']} (约{l['age']}岁)")
    lines.append("")
    lines.append("流年(立春分界): " + " ".join(f"{x['year']}{x['ganzhi']}" for x in result["liunian"]))
    if result["warnings"]:
        lines.append("")
        for w in result["warnings"]:
            lines.append(f"⚠ {w}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="四柱八字排盘 (BFFT)")
    ap.add_argument("datetime", help='当地钟表时间, e.g. "2024-05-23 10:00"')
    ap.add_argument("--name", default="")
    ap.add_argument("--tz", type=float, default=8.0, help="UTC 偏移小时, 默认 8")
    ap.add_argument("--lon", type=float, default=None,
                    help="出生地经度(东正西负), 用于真太阳时修正; 人盘强烈建议提供")
    ap.add_argument("--gender", choices=["male", "female"], default="male",
                    help="大运顺逆用; game/product 默认 male")
    ap.add_argument("--day-boundary", choices=["zi", "midnight"], default="zi",
                    help="换日流派: zi=23时换日(默认), midnight=00时换日")
    ap.add_argument("--dst", choices=["auto", "on", "off"], default="auto",
                    help="中国 1986—1991 夏令时处理, 默认 auto")
    ap.add_argument("--lucky", type=int, default=10)
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.lucky < 1 or args.years < 0:
        ap.error("--lucky 需 >=1, --years 需 >=0")
    if args.lon is not None and not -180.0 <= args.lon <= 180.0:
        ap.error("--lon 需在 -180..180")

    try:
        dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ap.error('时间格式应为 "YYYY-MM-DD HH:MM"')

    result = calc(dt, tz_hours=args.tz, gender=args.gender,
                  lucky_count=args.lucky, years_count=args.years,
                  lon=args.lon, day_boundary=args.day_boundary, dst=args.dst)
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
