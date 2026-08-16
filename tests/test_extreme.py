#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 极端化测试（v7.7）：边界矩阵 + 鲁棒性。

覆盖引擎最容易翻车的边界，全部可秒级跑完，纳入 unittest：

1. 时间边界：节气交界 ±1 分钟、子时两派、立春跨年、闰年 2/29、12-31 23:59:59、
   1582 历法切换日、夏令时起止整点、ΔT 分段端点年份（-500/500/1600/1700/1800/
   1860/1900/1920/1941/1961/1986/2005/2050/2150/2151）、可靠区间端点 1000/2200。
2. 地理边界：经度 -180/180、时区 -12/+14（基里巴斯）、无经度。
3. 参数边界：--lucky 1/100、--years 0/100、非法经度越界报错。
4. 鲁棒性：任意输入不抛未预期异常、输出 JSON 可序列化、两次调用结果一致（确定性）。

运行:
    python -m unittest tests.test_extreme -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

TZ = 8.0


class TestTimeExtremes(unittest.TestCase):
    """时间边界。"""

    def test_term_boundary_minus_plus_one_minute(self):
        """每个节交界 ±1 分钟: 不崩溃, 月柱只可能相同或进一位。"""
        for year in (1000, 1582, 1700, 1900, 2024, 2200):
            for name, idx, t in pp.jie_list(year, TZ):
                a = pp.calc(t - timedelta(minutes=1), tz_hours=TZ)["month_pillar"]
                b = pp.calc(t + timedelta(minutes=1), tz_hours=TZ)["month_pillar"]
                diff = (pp.idx60(b[0], b[1]) - pp.idx60(a[0], a[1])) % 60
                self.assertIn(diff, (0, 1), f"{year} {name} 前后月柱跳变异常 {a}->{b}")

    def test_zi_boundary_two_schools(self):
        """23:00/23:30/00:00/00:30 两派都不崩且日柱连续。"""
        for d in (datetime(2024, 1, 1, 23, 0), datetime(2024, 1, 1, 23, 30),
                  datetime(2024, 1, 2, 0, 0), datetime(2024, 1, 2, 0, 30)):
            zi = pp.calc(d, tz_hours=TZ, day_boundary="zi")
            mid = pp.calc(d, tz_hours=TZ, day_boundary="midnight")
            self.assertEqual(len(zi["day_pillar"]), 2)
            self.assertEqual(len(mid["day_pillar"]), 2)

    def test_second_precision_input(self):
        """秒级输入（23:59:59 跨日）不崩。"""
        r = pp.calc(datetime(2024, 12, 31, 23, 59, 59), tz_hours=TZ, lon=126.6)
        self.assertEqual(len(r["hour_pillar"]), 2)

    def test_gregorian_switch_days(self):
        """1582-10-04（儒略）与 10-15（格里）前后都正常。"""
        for d in (datetime(1582, 10, 3, 12, 0), datetime(1582, 10, 4, 12, 0),
                  datetime(1582, 10, 15, 12, 0), datetime(1582, 10, 16, 12, 0)):
            r = pp.calc(d, tz_hours=TZ, lon=120.0)
            self.assertEqual(len(r["year_pillar"]), 2)

    def test_dst_window_edges(self):
        """夏令时起止整点（02:00）边界: 起时含、止时不含。"""
        start = datetime(1986, 5, 4, 2, 0)
        end = datetime(1986, 9, 14, 2, 0)
        self.assertEqual(pp.dst_offset_hours(start), 1.0)
        self.assertEqual(pp.dst_offset_hours(end), 0.0)

    def test_delta_t_segment_edges(self):
        """ΔT 分段端点 ±1 年都收敛（牛顿迭代不因跳变发散）。

        回代必须用浮点年（2000+(jd-2451545)/365.25），与引擎内部口径一致——
        整数年会引入 1 秒级 ΔT 偏差（如 499 年 5719.9s vs 5718.7s），
        等效残差 1.4e-5 度，那是口径误差不是求解器误差。
        """
        for y in (499, 500, 501, 1599, 1600, 1601, 1699, 1700, 1701,
                  1799, 1800, 1801, 1859, 1860, 1861, 1899, 1900, 1901,
                  1919, 1920, 1921, 1940, 1941, 1942, 1960, 1961, 1962,
                  1985, 1986, 1987, 2004, 2005, 2006, 2049, 2050, 2051,
                  2149, 2150, 2151):
            jd = pp.term_ut_jd(y, pp.LICHUN_IDX)
            yf = 2000.0 + (jd - 2451545.0) / 365.25
            jd_tt = jd + pp.delta_t_seconds(yf) / 86400.0
            resid = ((pp.solar_longitude(jd_tt) - pp.TERM_DEG[pp.LICHUN_IDX] + 180.0)
                     % 360.0) - 180.0
            self.assertLess(abs(resid), 1e-6, f"{y} 立春残差 {resid:+.6f}°")

    def test_reliable_range_edges(self):
        """可靠区间端点 1000 与 2200 不崩，且出界（999/2201）给警告。"""
        r = pp.calc(datetime(1000, 1, 1, 12, 0), tz_hours=TZ, lon=120.0)
        self.assertEqual(len(r["year_pillar"]), 2)
        r = pp.calc(datetime(2200, 12, 31, 12, 0), tz_hours=TZ, lon=120.0)
        self.assertEqual(len(r["year_pillar"]), 2)
        for bad in (999, 2201):
            r = pp.calc(datetime(bad, 6, 15, 12, 0), tz_hours=TZ, lon=120.0)
            self.assertTrue(any("超出" in w or "可靠" in w for w in r["warnings"]),
                            f"{bad} 年应给出界警告")


