#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紫微排盘引擎测试 — BFFT v7.17.

覆盖：农历转换锚点、命宫/身宫规则、五行局、紫微五局定位、
十四主星互斥与紫微天府轴对称、四化标注正确性、范围外提示。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location(
    "zw", os.path.join(ROOT, "scripts", "ziwei", "paipan.py"))
_zw = importlib.util.module_from_spec(_spec)
sys.modules["zw"] = _zw
_spec.loader.exec_module(_zw)


class TestLunarConversion(unittest.TestCase):
    def test_2025_newyear(self):
        self.assertEqual(_zw._solar_to_lunar(2025, 1, 29), (2025, 1, 1, False))

    def test_2025_month_end(self):
        self.assertEqual(_zw._solar_to_lunar(2025, 2, 27), (2025, 1, 30, False))

    def test_out_of_range_none(self):
        self.assertIsNone(_zw._solar_to_lunar(1990, 1, 1))


class TestMingShenGong(unittest.TestCase):
    def test_ming_shen_rule(self):
        """命宫=月宫逆数至时; 身宫=月宫顺数至时; 两宫相对月宫对称。"""
        r = _zw.ziwei_calc(2025, 1, 29, 12)  # 正月 午时
        month_palace = 2  # 寅起正月
        shi = _zw.ZHI.index(_zw.ZHI[((12 + 1) // 2) % 12])
        ming = (month_palace - shi) % 12
        shen = (month_palace + shi) % 12
        self.assertEqual(r["ming_gong"]["zhi"], _zw.ZHI[ming])
        self.assertEqual(r["shen_gong"]["zhi"], _zw.ZHI[shen])
        # 命身与月宫对称
        self.assertEqual((ming + shen) % 12, (2 * month_palace) % 12)


class TestWuxingJuAndZiwei(unittest.TestCase):
    def test_ju_by_ming_gong_nayin(self):
        # 甲申命宫=泉中水? 甲申纳音"泉中水"->水二局
        r = _zw.ziwei_calc(2025, 1, 29, 12)
        self.assertEqual(r["wuxing_ju"], "水二局")
        self.assertEqual(r["ziwei_pos"], "寅")  # 水二局 生日1 -> 寅

    def test_ziwei_five_ju_start(self):
        # 各局生日 1 的紫微起始宫：水寅 木辰 金亥 土午 火酉
        expect = {2: "寅", 3: "辰", 4: "亥", 5: "午", 6: "酉"}
        for ju, start in expect.items():
            self.assertEqual(_zw.ZHI[_zw.JU_START[ju]], start)


class TestStars(unittest.TestCase):
    def test_fourteen_major_stars_all_placed(self):
        r = _zw.ziwei_calc(2025, 1, 29, 12)
        all_stars = [s for p in r["palaces"] for s in p["stars"]]
        majors = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞",
                  "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"]
        for m in majors:
            self.assertEqual(all_stars.count(m), 1, f"{m} 应恰好一颗")

    def test_majors_exactly_once_each(self):
        """十四主星各恰一颗（主星可同宫是常态: 紫杀/武杀等经典组合）。"""
        for d in range(1, 28):
            r = _zw.ziwei_calc(2025, 2, d, 8)
            majors = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞",
                      "天府", "太阴", "贪狼", "巨门", "天相", "天梁",
                      "七杀", "破军"]
            all_stars = [s for p in r["palaces"] for s in p["stars"]]
            for m in majors:
                self.assertEqual(all_stars.count(m), 1,
                                 f"d={d} {m} 应恰好一颗")

    def test_ziwei_tianfu_axis(self):
        """紫微与天府以寅申线轴对称。"""
        for d in range(1, 28):
            r = _zw.ziwei_calc(2025, 2, d, 8)
            zw_pos = _zw.ZHI.index(r["ziwei_pos"])
            tf_palace = next(p for p in r["palaces"] if "天府" in p["stars"])
            tf_pos = _zw.ZHI.index(tf_palace["ganzhi"][1])
            self.assertEqual((zw_pos + tf_pos) % 12, 10, "寅(2)+申(8)=10")


class TestSihua(unittest.TestCase):
    def test_yi_year_sihua(self):
        # 乙年: 禄天机 权天梁 科紫微 忌太阴（落在对应星所在宫）
        r = _zw.ziwei_calc(2025, 1, 29, 12)
        star_pos = {}
        for p in r["palaces"]:
            for s in p["stars"]:
                star_pos[s] = p["ganzhi"][1]
        self.assertEqual(r["sihua"]["禄"][0], star_pos["天机"])
        self.assertEqual(r["sihua"]["权"][0], star_pos["天梁"])
        self.assertEqual(r["sihua"]["科"][0], star_pos["紫微"])
        self.assertEqual(r["sihua"]["忌"][0], star_pos["太阴"])


class TestRangeGuard(unittest.TestCase):
    def test_out_of_range_gap(self):
        r = _zw.ziwei_calc(1990, 1, 1, 10)
        self.assertTrue(r["gaps"])
        self.assertEqual(r["lunar"]["year"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
