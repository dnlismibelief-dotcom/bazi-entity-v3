#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report.py 一键报告生成器测试 — BFFT v7.14."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "scripts", "report.py")


def run_report(*args):
    out = subprocess.run([sys.executable, REPORT, *args],
                         cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return out


class TestReportDatetimeMode(unittest.TestCase):
    def test_full_mode_outputs_json_and_md(self):
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "rep")
            out = run_report("--name", "测试", "--dt", "1990-01-01 10:00",
                             "--lon", "116.4", "--gender", "male", "--out", base)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(os.path.exists(base + ".json"))
            self.assertTrue(os.path.exists(base + ".md"))
            chart = json.load(open(base + ".json", encoding="utf-8"))
            self.assertEqual(chart["year_pillar"], "己巳")
            self.assertEqual(chart["input_mode"], "datetime")
            self.assertIn("relations", chart)
            self.assertIn("ren_yuan", chart)
            self.assertIn("lucky", chart)
            md = open(base + ".md", encoding="utf-8").read()
            self.assertIn("三盘交叉", md)
            self.assertIn("七维度", md)

    def test_bad_datetime_rejected(self):
        out = run_report("--dt", "1990-13-40 25:00", "--out", "x")
        self.assertNotEqual(out.returncode, 0)

    def test_bad_lon_rejected(self):
        out = run_report("--dt", "1990-01-01 10:00", "--lon", "999", "--out", "x")
        self.assertNotEqual(out.returncode, 0)


class TestReportPillarsMode(unittest.TestCase):
    def test_pillars_mode_gaps_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "rep")
            out = run_report("--name", "八字", "--pillars", "庚子 丁亥 庚午 壬午",
                             "--gender", "male", "--out", base)
            self.assertEqual(out.returncode, 0, out.stderr)
            chart = json.load(open(base + ".json", encoding="utf-8"))
            self.assertEqual(chart["input_mode"], "pillars")
            self.assertEqual(chart["four_pillars"] if "four_pillars" in chart
                             else chart["year_pillar"] + " " + chart["month_pillar"]
                             + " " + chart["day_pillar"] + " " + chart["hour_pillar"],
                             "庚子 丁亥 庚午 壬午")
            self.assertTrue(chart["gaps"], "仅八字模式必须标注数据缺口")
            # 大运序列方向: 庚子阳年男顺排, 月柱丁亥 -> 戊子起
            self.assertEqual(chart["lucky_sequence"][0], "戊子")
            self.assertEqual(chart["minggong"], "戊子")
            md = open(base + ".md", encoding="utf-8").read()
            self.assertIn("数据缺口", md)

    def test_pillars_invalid_rejected(self):
        out = run_report("--pillars", "甲子 丙寅", "--out", "x")
        self.assertNotEqual(out.returncode, 0)
        out2 = run_report("--pillars", "甲丑 丙寅 戊辰 庚午", "--out", "x")
        self.assertNotEqual(out2.returncode, 0, "甲丑非法组合应拒绝")

    def test_pillars_female_reverse(self):
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "rep")
            out = run_report("--pillars", "庚子 丁亥 庚午 壬午",
                             "--gender", "female", "--out", base)
            self.assertEqual(out.returncode, 0, out.stderr)
            chart = json.load(open(base + ".json", encoding="utf-8"))
            self.assertEqual(chart["dayun_direction"], "逆排")
            # 丁亥逆排上一位 = 丙戌
            self.assertEqual(chart["lucky_sequence"][0], "丙戌")


class TestReportMutualExclusion(unittest.TestCase):
    def test_dt_and_pillars_conflict(self):
        out = run_report("--dt", "1990-01-01 10:00",
                         "--pillars", "庚子 丁亥 庚午 壬午", "--out", "x")
        self.assertNotEqual(out.returncode, 0)

    def test_neither_rejected(self):
        out = run_report("--out", "x")
        self.assertNotEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
