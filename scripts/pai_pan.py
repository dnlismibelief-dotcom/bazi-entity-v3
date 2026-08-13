#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四柱八字排盘 (BaZi chart calculator) — BFFT v7.

Pure Python 3 stdlib, no external dependencies.

v7 相对 v6 的变化（全部由 50 人跨年代交叉验证暴露, 参照 sxtwl 与 lunar_python）
-----------------------------------------------------------------------------
修正:
  * ΔT 只有以 1900 为基准的一段, 往前外推发散: 1500 年算出 -63 天、1800 年 -7.4 小时。
    补全 Espenak & Meeus 分段(-500..2150)。
  * 节气求根用 t0±2 天二分、最多扩到 ±10 天, 1680 年前目标落窗外时把**初值**当结果返回
    (1500 与 1582 的节气时刻因此秒级完全相同) 且不抛异常。改牛顿迭代 + 残差校验抛异常。
  * 中国夏令时表被无条件套到全世界: 1988 年夏天的东京/纽约/新德里盘也回拨一小时。
    改为只对东八区生效, 别处需显式 --dst on。
  * jd_from_gregorian(输入) 用格里历而 jd_to_datetime(输出) 在 1582 前用儒略历,
    两侧历法不一致; 且会造出 1000-02-29 这种格里历里不存在的日期直接抛异常。
    输出统一为推算格里历。
  * 胎元原只输出"300 日法"并冠《三命通会》之名, 与通行口诀(月干进一/月支进三)不符,
    且倒推时把出生时刻截断成 00:00 (交节日会错一整月)。改为两派并列 + 保留时刻。

新增:
  * --calendar auto|julian|gregorian: 输入日期的历法声明。auto 在 1582-10-15 前按
    儒略历解释(史料惯例)。注意历法基准要逐条确认 —— 同一批史料里可能混着已换算过的值。
  * term_ut_jd 加 lru_cache: 45 条测试从 4.1s 降到 0.07s。

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
from functools import lru_cache

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

# 天乙贵人（口诀: 甲戊庚牛羊, 乙己鼠猴乡, 丙丁猪鸡位, 壬癸兔蛇藏, 六辛逢马虎）
TIANYI = {"甲": [1, 7], "戊": [1, 7], "庚": [1, 7],
          "乙": [0, 8], "己": [0, 8],
          "丙": [11, 9], "丁": [11, 9],
          "壬": [3, 5], "癸": [3, 5],
          "辛": [2, 6]}
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


def jd_from_julian(y: int, m: int, d: float, h: float = 0.0) -> float:
    """儒略历日期 → JD（就是格里历公式去掉那个世纪修正项 b）。"""
    if m <= 2:
        y -= 1
        m += 12
    return (math.floor(365.25 * (y + 4716)) +
            math.floor(30.6001 * (m + 1)) + d - 1524.5 + h / 24.0)


GREGORIAN_START = datetime(1582, 10, 15)


def normalize_calendar(dt: datetime, calendar: str = "auto"
                       ) -> tuple[datetime, str]:
    """把输入日期规范化成推算格里历 datetime。返回 (格里历 dt, 说明)。

    calendar:
      auto      —— 1582-10-15 之前按儒略历解释（史料与 sxtwl/lunar-javascript 的惯例）
      julian    —— 强制按儒略历
      gregorian —— 强制按推算格里历（v6 及以前的隐含行为）

    只在入口转一次, 之后全流程都是格里历, 下游逻辑不用关心历法。
    """
    if calendar == "gregorian":
        return dt, ""
    if calendar == "auto" and dt >= GREGORIAN_START:
        return dt, ""
    h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    jd = jd_from_julian(dt.year, dt.month, dt.day, h)
    greg = jd_to_datetime(jd)
    return greg, (f"输入 {dt:%Y-%m-%d %H:%M} 按儒略历解释，"
                  f"已换算为格里历 {greg:%Y-%m-%d %H:%M}（相差 "
                  f"{(greg.date() - dt.date()).days} 天）；"
                  "若你的日期本就是格里历，请用 --calendar gregorian")


