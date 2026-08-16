#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整干支关系表穷举测试 — BFFT v7.12.

关系表整合自四家外部仓库对照（china-testing/bazi、reed1898/bazi-tool、
openfate-ai/bazi-engine、yueyuan-bazi）与《三命通会》卷二。
本测试把 66 地支对、10 天干对逐对核对，防止表项遗漏/失配
（v7.9 教训：Unicode 排序失配让 7/66 对静默失效）。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "scripts", "pai_pan.py")

spec = importlib.util.spec_from_file_location("pai_pan", SCRIPT)
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"


def pair_set(table: dict) -> set:
    """表键归一化：键如 '子丑'，取无序对集合。"""
    return {frozenset(k) for k in table}


class TestGanRelations(unittest.TestCase):
    def test_gan_he_all_five(self):
        want = {frozenset("甲己"), frozenset("乙庚"), frozenset("丙辛"),
                frozenset("丁壬"), frozenset("戊癸")}
        self.assertEqual(pair_set(pp.GAN_HE), want)

    def test_gan_chong_all_four(self):
        want = {frozenset("甲庚"), frozenset("乙辛"),
                frozenset("丙壬"), frozenset("丁癸")}
        self.assertEqual(pair_set(pp.GAN_CHONG), want)

    def test_gan_he_and_chong_no_overlap(self):
        self.assertFalse(pair_set(pp.GAN_HE) & pair_set(pp.GAN_CHONG))

    def test_gan_pairs_10x10(self):
        """10 干两两对：同干返回'同干'，其余至少返回一个标签。"""
        for a in GAN:
            for b in GAN:
                rel = pp.gan_pair_relations(a, b)
                self.assertIsInstance(rel, list)
                self.assertTrue(rel, f"{a}{b} 应返回标签")
                if a == b:
                    self.assertEqual(rel, ["同干"])

    def test_gan_key_cases(self):
        self.assertEqual(pp.gan_pair_relations("甲", "己"), ["甲己合土"])
        self.assertEqual(pp.gan_pair_relations("甲", "庚"), ["甲庚冲"])
        self.assertEqual(pp.gan_pair_relations("乙", "庚"), ["乙庚合金"])
        self.assertEqual(pp.gan_pair_relations("乙", "辛"), ["乙辛冲"])
        self.assertEqual(pp.gan_pair_relations("丙", "丁"), ["静"])


