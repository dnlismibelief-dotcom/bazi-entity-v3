#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 排盘不变量测试。

设计原则
--------
本文件只测**不变量**（invariants）与**自校验**，不内置"权威万年历答案"——
凭记忆写死节气时刻本身就是不可靠的数据源，反而会把错误固化成测试。

其中最有力的一条是 test_terms_hit_target_longitude：拿算出的节气时刻回代
太阳黄经公式，检查是否真的落在目标黄经上。这不需要任何外部数据，却能抓出
求根、ΔT、时区换算的绝大多数错误。

绝对精度校验（对齐紫金山天文台/权威万年历）请填 tests/fixtures.csv，
本文件会自动读取；文件为空则相关测试跳过。

运行:
    python -m unittest discover -s tests -v
    python tests/test_pai_pan.py
"""

from __future__ import annotations

import csv
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "scripts", "pai_pan.py")

spec = importlib.util.spec_from_file_location("pai_pan", SCRIPT)
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

TZ = 8.0
FIXTURES = os.path.join(HERE, "fixtures.csv")


class TestGanZhiAlgebra(unittest.TestCase):
    """60 甲子、十神、长生这些纯代数部分。"""

    def test_pillar60_roundtrip(self):
        seen = set()
        for n in range(60):
            gz = pp.pillar60(n)
            self.assertEqual(pp.idx60(gz[0], gz[1]), n)
            seen.add(gz)
        self.assertEqual(len(seen), 60, "60 甲子应有 60 个不重复组合")

    def test_invalid_pillar_rejected(self):
        # 甲丑不存在（阳干只配阳支）
        with self.assertRaises(ValueError):
            pp.idx60("甲", "丑")

    def test_shishen_self_is_bijian(self):
        for g in pp.GAN:
            self.assertEqual(pp.shishen(g, g), "比肩")

    def test_shishen_covers_ten(self):
        got = {pp.shishen("甲", o) for o in pp.GAN}
        self.assertEqual(len(got), 10, "日干甲对十天干应产生 10 种十神")

    def test_changsheng_cycle_is_12(self):
        for g in pp.GAN:
            got = {pp.changsheng_pos(g, z) for z in pp.ZHI}
            self.assertEqual(len(got), 12, f"{g} 的十二长生应覆盖 12 位")

    def test_wuhu_wushu_rules(self):
        # 五虎遁: 甲己之年丙作首
        self.assertEqual(pp.GAN[pp.WUHU["甲"]], "丙")
        self.assertEqual(pp.GAN[pp.WUHU["己"]], "丙")
        self.assertEqual(pp.GAN[pp.WUHU["戊"]], "甲")
        # 五鼠遁: 甲己还加甲, 戊癸壬子居
        self.assertEqual(pp.GAN[pp.WUSHU["甲"]], "甲")
        self.assertEqual(pp.GAN[pp.WUSHU["癸"]], "壬")


class TestAstronomy(unittest.TestCase):
    """天文部分的自校验。"""

    def test_terms_hit_target_longitude(self):
        """核心自校验: 算出的节气时刻回代黄经公式应命中目标黄经。"""
        for year in (1901, 1950, 1988, 2000, 2024, 2050, 2099):
            for idx in range(24):
                jd_ut = pp.term_ut_jd(year, idx)
                y = 2000.0 + (jd_ut - 2451545.0) / 365.25
                jd_tt = jd_ut + pp.delta_t_seconds(y) / 86400.0
                lon = pp.solar_longitude(jd_tt)
                target = pp.TERM_DEG[idx]
                diff = abs(((lon - target + 180.0) % 360.0) - 180.0)
                # 求根收敛到 1e-6 度以内（约 0.09 秒）
                self.assertLess(diff, 1e-4,
                                f"{year} {pp.TERM_NAME[idx]} 黄经偏差 {diff:.2e}°")

    def test_terms_monotonic_within_year(self):
        for year in (1960, 2024, 2088):
            times = [pp.term_local(year, i, TZ) for i in range(24)]
            for a, b in zip(times, times[1:]):
                self.assertLess(a, b, f"{year} 节气时刻应单调递增")

    def test_term_spacing_reasonable(self):
        """相邻节气间隔应在 14—16.5 天之间。"""
        for year in (1930, 2024, 2075):
            times = [pp.term_local(year, i, TZ) for i in range(24)]
            for a, b in zip(times, times[1:]):
                gap = (b - a).total_seconds() / 86400.0
                self.assertTrue(14.0 < gap < 16.5, f"{year} 节气间隔异常: {gap:.2f} 天")

    def test_lichun_falls_in_february(self):
        for year in range(1950, 2101, 7):
            lc = pp.term_local(year, pp.LICHUN_IDX, TZ)
            self.assertEqual(lc.year, year)
            self.assertIn(lc.month, (2,), f"{year} 立春应在 2 月, 实际 {lc}")
            self.assertIn(lc.day, (3, 4, 5), f"{year} 立春日应为 3—5 日, 实际 {lc}")

    def test_dongzhi_falls_in_december(self):
        for year in range(1950, 2101, 11):
            dz = pp.term_local(year, 23, TZ)
            self.assertEqual(dz.month, 12)
            self.assertIn(dz.day, (20, 21, 22, 23))

    def test_equation_of_time_range(self):
        """均时差全年应落在 ±17 分钟内, 且过零点约 4 次。"""
        vals = []
        for d in range(0, 366, 3):
            dt = datetime(2024, 1, 1) + timedelta(days=d)
            jd = pp.jd_from_gregorian(dt.year, dt.month, dt.day, 12.0)
            vals.append(pp.equation_of_time(jd))
        self.assertLess(max(vals), 17.0)
        self.assertGreater(min(vals), -17.0)
        signs = [1 if v > 0 else -1 for v in vals]
        crossings = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
        self.assertGreaterEqual(crossings, 3, "均时差一年应有约 4 次过零")

    def test_delta_t_reasonable(self):
        self.assertTrue(50 < pp.delta_t_seconds(2000) < 80)
        self.assertTrue(60 < pp.delta_t_seconds(2024) < 90)
        # 1900 年前后 ΔT 接近 0（历史真值约 -2.8 秒）
        self.assertTrue(-6 < pp.delta_t_seconds(1900) < 6)
        self.assertTrue(20 < pp.delta_t_seconds(1930) < 30)

    def test_jd_datetime_roundtrip(self):
        for dt in (datetime(1901, 3, 4, 5, 6, 7), datetime(2024, 5, 23, 10, 0, 0),
                   datetime(2099, 12, 31, 23, 59, 59)):
            jd = pp.jd_from_gregorian(dt.year, dt.month, dt.day,
                                      dt.hour + dt.minute / 60 + dt.second / 3600)
            back = pp.jd_to_datetime(jd)
            self.assertLessEqual(abs((back - dt).total_seconds()), 1.0,
                                 f"儒略日往返误差过大: {dt} -> {back}")


class TestTimeCorrections(unittest.TestCase):
    """真太阳时与夏令时。"""

    def test_longitude_15deg_equals_one_hour(self):
        """经度每 15° 对应 1 小时。"""
        dt = datetime(2024, 3, 20, 12, 0)
        a, da = pp.to_true_solar(dt, TZ, 120.0)
        b, db = pp.to_true_solar(dt, TZ, 135.0)
        self.assertAlmostEqual((b - a).total_seconds() / 3600.0, 1.0, places=3)

    def test_no_lon_means_no_change(self):
        dt = datetime(2024, 3, 20, 12, 0)
        out, detail = pp.to_true_solar(dt, TZ, None)
        self.assertEqual(out, dt)
        self.assertFalse(detail["applied"])

    def test_central_meridian_only_eot(self):
        """位于时区中央经线时, 修正量应只剩均时差。"""
        dt = datetime(2024, 8, 1, 12, 0)
        out, detail = pp.to_true_solar(dt, TZ, 120.0)
        self.assertAlmostEqual(detail["lon_correction_min"], 0.0, places=6)
        self.assertAlmostEqual((out - dt).total_seconds() / 60.0,
                               detail["eot_min"], places=3)

    def test_dst_window(self):
        self.assertEqual(pp.dst_offset_hours(datetime(1988, 7, 1, 12)), 1.0)
        self.assertEqual(pp.dst_offset_hours(datetime(1988, 3, 1, 12)), 0.0)
        self.assertEqual(pp.dst_offset_hours(datetime(1992, 7, 1, 12)), 0.0)
        self.assertEqual(pp.dst_offset_hours(datetime(1985, 7, 1, 12)), 0.0)

    def test_dst_manual_override(self):
        d = datetime(1988, 7, 1, 12)
        self.assertEqual(pp.dst_offset_hours(d, "off"), 0.0)
        self.assertEqual(pp.dst_offset_hours(datetime(2024, 7, 1, 12), "on"), 1.0)

    def test_urumqi_shanghai_differ(self):
        """同一钟表时刻, 乌鲁木齐与上海真太阳时相差约 2 小时 15 分。"""
        dt = datetime(2000, 6, 15, 7, 30)
        a, _ = pp.to_true_solar(dt, TZ, 87.6)
        b, _ = pp.to_true_solar(dt, TZ, 121.5)
        gap = (b - a).total_seconds() / 60.0
        self.assertTrue(130 < gap < 140, f"两地真太阳时差 {gap:.1f} 分, 应约 135 分")


class TestDateHelpers(unittest.TestCase):

    def test_add_months_keeps_day(self):
        """v4 的 min(day,28) bug: 31 日不应被压成 28 日。"""
        got = pp.add_months(datetime(2024, 1, 31, 10, 0), 2)
        self.assertEqual((got.year, got.month), (2024, 3))
        self.assertEqual(got.day, 31)

    def test_add_months_overflow_backs_off(self):
        got = pp.add_months(datetime(2024, 1, 31, 10, 0), 1)  # 2 月无 31 日
        self.assertEqual((got.year, got.month, got.day), (2024, 2, 29))

    def test_add_months_crosses_year(self):
        got = pp.add_months(datetime(2024, 11, 15, 0, 0), 3)
        self.assertEqual((got.year, got.month, got.day), (2025, 2, 15))

    def test_format_delta_three_days_one_year(self):
        self.assertEqual(pp.format_delta(3.0), "1年0个月")
        self.assertEqual(pp.format_delta(0.0), "0年0个月")
        # 3 天折 1 年, 余 1.5 天 × 4 = 6 个月
        self.assertEqual(pp.format_delta(4.5), "1年6个月")
        self.assertEqual(pp.format_delta(0.75), "0年3个月")


class TestChartInvariants(unittest.TestCase):
    """整盘层面的不变量。"""

    def test_known_regression_mingchao(self):
        """回归锚: 鸣潮公测盘（与 v3/v4 输出一致, 防止重构跑偏）。"""
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ)
        self.assertEqual(r["year_pillar"], "甲辰")
        self.assertEqual(r["month_pillar"], "己巳")
        self.assertEqual(r["day_pillar"], "丁亥")
        self.assertEqual(r["hour_pillar"], "乙巳")

    def test_year_pillar_switches_at_lichun(self):
        for year in (1975, 2024, 2077):
            lc = pp.term_local(year, pp.LICHUN_IDX, TZ)
            before = pp.calc(lc - timedelta(minutes=2), tz_hours=TZ)["year_pillar"]
            after = pp.calc(lc + timedelta(minutes=2), tz_hours=TZ)["year_pillar"]
            self.assertNotEqual(before, after, f"{year} 立春前后年柱应改变")
            self.assertEqual(
                pp.idx60(after[0], after[1]),
                (pp.idx60(before[0], before[1]) + 1) % 60,
                "立春后年柱应恰好进一位")

    def test_month_pillar_switches_at_jie(self):
        """每个节的前后, 月柱应恰好进一位。"""
        jies = pp.jie_list(2024, TZ)
        for name, idx, t in jies:
            a = pp.calc(t - timedelta(minutes=2), tz_hours=TZ)["month_pillar"]
            b = pp.calc(t + timedelta(minutes=2), tz_hours=TZ)["month_pillar"]
            self.assertEqual(pp.idx60(b[0], b[1]),
                             (pp.idx60(a[0], a[1]) + 1) % 60,
                             f"{name} 前后月柱未进一位: {a} -> {b}")

    def test_day_pillar_advances_daily(self):
        base = datetime(2024, 5, 23, 10, 0)
        prev = pp.calc(base, tz_hours=TZ)["day_pillar"]
        for k in range(1, 40):
            cur = pp.calc(base + timedelta(days=k), tz_hours=TZ)["day_pillar"]
            self.assertEqual(pp.idx60(cur[0], cur[1]),
                             (pp.idx60(prev[0], prev[1]) + 1) % 60)
            prev = cur

    def test_day_boundary_zi_vs_midnight(self):
        d = datetime(2024, 5, 23, 23, 30)
        zi = pp.calc(d, tz_hours=TZ, day_boundary="zi")
        mid = pp.calc(d, tz_hours=TZ, day_boundary="midnight")
        self.assertEqual(pp.idx60(zi["day_pillar"][0], zi["day_pillar"][1]),
                         (pp.idx60(mid["day_pillar"][0], mid["day_pillar"][1]) + 1) % 60,
                         "23:30 时子初换日派应比子正派多一日")
        self.assertEqual(zi["day_pillar_alt"], mid["day_pillar"],
                         "并列输出的另一派日柱应与实际切换结果一致")

    def test_day_boundary_no_diff_at_noon(self):
        r = pp.calc(datetime(2024, 5, 23, 12, 0), tz_hours=TZ)
        self.assertIsNone(r["day_pillar_alt"], "非子时两派应无分歧")

    def test_hour_zhi_mapping(self):
        """时支: 23—01 子, 01—03 丑 ... 11—13 午。"""
        expect = {23: "子", 0: "子", 1: "丑", 2: "丑", 11: "午", 12: "午", 13: "未"}
        for hour, zhi in expect.items():
            r = pp.calc(datetime(2024, 5, 23, hour, 30), tz_hours=TZ)
            self.assertEqual(r["hour_pillar"][1], zhi, f"{hour} 时支应为 {zhi}")

    def test_liunian_uses_lichun(self):
        """流年干支须以立春分界（v4 的 bug 在此）。"""
        r = pp.calc(datetime(2026, 1, 20, 10, 0), tz_hours=TZ, years_count=1)
        # 2026-01-20 尚未立春, 年柱应是乙巳(2025)
        self.assertEqual(r["year_pillar"], "乙巳")
        first = r["liunian"][0]
        self.assertEqual(first["year"], 2026)
        self.assertEqual(first["ganzhi"], "丙午")
        self.assertTrue(first["lichun"].startswith("2026-02"))

    def test_dayun_direction_rules(self):
        # 甲辰年(阳)男 -> 顺排; 女 -> 逆排
        m = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, gender="male")
        f = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, gender="female")
        self.assertEqual(m["dayun_direction"], "顺排")
        self.assertEqual(f["dayun_direction"], "逆排")

    def test_dayun_sequence_is_contiguous(self):
        """大运干支必须逐位连续（旧文档曾漏掉辛未一步）。"""
        for gender, step in (("male", 1), ("female", -1)):
            r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ,
                        gender=gender, lucky_count=8)
            month_n = pp.idx60(r["month_pillar"][0], r["month_pillar"][1])
            for k, item in enumerate(r["lucky"]):
                want = (month_n + step * (k + 1)) % 60
                self.assertEqual(pp.idx60(item["ganzhi"][0], item["ganzhi"][1]), want,
                                 f"{gender} 第 {k+1} 步大运不连续: {item['ganzhi']}")

    def test_dayun_ten_year_spacing(self):
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lucky_count=5)
        ages = [x["age"] for x in r["lucky"]]
        for a, b in zip(ages, ages[1:]):
            self.assertAlmostEqual(b - a, 10.0, places=6)

    def test_taiyuan_two_schools(self):
        """胎元两派并列：鸣潮月柱己巳 → 进三位法庚申（主派）/ 300 日法己未（旁证）。"""
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=113.3)
        self.assertEqual(r["version"], "v7")
        self.assertEqual(r["month_pillar"], "己巳")
        ty = r["taiyuan"]
        self.assertEqual(ty["primary"], "庚申")
        self.assertEqual(ty["alt"], "己未")
        self.assertFalse(ty["agree"])

    def test_taiyuan_primary_is_month_pillar_shift(self):
        """主派必须严格等于"月干进一位、月支进三位"，随机抽若干盘核验。"""
        for dt in (datetime(1984, 5, 1, 19, 30), datetime(1990, 11, 3, 4, 20),
                   datetime(2001, 2, 20, 15, 0), datetime(2024, 5, 23, 10, 0)):
            r = pp.calc(dt, tz_hours=TZ, lon=116.4)
            mg, mz = r["month_pillar"][0], r["month_pillar"][1]
            want = (pp.GAN[(pp.GAN.index(mg) + 1) % 10]
                    + pp.ZHI[(pp.ZHI.index(mz) + 3) % 12])
            self.assertEqual(r["taiyuan"]["primary"], want, f"{dt} 月柱{mg}{mz}")

    def test_taiyuan_300days_keeps_clock_time(self):
        """300 日法必须保留出生时刻。

        2024 立夏 05-05 08:03；出生 2025-03-01 20:00 精确倒推 300 日 = 05-05 20:00，
        已过立夏，应落巳月。v6 把倒推起点截断成 00:00，会错判成上一个月（清明/辰月）。
        """
        r = pp.calc(datetime(2025, 3, 1, 20, 0), tz_hours=TZ, lon=120.0)
        self.assertEqual(r["taiyuan"]["jie"], "立夏")
        self.assertEqual(r["taiyuan"]["alt"], "己巳")

    def test_minggong_sanming_example(self):
        """命宫（三命通会例）：甲子年三月生戌时 → 命坐卯宫 → 丁卯。"""
        # 1984 甲子年 5 月 1 日 19:30：辰月（农历三月）、戌时
        r = pp.calc(datetime(1984, 5, 1, 19, 30), tz_hours=TZ, lon=116.4)
        self.assertEqual(r["year_pillar"], "甲子")
        self.assertEqual(r["month_pillar"], "戊辰")
        self.assertEqual(r["hour_pillar"], "丙戌")
        self.assertEqual(r["minggong"], "丁卯")

    def test_minggong_mingchao(self):
        """鸣潮 2024-05-23 巳时 → 命宫辛未（三命通会法）。"""
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=113.3)
        self.assertEqual(r["minggong"], "辛未")

    # ---- v7 修的三处：ΔT 适用年限 / 节气求解收敛 / 夏令时地域 ----

    def test_delta_t_historical_reference_values(self):
        """ΔT 分段必须覆盖古代。v6 只有 1900 基准式，1500 年算出 −63 天。

        参考值取 Espenak & Meeus 表；古代本身有不确定度，给 20 秒容差。
        """
        for year, want in ((1500, 198.0), (1600, 120.0), (1700, 8.83),
                           (1800, 13.72), (1860, 7.62), (1900, -2.79),
                           (2000, 63.87)):
            got = pp.delta_t_seconds(year)
            self.assertAlmostEqual(got, want, delta=20.0,
                                   msg=f"ΔT({year}) = {got:.2f}s, 期望 ≈{want}s")

    def test_delta_t_segments_continuous(self):
        """分段端点不得跳变 —— 跳变说明某段系数抄错了。"""
        for b in (500, 1600, 1700, 1800, 1860, 1900, 1920, 1941, 1961, 1986,
                  2005, 2050):
            left = pp.delta_t_seconds(b - 0.001)
            right = pp.delta_t_seconds(b)
            self.assertLess(abs(right - left), 2.0,
                            f"{b} 年边界跳变 {right - left:+.2f}s")

    def test_term_solver_converges_across_millennia(self):
        """节气时刻回代黄经必须命中目标。

        v6 的二分窗口只有 ±10 天，1680 年前目标点落在窗外时会把**初值**当结果返回
        （1500 与 1582 的节气时刻因此秒级完全相同），且不抛异常。
        """
        for year in (1200, 1400, 1500, 1582, 1650, 1700, 1800, 1900, 2024, 2100):
            for idx in (pp.LICHUN_IDX, 18):      # 立春 / 寒露
                jd = pp.term_ut_jd(year, idx)
                y = 2000.0 + (jd - 2451545.0) / 365.25
                jd_tt = jd + pp.delta_t_seconds(y) / 86400.0
                resid = ((pp.solar_longitude(jd_tt) - pp.TERM_DEG[idx] + 180.0)
                         % 360.0) - 180.0
                self.assertLess(abs(resid), 1e-6,
                                f"{year} 年 {pp.TERM_NAME[idx]} 残差 {resid:+.6f}°")

    def test_term_times_differ_across_years(self):
        """同一节气在不同年份的时刻不该完全相同 —— 相同就是退化成初值了。"""
        stamps = {pp.term_local(y, pp.LICHUN_IDX, 8.0).strftime("%H:%M:%S")
                  for y in (1400, 1500, 1582, 1650)}
        self.assertGreater(len(stamps), 1, f"立春时刻在多个古代年份完全相同: {stamps}")

    def test_cn_dst_only_applies_to_utc8(self):
        """中国夏令时表只能套东八区。1988-07-15 14:00 各地对比。"""
        cn = pp.calc(datetime(1988, 7, 15, 14, 0), tz_hours=8, lon=120.0)
        self.assertEqual(cn["solar_time"]["clock_time"], "1988-07-15 13:00:00")
        for tz, lon in ((9, 135.0), (-5, -75.0), (5.5, 82.5)):
            r = pp.calc(datetime(1988, 7, 15, 14, 0), tz_hours=tz, lon=lon)
            self.assertEqual(r["solar_time"]["clock_time"], "1988-07-15 14:00:00",
                             f"tz{tz:+g} 被错误套用了中国夏令时")

    def test_julian_input_normalized(self):
        """1582-10-15 之前默认按儒略历解释输入并换算成格里历。

        v6 把史料的儒略历日期当推算格里历用, 日柱差 9—10 天;
        且输入用格里历、jd_to_datetime 输出用儒略历, 两侧不一致。
        """
        r = pp.calc(datetime(1518, 7, 3, 12, 0), tz_hours=TZ, lon=120.0)
        self.assertEqual(r["input_raw"], "1518-07-03 12:00")
        self.assertEqual(r["input"], "1518-07-13 12:00")     # 1500s 差 10 天
        self.assertTrue(any("儒略历" in w for w in r["warnings"]))

    def test_calendar_gregorian_override(self):
        """--calendar gregorian 时不做换算 (给已经换算过的日期用)。"""
        r = pp.calc(datetime(1518, 7, 3, 12, 0), tz_hours=TZ, lon=120.0,
                    calendar="gregorian")
        self.assertEqual(r["input"], "1518-07-03 12:00")
        self.assertFalse(any("儒略历" in w for w in r["warnings"]))

    def test_ancient_years_do_not_crash(self):
        """公元 1000 年儒略历闰、格里历不闰, v6 会在 jd_to_datetime 抛
        "day is out of range for month"。"""
        for y in (800, 900, 1000, 1100, 1265):
            r = pp.calc(datetime(y, 6, 15, 12, 0), tz_hours=TZ, lon=120.0)
            self.assertEqual(len(r["year_pillar"]), 2)

    def test_dst_explicit_on_still_works(self):
        """非东八区若确知当年有夏令时, --dst on 仍要能回拨。"""
        r = pp.calc(datetime(1988, 7, 15, 14, 0), tz_hours=9, lon=135.0, dst="on")
        self.assertEqual(r["solar_time"]["clock_time"], "1988-07-15 13:00:00")

    def test_wuxing_counts_total(self):
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ)
        cang_total = sum(len(p["canggan"]) for p in r["pillars"])
        self.assertEqual(sum(r["wuxing_counts"].values()), 4 + cang_total)

    def test_nayin_pairs(self):
        """纳音 60 甲子两两共用, 共 30 个。"""
        got = {pp.NAYIN_30[pp.idx60(pp.pillar60(n)[0], pp.pillar60(n)[1]) // 2]
               for n in range(60)}
        self.assertEqual(len(got), 30)

    def test_warning_when_no_lon(self):
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ)
        self.assertTrue(any("lon" in w or "经度" in w for w in r["warnings"]))

    def test_no_warning_spam_with_lon(self):
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=116.4)
        self.assertFalse(any("经度" in w for w in r["warnings"]))

    def test_json_serialisable(self):
        import json
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ, lon=116.4)
        json.loads(json.dumps(r, ensure_ascii=False))

    def test_render_smoke(self):
        r = pp.calc(datetime(1988, 7, 1, 12, 0), tz_hours=TZ, lon=116.4)
        text = pp.render(r)
        for kw in ("四柱", "纳音", "大运", "流年"):
            self.assertIn(kw, text)


class TestFixtures(unittest.TestCase):
    """对齐权威万年历（tests/fixtures.csv）。空文件则跳过。"""

    def _rows(self):
        if not os.path.exists(FIXTURES):
            return []
        with open(FIXTURES, encoding="utf-8") as f:
            # 模板允许在表头前写注释行; 若直接交给 DictReader,
            # 首行注释会被当成 fieldnames, 导致永远读不到数据。
            lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            return []
        return [r for r in csv.DictReader(lines) if r.get("datetime")]

    def test_fixtures(self):
        rows = self._rows()
        if not rows:
            self.skipTest("tests/fixtures.csv 无数据；填入权威万年历样本后此测试才生效")
        for r in rows:
            dt = datetime.strptime(r["datetime"].strip(), "%Y-%m-%d %H:%M")
            kwargs = {"tz_hours": float(r.get("tz") or 8)}
            if r.get("lon"):
                kwargs["lon"] = float(r["lon"])
            if r.get("day_boundary"):
                kwargs["day_boundary"] = r["day_boundary"].strip()
            got = pp.calc(dt, **kwargs)
            want = " ".join(x for x in [r.get("year_pillar"), r.get("month_pillar"),
                                        r.get("day_pillar"), r.get("hour_pillar")] if x)
            actual = " ".join([got["year_pillar"], got["month_pillar"],
                               got["day_pillar"], got["hour_pillar"]])
            self.assertEqual(actual.strip(), want.strip(),
                             f"{r['datetime']} 排盘与权威数据不符（来源: {r.get('source','')}）")


class TestCompareCharts(unittest.TestCase):
    """两盘对比工具（v7.1 新增）：同盘异命分析。"""

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "compare_charts", os.path.join(ROOT, "scripts", "compare_charts.py"))
        cc = importlib.util.module_from_spec(spec)
        sys.modules["compare_charts"] = cc
        spec.loader.exec_module(cc)
        return cc

    def test_lincoln_darwin_same_pillars_different_jiao(self):
        """林肯/达尔文（同日正午占位）：四柱相同、大运序列相同、交运日差 33 天。"""
        cc = self._load()
        r = cc.compare(
            {"dt": "1809-02-12 12:00", "tz": -6.0, "lon": -85.7},
            {"dt": "1809-02-12 12:00", "tz": 0.0, "lon": -2.8},
        )
        self.assertTrue(r["same_four_pillars"])
        self.assertTrue(r["same_lucky"])
        self.assertEqual(r["jiao_time_diff_days"], 33)

    def test_sensitivity_reveals_hour_dependence(self):
        """同一日期不同钟表时刻会改变四柱：占位时辰不可当作真实盘。"""
        cc = self._load()
        s = cc.sensitivity({"dt": "1809-02-12 12:00", "tz": -6.0, "lon": -85.7})
        self.assertGreater(s["distinct_charts"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