def jd_to_datetime(jd: float) -> datetime:
    """儒略日 → datetime（秒级，四舍五入到秒）。

    **始终按推算格里历**, 与输入侧 jd_from_gregorian 保持一致。
    v6 及以前对 z < 2299161 走儒略历分支, 于是输入按格里历、输出按儒略历,
    1582 年前节气时刻与出生时刻实际是拿两套历法的日期在比较 (差 9—10 天);
    还会造出格里历里不存在的日期 —— 公元 1000 年儒略历闰而格里历不闰,
    算出 1000-02-29 直接让 datetime 抛 "day is out of range for month"。
    """
    jd += 0.5
    z = math.floor(jd)
    f = jd - z
    alpha = math.floor((z - 1867216.25) / 36524.25)
    a = z + 1 + alpha - math.floor(alpha / 4)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    base = datetime(year, month, 1) + timedelta(days=int(day) - 1)
    return base + timedelta(seconds=round(f * 86400.0))


def delta_t_seconds(year: float) -> float:
    """ΔT = TT - UT，秒。Espenak & Meeus 分段多项式（NASA eclipse 网站那套）。

    覆盖 −500 … +2150。**每一段只在自己的区间内有效，往外外推会发散** ——
    v6 及以前把 1900 年前全部塞给以 1900 为基准的四次式，结果 1500 年算出 −63 天、
    1800 年算出 −7.4 小时，节气时刻整体错位（1680 年前更是让求解器直接不收敛）。
    分段端点互相衔接（1600 段边界 120.3 vs 120、1700 段 8.99 vs 8.83），可作自检。
    """
    if year < -500:
        u = (year - 1820) / 100.0
        return -20 + 32 * u ** 2
    if year < 500:
        u = year / 100.0
        return (10583.6 - 1014.41 * u + 33.78311 * u ** 2 - 5.952053 * u ** 3
                - 0.1798452 * u ** 4 + 0.022174192 * u ** 5
                + 0.0090316521 * u ** 6)
    if year < 1600:
        u = (year - 1000) / 100.0
        return (1574.2 - 556.01 * u + 71.23472 * u ** 2 + 0.319781 * u ** 3
                - 0.8503463 * u ** 4 - 0.005050998 * u ** 5
                + 0.0083572073 * u ** 6)
    if year < 1700:
        t = year - 1600
        return 120 - 0.9808 * t - 0.01532 * t ** 2 + t ** 3 / 7129.0
    if year < 1800:
        t = year - 1700
        return (8.83 + 0.1603 * t - 0.0059285 * t ** 2 + 0.00013336 * t ** 3
                - t ** 4 / 1174000.0)
    if year < 1860:
        t = year - 1800
        return (13.72 - 0.332447 * t + 0.0068612 * t ** 2 + 0.0041116 * t ** 3
                - 0.00037436 * t ** 4 + 0.0000121272 * t ** 5
                - 0.0000001699 * t ** 6 + 0.000000000875 * t ** 7)
    if year < 1900:
        t = year - 1860
        return (7.62 + 0.5737 * t - 0.251754 * t ** 2 + 0.01680668 * t ** 3
                - 0.0004473624 * t ** 4 + t ** 5 / 233174.0)
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


@lru_cache(maxsize=4096)
def term_ut_jd(year: int, idx: int) -> float:
    """太阳视黄经到达 TERM_DEG[idx] 的 UT 儒略日（含 ΔT 修正）。

    用牛顿法而不是二分: 太阳黄经日均走 0.98565°, 残差归一到 ±180° 后除以日角速度
    就是天数步长, 任意年份都几步收敛。
    旧版是 t0±2 天二分、失败最多扩到 ±10 天 —— 远古年份目标点落在窗外时
    f(lo)*f(hi) 恒同号, 100 次二分白跑, `return (lo+hi)/2` 把**初值**当结果返回,
    所以 1500 和 1582 年算出的节气时刻秒级完全相同。现在不收敛直接抛异常。
    """
    target = TERM_DEG[idx]
    jd = jd_from_gregorian(year, 1, 6) + idx * 15.2184

    def resid(jd_ut: float) -> float:
        y = 2000.0 + (jd_ut - 2451545.0) / 365.25
        jd_tt = jd_ut + delta_t_seconds(y) / 86400.0
        return ((solar_longitude(jd_tt) - target + 180.0) % 360.0) - 180.0

    for _ in range(40):
        d = resid(jd)
        if abs(d) < 1e-9:
            break
        # 限步: 防远古年份初值偏差过大时一步甩到隔年的同名节气
        jd -= max(-40.0, min(40.0, d / 0.98564736))

    d = resid(jd)
    if abs(d) > 1e-6:
        raise ValueError(
            f"节气求解未收敛: year={year} idx={idx}({TERM_NAME[idx]}) "
            f"残差={d:+.6f}° —— 请检查 ΔT 与黄经公式的适用年限")
    return jd


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