class TestZhiRelations(unittest.TestCase):
    def test_liuhe_six(self):
        want = {frozenset("子丑"), frozenset("寅亥"), frozenset("卯戌"),
                frozenset("辰酉"), frozenset("巳申"), frozenset("午未")}
        self.assertEqual(pair_set(pp.ZHI_LIUHE), want)

    def test_liuchong_six(self):
        want = {frozenset("子午"), frozenset("丑未"), frozenset("寅申"),
                frozenset("卯酉"), frozenset("辰戌"), frozenset("巳亥")}
        self.assertEqual(pair_set(pp.ZHI_LIUCHONG), want)

    def test_liuhai_six(self):
        want = {frozenset("子未"), frozenset("丑午"), frozenset("寅巳"),
                frozenset("卯辰"), frozenset("申亥"), frozenset("酉戌")}
        self.assertEqual(pair_set(pp.ZHI_LIUHAI), want)

    def test_sanhe_four(self):
        self.assertEqual(len(pp.ZHI_SANHE), 4)
        self.assertEqual(pp.ZHI_SANHE["申子辰"], "申子辰合水局")
        self.assertEqual(pp.ZHI_SANHE["亥卯未"], "亥卯未合木局")
        self.assertEqual(pp.ZHI_SANHE["寅午戌"], "寅午戌合火局")
        self.assertEqual(pp.ZHI_SANHE["巳酉丑"], "巳酉丑合金局")

    def test_banhe_twelve(self):
        # 每局三对：两生旺半合 + 一拱
        self.assertEqual(len(pp.ZHI_BANHE), 12)

    def test_xing_seven(self):
        want = {frozenset("寅巳"), frozenset("巳申"), frozenset("寅申"),
                frozenset("丑戌"), frozenset("戌未"), frozenset("丑未"),
                frozenset("子卯")}
        self.assertEqual(pair_set(pp.ZHI_XING), want)

    def test_zixing_four(self):
        self.assertEqual(pp.ZHI_ZIXING, {"辰", "午", "酉", "亥"})

    def test_po_four_plus_hezhong(self):
        want = {frozenset("子酉"), frozenset("午卯"),
                frozenset("辰丑"), frozenset("戌未")}
        self.assertEqual(pair_set(pp.ZHI_PO), want)

    def test_zhi_66_exhaustive_no_silent_failure(self):
        """66 地支对穷举：每对必须有明确标签（合冲害刑破半合或静/伏吟）。"""
        for i in range(12):
            for j in range(i, 12):
                z1, z2 = ZHI[i], ZHI[j]
                rel = pp.zhi_pair_relations(z1, z2)
                self.assertTrue(rel, f"{z1}{z2} 空标签")
                if z1 == z2:
                    self.assertTrue(
                        rel[0] == "伏吟" or "自刑" in rel[0],
                        f"{z1}{z1} 应为伏吟或自刑")
        # 反向调用必须对称
        for i in range(12):
            for j in range(12):
                if i == j:
                    continue
                z1, z2 = ZHI[i], ZHI[j]
                a = pp.zhi_pair_relations(z1, z2)
                b = pp.zhi_pair_relations(z2, z1)
                self.assertEqual(a, b, f"{z1}{z2} 双向不对称")

    def test_zhi_key_cases(self):
        # 合中带破（巳申）、合中带刑（巳申）
        self.assertIn("巳申合水", pp.zhi_pair_relations("巳", "申"))
        self.assertIn("巳申刑", pp.zhi_pair_relations("巳", "申"))
        # 寅亥合中带破
        self.assertIn("寅亥合木", pp.zhi_pair_relations("寅", "亥"))
        # 子午冲
        self.assertEqual(pp.zhi_pair_relations("子", "午"), ["子午冲"])
        # 自刑 vs 伏吟
        self.assertEqual(pp.zhi_pair_relations("辰", "辰"), ["辰辰自刑"])
        self.assertEqual(pp.zhi_pair_relations("子", "子"), ["伏吟"])

    def test_sanhe_groups_detection(self):
        self.assertEqual(pp.sanhe_groups(["申", "子", "辰", "午"]),
                         ["申子辰合水局"])
        self.assertEqual(pp.sanhe_groups(["寅", "午", "戌"]),
                         ["寅午戌合火局"])
        self.assertEqual(pp.sanhe_groups(["子", "丑", "寅", "卯"]), [])


class TestRenYuan(unittest.TestCase):
    def test_table_shape(self):
        self.assertEqual(len(pp.RENYUAN), 12)
        for z in ZHI:
            self.assertIn(z, pp.RENYUAN)
            total = sum(d for _, d in pp.RENYUAN[z])
            self.assertAlmostEqual(total, 30.0, delta=0.01,
                                   msg=f"{z} 月人元天数应合计 30")

    def test_game_a_si_month(self):
        """游戏甲(示例) 2024-05-23 立夏后约 18 天 → 巳月丙火用事（戊7+庚7=14）。"""
        r = pp.calc(datetime(2024, 5, 23, 10, 0), tz_hours=8, lon=113.3)
        ry = r["ren_yuan"]
        self.assertEqual(ry["god"], "丙")
        self.assertGreater(ry["days_after_jie"], 14)

    def test_renyuan_present_in_calc(self):
        r = pp.calc(datetime(1990, 1, 1, 10, 0), tz_hours=8, lon=116.4)
        self.assertIn("ren_yuan", r)
        self.assertIn("relations", r)
        self.assertIn("zhi_pairs", r["relations"])
        self.assertIn("gan_pairs", r["relations"])
        self.assertIn("sanhe", r["relations"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
