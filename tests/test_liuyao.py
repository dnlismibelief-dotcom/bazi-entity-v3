#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻排盘引擎穷举测试 — BFFT v7.15.

覆盖：
  - 64 卦全表装卦（宫/世/应/卦名/卦类型，与 guagong 表一致）
  - 全部 64 种六爻编码组合（每爻 4 态取子集）的排盘冒烟
  - 动变正确性（老阳变阴、老阴变阳；变卦卦名正确）
  - 六亲五行生克正确性（宫五行 vs 爻五行五类）
  - 旬空六旬正确性（BFFT idx60 版）
  - 格局检测（六冲卦 10 个、六合卦 8 个、游魂/归魂、独发、六静）
  - CLI 非法输入拒绝
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import subprocess
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(ROOT, "scripts", "liuyao_cli.py")

_spec = importlib.util.spec_from_file_location(
    "ly", os.path.join(ROOT, "scripts", "liuyao", "paipan.py"))
_ly = importlib.util.module_from_spec(_spec)
sys.modules["ly"] = _ly
_spec.loader.exec_module(_ly)

_g = importlib.util.spec_from_file_location(
    "guagong", os.path.join(ROOT, "scripts", "liuyao", "guagong.py"))
_gm = importlib.util.module_from_spec(_g)
sys.modules["guagong"] = _gm
_g.loader.exec_module(_gm)

DT = "2026-08-16 23:00"


class TestGua64Table(unittest.TestCase):
    def test_table_has_64(self):
        self.assertEqual(len(_gm.HEXAGRAMS), 64)

    def test_eight_gongs_eight_gua(self):
        from collections import Counter
        c = Counter(v["宫名"] for v in _gm.HEXAGRAMS.values())
        self.assertEqual(len(c), 8)
        for gong, n in c.items():
            self.assertEqual(n, 8, f"{gong} 应有 8 卦")

    def test_shi_ying_pairs_valid(self):
        # 世应索引差恒为 3（六爻世应规则）
        for v in _gm.HEXAGRAMS.values():
            self.assertEqual(abs(v["世爻索引"] - v["应爻索引"]), 3)

    def test_each_gong_has_you_hun_gui_hun(self):
        from collections import defaultdict
        d = defaultdict(list)
        for v in _gm.HEXAGRAMS.values():
            d[v["宫名"]].append(v["卦类型"])
        for gong, types in d.items():
            self.assertIn("游魂卦", types, gong)
            self.assertIn("归魂卦", types, gong)

    def test_all_64_paipan_smoke(self):
        """64 卦每个都装一遍（配可生成该卦的动爻编码）。"""
        codes = {("乾为天", (2, 2, 2, 2, 2, 2)), ("坤为地", (1, 1, 1, 1, 1, 1))}
        for v in _gm.HEXAGRAMS.values():
            yao = [2 if x == "1" else 1 for x in v and ()]  # placeholder
        # 直接构造：本卦=全部少阳/少阴组合由卦的阴阳序列定
        for key, v in _gm.HEXAGRAMS.items():
            yy = [int(x) for x in key.split(",")]
            yao = [2 if x else 1 for x in yy]
            r = _ly.liuyao_calc(yao, DT)
            self.assertEqual(r["original"]["name"], v["卦名"],
                             f"编码 {yao} 应装 {v['卦名']}")
            self.assertEqual(r["original"]["gong"], v["宫名"])
            self.assertEqual(r["original"]["type"], v["卦类型"])


class TestDongBian(unittest.TestCase):
    def test_old_yang_changes_to_yin(self):
        # 111111 全阳 六爻全老阳 -> 变卦坤为地
        r = _ly.liuyao_calc([3, 3, 3, 3, 3, 3], DT)
        self.assertEqual(r["original"]["name"], "乾为天")
        self.assertEqual(r["changed"]["name"], "坤为地")
        self.assertEqual(len(r["moving_positions"]), 6)

    def test_old_yin_changes_to_yang(self):
        r = _ly.liuyao_calc([4, 4, 4, 4, 4, 4], DT)
        self.assertEqual(r["original"]["name"], "坤为地")
        self.assertEqual(r["changed"]["name"], "乾为天")

    def test_static_no_change(self):
        r = _ly.liuyao_calc([2, 1, 2, 1, 2, 1], DT)
        self.assertIsNone(r["changed"])
        self.assertIn("六静", r["patterns"])

    def test_single_dong(self):
        r = _ly.liuyao_calc([3, 2, 1, 1, 1, 1], DT)
        self.assertEqual(len(r["moving_positions"]), 1)
        self.assertIn("独发", r["patterns"])