def dst_offset_hours(dt: datetime, mode: str = "auto",
                     tz_hours: float | None = None) -> float:
    """中国 1986—1991 夏令时。返回需要减去的小时数。

    auto 只对**东八区**生效 —— 这张表是中国的, 套到别处就是错。
    v6 及以前只看 dt 不看时区, 于是 1988 年夏天出生的东京/纽约/新德里盘
    也一律回拨一小时, 真太阳时恒错 60 分钟。
    别国夏令时规则各异且逐年变动, 不进这张表, 需要时显式 --dst on。
    """
    if mode == "off":
        return 0.0
    if mode == "on":
        return 1.0
    if tz_hours is not None and abs(tz_hours - 8.0) > 1e-9:
        return 0.0
    for start, end in CN_DST:
        if start <= dt < end:
            return 1.0
    return 0.0


def to_solar_time(dt: datetime, tz_hours: float, lon: float | None) -> datetime:
    """当地标准时 → 真太阳时 datetime（lon 为 None 时原样返回）。

    节气时刻、起运锚点、胎元倒推都必须与出生时刻用同一个时间基准比较，
    否则经度偏差会伪装成"节气提前/延后"（v7.1 及以前: 乌鲁木齐 17:00 立春
    当天的盘年柱月柱整体错位, 因为拿真太阳时的出生去比标准时的节气）。
    """
    if lon is None:
        return dt
    jd_ut = jd_from_gregorian(dt.year, dt.month, dt.day,
                              dt.hour + dt.minute / 60.0 + dt.second / 3600.0) - tz_hours / 24.0
    eot = equation_of_time(jd_ut)
    lon_corr = (lon - tz_hours * 15.0) * 4.0
    return dt + timedelta(minutes=lon_corr + eot)


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
    true_dt = to_solar_time(dt, tz_hours, lon)
    jd_ut = jd_from_gregorian(dt.year, dt.month, dt.day,
                              dt.hour + dt.minute / 60.0 + dt.second / 3600.0) - tz_hours / 24.0
    eot = equation_of_time(jd_ut)
    lon_corr = (lon - tz_hours * 15.0) * 4.0
    detail.update({"lon_correction_min": round(lon_corr, 4),
                   "eot_min": round(eot, 4), "applied": True})
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


