#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紫微斗数排盘引擎 — BFFT v7.17（紫微平行模块，后端；零依赖）。

来源与许可：
  - 农历数据表（lunar_data.py 2025-2086）：Seanding1998/liuyao-frv
    （个人免费·商业授权许可证——本模块仅限个人/学习/研究使用，
     商业使用请联系原作者 Seanding；数据源紫金山天文台/寿星天文历）
  - 安星规则（命宫/五行局/紫微定位/十四主星/四化/辅星）：公开经典算法
    （《紫微斗数全书》体系），参照 Renhuai123/ziwei-doushu（MIT）的
    常量表（四化/纳音/魁钺）——该仓库排盘依赖 iztro，本模块自研实现，
    不引入第三方排盘库（BFFT 零依赖原则）。
  - 紫微与四柱是平行体系：解盘纪律与四柱一致（事前判据、禁伪精确、
    断语分级），不因换体系而放松。

覆盖范围（骨架版）：
  命宫/身宫、十二宫、宫干五虎遁、五行局、紫微定位、十四主星、
  生年四化、文昌文曲、左辅右弼、天魁天钺、禄存、擎羊陀罗。
  （火铃/空劫/其余杂曜、大限流年未实现，后续版本补充。）

用法:
  from scripts.ziwei.paipan import ziwei_calc
  r = ziwei_calc(1990, 1, 1, 10, gender="male")