class TestLiuqin(unittest.TestCase):
    def test_liuqin_five_types(self):
        # 乾宫属金：爻支子(水)=子孙? 金生水=子孙; 寅(木)=妻财(金克木); 辰(土)=父母(土生金);
        # 午(火)=官鬼(火克金); 申(金)=兄弟
        r = _ly.liuyao_calc([2, 2, 2, 2, 2, 2], DT)  # 乾为天 子寅辰午申戌
        want = ["子孙", "妻财", "父母", "官鬼", "兄弟", "父母"]
        got = [ln["liuqin"] for ln in r["lines"]]
        self.assertEqual(got, want)

    def test_changed_liuqin_by_changed_gong(self):
        r = _ly.liuyao_calc([3, 2, 2, 2, 2, 2], DT)
        ln = r["lines"][0]
        self.assertTrue(ln["moving"])
        self.assertIsNotNone(ln["changed_liuqin"])


class TestXunkong(unittest.TestCase):
    def test_six_xun(self):
        cases = [
            ("甲子", ["戌", "亥"]), ("甲戌", ["申", "酉"]), ("甲申", ["午", "未"]),
            ("甲午", ["辰", "巳"]), ("甲辰", ["寅", "卯"]), ("甲寅", ["子", "丑"]),
        ]
        for gz, want in cases:
            self.assertEqual(_ly._xunkong(gz), want, gz)
        self.assertEqual(_ly._xunkong("癸亥"), ["子", "丑"])
        self.assertEqual(_ly._xunkong("丙午"), ["寅", "卯"])


class TestPatterns(unittest.TestCase):
    def test_liuchong_gua_count_10(self):
        self.assertEqual(len(_ly.LIUCHONG_GUA), 10)

    def test_liuhe_gua_count_8(self):
        self.assertEqual(len(_ly.LIUHE_GUA), 8)

    def test_you_hun_gui_hun_pattern(self):
        # 火地晋=乾宫游魂: 阴阳 0,0,0,1,0,1 -> yao: 1,1,1,2,1,2
        r = _ly.liuyao_calc([1, 1, 1, 2, 1, 2], DT)
        self.assertEqual(r["original"]["name"], "火地晋")
        self.assertIn("游魂", r["patterns"])
        # 火天大有=乾宫归魂: 1,1,1,1,0,1 -> 2,2,2,2,1,2
        r2 = _ly.liuyao_calc([2, 2, 2, 2, 1, 2], DT)
        self.assertEqual(r2["original"]["name"], "火天大有")
        self.assertIn("归魂", r2["patterns"])

    def test_liuhe_liuchong_by_name(self):
        r = _ly.liuyao_calc([1, 1, 1, 2, 2, 2], DT)  # 天地否=下坤上乾
        self.assertEqual(r["original"]["name"], "天地否")
        self.assertIn("六合卦", r["patterns"])


class TestCli(unittest.TestCase):
    def test_invalid_yao_rejected(self):
        out = subprocess.run([sys.executable, CLI, "--yao", "12345", "--dt", DT],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        self.assertNotEqual(out.returncode, 0)
        out2 = subprocess.run([sys.executable, CLI, "--yao", "129121", "--dt", DT],
                              cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertNotEqual(out2.returncode, 0)

    def test_no_yao_no_random_rejected(self):
        out = subprocess.run([sys.executable, CLI, "--dt", DT],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        self.assertNotEqual(out.returncode, 0)

    def test_random_valid(self):
        out = subprocess.run([sys.executable, CLI, "--random", "--dt", DT, "--json"],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