def taiyuan_month_pillar(birth: datetime, tz_hours: float,
                         month_pillar: str, lon: float | None = None) -> dict:
    """胎元。两派并列输出, 不作独断（同换日流派的处理方式）。

    主派 —— 进三位法：月干进一位、月支进三位。十月怀胎逆推十月即地支顺进三位,
    这是《三命通会》《渊海子平》《神峰通考》共载的通行口诀。
    旁证 —— 300 日法：生日前 300 日所在节令月。

    两派常给出不同结果（如月柱己巳: 进三位 → 庚申, 300 日法 → 己未），所以并列。
    v6 只输出 300 日法且冠以"三命通会"之名, 与通行口诀不符, 已改。
    v7.2: 倒推出的时刻与节气时刻统一用真太阳时比较（与 calc 同基准）。
    """
    # 主派: 月柱进位
    m_gan_i = GAN.index(month_pillar[0])
    m_zhi_i = ZHI.index(month_pillar[1])
    primary = GAN[(m_gan_i + 1) % 10] + ZHI[(m_zhi_i + 3) % 12]

    # 旁证: 300 日法。保留出生时刻再倒推 —— 只取日期会让胎元落在交节当天时错一整月
    tai_dt = birth - timedelta(days=300)
    jies = sorted(
        jie_list(tai_dt.year - 1, tz_hours) + jie_list(tai_dt.year, tz_hours),
        key=lambda x: x[2],
    )
    cur = None
    cur_std_time = None
    for (name, idx, t), (_, _, t_std) in zip(
            [(name, idx, to_solar_time(t, tz_hours, lon)) for name, idx, t in jies],
            jies):
        if t <= tai_dt:
            cur = (name, idx, t)
            cur_std_time = t_std
    if cur is None:
        raise ValueError("无法定位胎元月令")
    cur_name, cur_idx, cur_time = cur
    zhi_i = JIE_ZHI[JIE_IDX.index(cur_idx)]
    lichun = to_solar_time(term_local(tai_dt.year, LICHUN_IDX, tz_hours), tz_hours, lon)
    ty = tai_dt.year if tai_dt >= lichun else tai_dt.year - 1
    year_gan = GAN[(ty - 4) % 10]
    gan = GAN[(WUHU[year_gan] + (zhi_i - 2) % 12) % 10]
    by_300 = gan + ZHI[zhi_i]

    return {
        "primary": primary,
        "primary_method": "进三位法(月干进一/月支进三, 三命通会通行口诀)",
        "alt": by_300,
        "alt_method": "300日法(旁证)",
        "agree": primary == by_300,
        "date": tai_dt.strftime("%Y-%m-%d %H:%M"),
        "jie": cur_name,
        "jie_time": (cur_std_time or cur_time).strftime("%Y-%m-%d %H:%M:%S"),
    }