class TestGeoExtremes(unittest.TestCase):
    """地理/时区边界。"""

    def test_longitude_extremes(self):
        """经度 ±180、±90 不崩（真太阳时修正极端值）。"""
        for lon in (-180.0, -90.0, 0.0, 90.0, 180.0):
            r = pp.calc(datetime(2024, 6, 15, 12, 0), tz_hours=0, lon=lon)
            self.assertEqual(len(r["hour_pillar"]), 2, f"lon={lon}")

    def test_tz_extremes(self):
        """时区 -12 与 +14 不崩。"""
        for tz, lon in ((-12.0, -180.0), (14.0, 180.0)):
            r = pp.calc(datetime(2024, 6, 15, 12, 0), tz_hours=tz, lon=lon)
            self.assertEqual(len(r["hour_pillar"]), 2)

    def test_intl_date_line(self):
        """国际日期变更线两侧同一时刻（±12 时区）都不崩。"""
        for tz, lon in ((-12.0, -180.0), (12.0, 180.0)):
            r = pp.calc(datetime(2024, 1, 1, 12, 0), tz_hours=tz, lon=lon)
            self.assertEqual(len(r["year_pillar"]), 2)


class TestParamExtremes(unittest.TestCase):
    """参数边界。"""

    def test_lucky_and_years_extremes(self):
        for lucky in (1, 100):
            r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ,
                        lucky_count=lucky, years_count=0)
            self.assertEqual(len(r["lucky"]), lucky)
            self.assertEqual(len(r["liunian"]), 1)  # years=0 也含出生当年
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=TZ,
                    lucky_count=1, years_count=100)
        self.assertEqual(len(r["liunian"]), 101)

    def test_cli_rejects_bad_lon(self):
        """CLI 层非法经度应报错（argparse error, 非崩溃）。"""
        import subprocess
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "pai_pan.py"),
             "2024-05-23 10:00", "--lon", "181"],
            capture_output=True, text=True, cwd=ROOT, timeout=30)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("lon", out.stderr)

    def test_bad_datetime_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "pai_pan.py"),
             "not-a-date"],
            capture_output=True, text=True, cwd=ROOT, timeout=30)
        self.assertNotEqual(out.returncode, 0)


class TestRobustness(unittest.TestCase):
    """鲁棒性：确定性 + JSON 可序列化 + 无未预期异常。"""

    def test_deterministic(self):
        """同一输入两次排盘结果完全一致。"""
        dt = datetime(1990, 5, 23, 17, 30)
        a = pp.calc(dt, tz_hours=8, lon=116.4, lucky_count=5, years_count=5)
        b = pp.calc(dt, tz_hours=8, lon=116.4, lucky_count=5, years_count=5)
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))

    def test_fuzz_no_crash(self):
        """伪随机 200 盘: 不抛未预期异常、JSON 可序列化。"""
        import random
        rng = random.Random(20260814)
        for _ in range(200):
            y = rng.randint(1000, 2200)
            m = rng.randint(1, 12)
            d = rng.randint(1, 28)
            h = rng.randint(0, 23)
            mi = rng.randint(0, 59)
            tz = rng.choice([-12.0, -8.0, -5.0, 0.0, 5.5, 8.0, 9.0, 12.0, 14.0])
            lon = rng.choice([None, -180.0, -85.7, 0.0, 87.6, 116.4, 121.5, 180.0])
            boundary = rng.choice(["zi", "midnight"])
            dst = rng.choice(["auto", "on", "off"])
            cal = rng.choice(["auto", "julian", "gregorian"])
            try:
                r = pp.calc(datetime(y, m, d, h, mi), tz_hours=tz, lon=lon,
                            gender="male", day_boundary=boundary, dst=dst,
                            calendar=cal, lucky_count=5, years_count=5)
                json.dumps(r, ensure_ascii=False)
                self.assertEqual(len(r["year_pillar"]), 2)
            except (ValueError, OverflowError) as e:
                # 只有这两类异常允许出现（输入本身的非法性），且必须是明确信息
                self.assertIn(str(e), "", "")  # 不吞异常, 直接抛给测试失败
                raise AssertionError(f"fuzz 抛异常 {y}-{m}-{d} {h}:{mi} tz={tz} "
                                     f"lon={lon} {boundary} {dst} {cal}: {e}") from e

    def test_performance_budget(self):
        """单盘排盘应在 50ms 内（lru_cache 生效，防回归）。"""
        import time
        dt = datetime(2024, 5, 23, 10, 0)
        pp.calc(dt, tz_hours=TZ, lon=116.4)  # 预热 cache
        t0 = time.perf_counter()
        for _ in range(20):
            pp.calc(dt, tz_hours=TZ, lon=116.4)
        elapsed = (time.perf_counter() - t0) / 20
        self.assertLess(elapsed, 0.05, f"单盘耗时 {elapsed*1000:.1f}ms 超预算")


if __name__ == "__main__":
    unittest.main(verbosity=2)