"""

from __future__ import annotations

import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "lunar_data", os.path.join(_HERE, "lunar_data.py"))
_LD = importlib.util.module_from_spec(_SPEC)
sys.modules["lunar_data"] = _LD
_SPEC.loader.exec_module(_LD)

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
PALACES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
           "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]

WUHU = {"甲": 2, "乙": 4, "丙": 6, "丁": 8, "戊": 0,
        "己": 2, "庚": 4, "辛": 6, "壬": 8, "癸": 0}

# 纳音五行（60 甲子顺序，每两组一纳音）
NAYIN = ["金", "火", "木", "土", "金", "火", "水", "土", "金", "木",
         "水", "土", "火", "木", "水", "金", "火", "木", "土", "金",
         "火", "水", "土", "金", "木", "水", "土", "火", "木", "水"]
JU_NUM = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAMES = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 五局紫微起始宫（《紫微斗数全书》）
JU_START = {2: 2, 3: 4, 4: 11, 5: 6, 6: 9}  # 水二局寅、木三局辰、金四局亥、土五局午、火六局酉

# 四化（年干 → 禄权科忌）
SIHUA = {
    "甲": ["廉贞", "破军", "武曲", "太阳"],
    "乙": ["天机", "天梁", "紫微", "太阴"],
    "丙": ["天同", "天机", "文昌", "廉贞"],
    "丁": ["太阴", "天同", "天机", "巨门"],
    "戊": ["贪狼", "太阴", "右弼", "天机"],
    "己": ["武曲", "贪狼", "天梁", "文曲"],
    "庚": ["太阳", "武曲", "太阴", "天同"],
    "辛": ["巨门", "太阳", "文曲", "文昌"],
    "壬": ["天梁", "紫微", "左辅", "武曲"],
    "癸": ["破军", "巨门", "太阴", "贪狼"],
}

# 天魁天钺（年干 → 天魁支, 天钺支）
KUIYUE = {
    "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("子", "申"), "己": ("子", "申"),
    "丙": ("亥", "酉"), "丁": ("亥", "酉"),
    "壬": ("卯", "巳"), "癸": ("卯", "巳"),
    "辛": ("午", "寅"),
}

# 禄存（年干 → 支）
LUCUN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
         "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}


def _ganzhi60(n: int) -> str:
    return GAN[n % 10] + ZHI[n % 12]


def _idx60(gz: str) -> int:
    g, z = gz[0], gz[1]
    for n in range(60):
        if GAN[n % 10] == g and ZHI[n % 12] == z:
            return n
    raise ValueError(gz)


def _nayin_element(gz: str) -> str:
    return NAYIN[_idx60(gz) // 2]


def _solar_to_lunar(year, month, day) -> tuple[int, int, int, bool] | None:
    """公历→农历（lunar_data 2025-2086 表）。返回 (农历年, 月, 日, 是否闰月)。"""
    table = _LD.LUNAR_TABLE_2025_2086
    for ly in range(year, year - 2, -1):
        if ly not in table:
            continue
        m0, d0, bits, total, leap = table[ly]
        # 农历年 ly 的正月初一公历日期
        anchor_y = ly
        anchor_m, anchor_d = m0, d0
        # 计算公历日期相对锚点的天数
        import datetime as _dt
        target = _dt.date(year, month, day)
        anchor = _dt.date(anchor_y, anchor_m, anchor_d)
        delta = (target - anchor).days
        if delta < 0:
            continue
        # 逐月推进
        for mi in range(1, total + 1):
            is_leap = (leap > 0 and mi == leap + 1)
            real_mi = (leap if is_leap else (mi - 1 if leap > 0 and mi > leap else mi))
            days = 30 if ((bits >> (total - mi)) & 1) else 29
            if delta < days:
                return ly, real_mi, delta + 1, is_leap
            delta -= days
        # 可能属于下一年
        continue
    return None


def ziwei_calc(year: int, month: int, day: int, hour: int,
               gender: str = "male") -> dict:
    """紫微斗数排盘（公历输入）。

    hour: 0-23。2025-2086 外返回 gaps 提示（农历表范围）。
    """
    gaps = []
    if not (2025 <= year <= 2086):
        gaps.append(f"农历数据表覆盖 2025-2086，{year} 年超出范围，"
                    "农历与紫微定位不可算，以下字段为空")

    lunar = _solar_to_lunar(year, month, day) if not gaps else None
    if not lunar and not gaps:
        gaps.append("农历转换失败（该日期属表前一年腊月或超出农历表范围），"
                    "紫微定位与主星不可算；请改用表内日期（2025-02 起）")
    if lunar:
        l_year, l_month, l_day, l_leap = lunar
        l_year_gan = GAN[(l_year - 4) % 10]
        l_year_zhi = ZHI[(l_year - 4) % 12]
    else:
        l_year_gan = l_year_zhi = ""
        l_month = l_day = 0
        l_leap = False

    # 命宫/身宫（寅起正月顺数至生月；命宫逆数至生时，身宫顺数至生时）
    month_palace = (2 + l_month - 1) % 12  # 寅=2 起正月
    shi_zhi = ZHI.index(ZHI[((hour + 1) // 2) % 12])
    ming = (month_palace - shi_zhi) % 12
    shen = (month_palace + shi_zhi) % 12

    # 十二宫（命宫起逆布）
    palaces = []
    for i in range(12):
        zhi_i = (ming - i) % 12
        palaces.append({"name": PALACES[i], "zhi": ZHI[zhi_i]})

    # 宫干（命宫五虎遁起）
    if l_year_gan:
        ming_gan_i = (WUHU[l_year_gan] + ming - 2) % 10
        for i, p in enumerate(palaces):
            p["gan"] = GAN[(ming_gan_i + i) % 10]
    else:
        for p in palaces:
            p["gan"] = ""

    # 五行局（命宫干支纳音）
    ju = None
    ziwei_pos = None
    if l_year_gan and l_day:
        ming_gz = palaces[0]["gan"] + palaces[0]["zhi"]
        element = _nayin_element(ming_gz)
        ju = JU_NUM[element]
        ziwei_pos = (JU_START[ju] + (l_day - 1) // ju) % 12

    # 十四主星安星
    star_map = {i: [] for i in range(12)}
    if ziwei_pos is not None:
        # 紫微系（逆行）
        ziwei_series = [("紫微", 0), ("天机", 1), ("太阳", 3), ("武曲", 4),
                        ("天同", 5), ("廉贞", 8)]
        for name, back in ziwei_series:
            pos = (ziwei_pos - back) % 12
            star_map[pos].append(name)
        # 天府系（顺行；天府与紫微以寅申轴对称：天府pos = (寅+申) - 紫微pos）
        tianfu_pos = (2 + 8 - ziwei_pos) % 12
        tianfu_series = [("天府", 0), ("太阴", 1), ("贪狼", 2), ("巨门", 3),
                         ("天相", 4), ("天梁", 5), ("七杀", 6), ("破军", 10)]
        for name, fwd in tianfu_series:
            pos = (tianfu_pos + fwd) % 12
            star_map[pos].append(name)

    # 辅星
    if l_year_gan:
        kui, yue = KUIYUE[l_year_gan]
        star_map[ZHI.index(kui)].append("天魁")
        star_map[ZHI.index(yue)].append("天钺")
        lucun_zhi = LUCUN[l_year_gan]
        star_map[ZHI.index(lucun_zhi)].append("禄存")
        # 擎羊/陀罗 = 禄存前后各一宫
        star_map[(ZHI.index(lucun_zhi) + 1) % 12].append("擎羊")
        star_map[(ZHI.index(lucun_zhi) - 1) % 12].append("陀罗")
        # 昌曲（时支起戌辰逆顺）: 文昌=戌起逆数至时支, 文曲=辰起顺数至时支
        star_map[(10 - shi_zhi) % 12].append("文昌")
        star_map[(4 + shi_zhi) % 12].append("文曲")
        # 左右（月支）: 左辅=辰起顺数至生月, 右弼=戌起逆数至生月
        star_map[(4 + l_month - 1) % 12].append("左辅")
        star_map[(10 - (l_month - 1)) % 12].append("右弼")

    # 四化标注（生年干）
    sihua_flags = {"禄": [], "权": [], "科": [], "忌": []}
    if l_year_gan:
        lu, quan, ke, ji = SIHUA[l_year_gan]
        for key, star in [("禄", lu), ("权", quan), ("科", ke), ("忌", ji)]:
            for i, stars in star_map.items():
                if star in stars:
                    sihua_flags[key].append(i)

    return {
        "version": "v7.17",
        "input": f"{year}-{month:02d}-{day:02d} {hour:02d}:00",
        "gender": gender,
        "lunar": {"year": l_year_gan + l_year_zhi if l_year_gan else "",
                  "month": l_month, "day": l_day, "leap": l_leap},
        "ming_gong": {"zhi": palaces[0]["zhi"], "name": "命宫"},
        "shen_gong": {"zhi": ZHI[shen], "name": "身宫"},
        "wuxing_ju": JU_NAMES.get(ju) if ju else "",
        "ziwei_pos": ZHI[ziwei_pos] if ziwei_pos is not None else "",
        "palaces": [
            {"name": p["name"], "ganzhi": p["gan"] + p["zhi"],
             "stars": star_map[(ming - i) % 12]}
            for i, p in enumerate(palaces)
        ],
        "sihua": {k: [ZHI[i] for i in v] for k, v in sihua_flags.items()},
        "gaps": gaps,
    }