def minggong(year_gan: str, month_zhi_i: int, hour_zhi: str) -> str:
    """命宫（《三命通会》法）：子位起正月逆行至生月，从月宫顺数至卯安命宫。

    例：三月生戌时 → 三月在戌宫，卯时落卯宫 → 命坐卯宫；甲子年 → 丁卯。
    """
    month_no = (month_zhi_i - 2) % 12 + 1  # 寅=1 … 丑=12
    month_i = (13 - month_no) % 12  # 正月在子(0)
    hour_i = ZHI.index(hour_zhi)
    ming_i = (month_i + (3 - hour_i)) % 12  # 卯序=3
    ming_zhi = ZHI[ming_i]
    ming_gan = GAN[(WUHU[year_gan] + (ming_i - 2) % 12) % 10]
    return ming_gan + ming_zhi


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
         dst: str = "auto", calendar: str = "auto") -> dict:
    warnings = []

    # ---- 输入历法: 1582-10-15 前默认按儒略历解释, 入口一次性换算成格里历 ----
    raw_input_dt = dt
    dt, cal_note = normalize_calendar(dt, calendar)
    if cal_note:
        warnings.append(cal_note)
    if not (1000 <= dt.year <= 2200):
        warnings.append(
            f"出生年 {dt.year} 超出黄经与 ΔT 公式的可靠区间（约 1000—2200），"
            "节气时刻误差会显著放大")

    # ---- 夏令时 ----
    dst_h = dst_offset_hours(dt, dst, tz_hours)
    if dst_h:
        warnings.append(
            f"命中中国夏令时区间（1986—1991），已将钟表时间回拨 {dst_h:g} 小时；"
            "若出生记录本身已是标准时，请用 --dst off")
    elif dst == "auto" and abs(tz_hours - 8.0) > 1e-9 and any(
            s <= dt < e for s, e in CN_DST):
        warnings.append(
            "落在中国 1986—1991 夏令时区间但不在东八区，未做回拨；"
            "若出生地当年实行夏令时，请核对后用 --dst on")
    std = dt - timedelta(hours=dst_h)

    # ---- 真太阳时 ----
    solar, solar_detail = to_true_solar(std, tz_hours, lon)
    if lon is None:
        warnings.append(
            "未提供 --lon，按时区中央经线计算；东八区内经度偏差最大可达 ±2 小时，"
            "时柱可能整根错位，人盘务必补经度")
    birth = solar

    # ---- 年柱（立春为界）----
    # 节气时刻与出生时刻统一换算成真太阳时再比较（v7.2 修复：v7.1 及以前
    # 拿真太阳时的出生去比标准时的节气，经度偏差 ±2h16m 会整体错年/月柱）
    lichun_std = term_local(birth.year, LICHUN_IDX, tz_hours)
    lichun = to_solar_time(lichun_std, tz_hours, lon)
    gy = birth.year if birth >= lichun else birth.year - 1
    year_gan, year_zhi = GAN[(gy - 4) % 10], ZHI[(gy - 4) % 12]

    # ---- 月柱（12 节为界）----
    jies = jie_list(birth.year - 1, tz_hours) + jie_list(birth.year, tz_hours)
    jies.sort(key=lambda x: x[2])
    jies_solar = [(name, idx, to_solar_time(t, tz_hours, lon)) for name, idx, t in jies]
    cur = None
    cur_std_time = None
    for (name, idx, t), (_, _, t_std) in zip(jies_solar, jies):
        if t <= birth:
            cur = (name, idx, t)
            cur_std_time = t_std
    if cur is None:
        raise ValueError("无法定位月令，请检查输入时间")
    cur_name, cur_idx, cur_solar_time = cur
    month_zhi_i = JIE_ZHI[JIE_IDX.index(cur_idx)]
    month_zhi = ZHI[month_zhi_i]
    month_gan = GAN[(WUHU[year_gan] + (month_zhi_i - 2) % 12) % 10]

    # 距节气过近时提示（低精度黄经式 + 历史授时差异；基准已统一为真太阳时）
    hours_to_jie = abs((birth - cur_solar_time).total_seconds()) / 3600.0
    nxt = next((t for _, _, t in jies_solar if t > birth), None)
    if nxt is not None:
        hours_to_jie = min(hours_to_jie, abs((nxt - birth).total_seconds()) / 3600.0)
    if hours_to_jie < 1.0:
        warnings.append(
            f"距节气交界不足 1 小时（{hours_to_jie*60:.0f} 分钟，真太阳时基准），"
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
    jies_all_solar = [(name, idx, to_solar_time(t, tz_hours, lon))
                      for name, idx, t in jies_all]
    if forward:
        anchor = next(t for _, _, t in jies_all_solar if t > birth)
    else:
        anchor = max(t for _, _, t in jies_all_solar if t < birth)
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

    # ---- 胎元与命宫（三命通会，v6 新增，低置信旁证）----
    taiyuan = taiyuan_month_pillar(birth, tz_hours, month_gan + month_zhi, lon)
    minggong_gz = minggong(year_gan, month_zhi_i, hour_zhi)

    return {
        "version": "v7",
        "input": dt.strftime("%Y-%m-%d %H:%M"),
        "input_raw": raw_input_dt.strftime("%Y-%m-%d %H:%M"),
        "calendar": calendar,
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
        "month_jie_time": cur_std_time.strftime("%Y-%m-%d %H:%M:%S"),
        "pillars": pillars,
        "changsheng": changsheng,
        "wuxing_counts": counts,
        "shensha": shensha,
        "dayun_direction": "顺排" if forward else "逆排",
        "jiao_time": jiao_time.strftime("%Y-%m-%d"),
        "jiao_age": format_delta(gap_days),
        "lucky": lucky,
        "liunian": liunian,
        "taiyuan": taiyuan,
        "minggong": minggong_gz,
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
    ty = result["taiyuan"]
    if ty["agree"]:
        lines.append(f"胎元: {ty['primary']} (两派一致: 进三位法 / 300日法)")
    else:
        lines.append(f"胎元: {ty['primary']} ({ty['primary_method']})"
                     f"　｜　旁证 {ty['alt']} ({ty['alt_method']}, 受胎约 {ty['date']})")
    lines.append(f"命宫: {result['minggong']} (三命通会法, 低置信旁证)")
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
    ap.add_argument("--calendar", choices=["auto", "julian", "gregorian"],
                    default="auto",
                    help="输入日期的历法。auto=1582-10-15 前按儒略历(史料惯例), 默认 auto")
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
                  lon=args.lon, day_boundary=args.day_boundary, dst=args.dst,
                  calendar=args.calendar)
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
