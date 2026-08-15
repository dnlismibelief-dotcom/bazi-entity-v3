#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""famous20 数据集与参照比对测试 — BFFT v7.5.

保证两件事：
1. data/famous20_times.json 只含 A/AA 级（有明确出生时刻）的名人，且带独立参照四柱；
2. 引擎批量排盘与参照逐柱比对 20/20 全过（时柱的真太阳时口径差异已复算）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location(
    "famous20", os.path.join(ROOT, "scripts", "famous20.py"))
f20 = importlib.util.module_from_spec(spec)
sys.modules["famous20"] = f20
spec.loader.exec_module(f20)


class TestFamous20Data(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.people = f20.load_people(f20.DATA_DEFAULT)

    def test_has_exactly_20_people(self):
        self.assertEqual(len(self.people), 20)

    def test_everyone_has_documented_time_and_reference(self):
        for p in self.people:
            self.assertIn(p.get("rating"), ("A", "AA"),
                          f"{p.get('name')} 评级应为 A/AA，实际 {p.get('rating')}")
            self.assertTrue(p.get("dt"), f"{p.get('name')} 缺 dt")
            self.assertTrue(p.get("sources"), f"{p.get('name')} 缺来源")
            ref = p.get("reference") or {}
            self.assertEqual(len(ref.get("four_pillars", "")), 11,
                             f"{p.get('name')} 缺参照四柱: {ref}")

    def test_reference_pillars_are_valid(self):
        for p in self.people:
            for key in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"):
                gz = p["reference"].get(key, "")
                self.assertIn(gz[0], f20.pp.GAN, f"{p['name']} {key} 天干非法: {gz}")
                self.assertIn(gz[1], f20.pp.ZHI, f"{p['name']} {key} 地支非法: {gz}")

    def test_no_duplicate_ids(self):
        ids = [p["id"] for p in self.people]
        self.assertEqual(len(ids), len(set(ids)))

    def test_engine_matches_reference_20_of_20(self):
        results = [f20.run_one(p) for p in self.people]
        report = f20.check(results, self.people)
        self.assertEqual(report["mismatches"], [], "存在未解释的柱位差异")
        self.assertEqual(report["all_ok"], 20)
        for lab in f20.PILLAR_LABELS:
            self.assertEqual(report["per_pillar"][lab], 20, f"{lab} 未全对")

    def test_sensitivity_finds_multiple_charts(self):
        p = next(x for x in self.people if x["id"] == "jobs")
        s = f20.sensitivity(p, hours=3)
        self.assertGreater(s["distinct_charts"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
