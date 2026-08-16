#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yearly_bazi 逐年规则与打分测试 — BFFT v7.5."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location(
    "yearly_bazi", os.path.join(ROOT, "scripts", "yearly_bazi.py"))
yb = importlib.util.module_from_spec(spec)
sys.modules["yearly_bazi"] = yb
spec.loader.exec_module(yb)

TAYLOR = dict(dt="1989-12-13 08:36", tz=-5.0, lon=-75.93, gender="female")


def taylor_chart():
    return yb.pp.calc(datetime.strptime(TAYLOR["dt"], "%Y-%m-%d %H:%M"),
                      tz_hours=TAYLOR["tz"], lon=TAYLOR["lon"],
                      gender=TAYLOR["gender"], lucky_count=10)


class TestYearlyRules(unittest.TestCase):

    def test_rules_deterministic_and_bounded(self):
        a = yb.yearly_rows(taylor_chart(), 2006, 2031)
        b = yb.yearly_rows(taylor_chart(), 2006, 2031)
        self.assertEqual(a, b)
        for r in a:
            self.assertTrue(0.10 <= r["p_album"] <= 0.80)
            self.assertTrue(0.10 <= r["p_tour"] <= 0.80)
            self.assertEqual(len(r["liunian"]), 2)

    def test_dayun_switches_at_2018_boundary(self):
        rows = {r["year"]: r for r in yb.yearly_rows(taylor_chart(), 2017, 2018)}
        self.assertEqual(rows[2017]["dayun"], "戊寅")
        self.assertEqual(rows[2018]["dayun"], "己卯")

    def test_dayun_before_jiao_uses_month_pillar(self):
        """交运前年份的主运应为月柱（泰勒 1997-08 才交运）。

        v7.8 修复：此前退化成 lucky[0]（丁丑），把第一步大运错误套到
        1989—1997 交运前的年份；正确行为是起运前行运即月柱丙子。
        """
        rows = {r["year"]: r for r in yb.yearly_rows(taylor_chart(), 1989, 1998)}
        self.assertEqual(rows[1989]["dayun"], "丙子", "交运前应用月柱")
        self.assertEqual(rows[1989]["dayun_gan_relation"], "劫财")
        self.assertEqual(rows[1989]["dayun_zhi_relation"], "六穿")
        self.assertFalse(rows[1989]["dayun_change"])
        self.assertEqual(rows[1996]["dayun"], "丙子")
        self.assertTrue(rows[1997]["dayun_change"], "1997 为交运年")
        self.assertEqual(rows[1998]["dayun"], "丁丑", "交运后进入第一步大运")

    def test_zhi_rel_all_pairs_match_tables(self):
        """66 地支对穷举：zhi_rel 输出必须与六合/六冲/六穿/半合/刑表完全一致。

        v7.9 修复：sorted() 按 Unicode 码位排序（'申亥'→'亥申'）与表键序
        失配，7/66 对静默失效（子丑合/寅亥合/子午冲/辰戌冲/巳亥冲/申亥穿/
        酉戌穿）。修复后逐对校验，任何失配立即报出。
        """
        ZHI = yb.pp.ZHI
        for i in range(12):
            for j in range(i + 1, 12):
                z1, z2 = ZHI[i], ZHI[j]
                got = yb.zhi_rel(z1, z2) or "静"
                pair = ZHI[i] + ZHI[j]  # 表键序
                expect = "静"
                if pair in yb.LIUHE: expect = "六合"
                elif pair in yb.LIUCHONG: expect = "六冲"
                elif pair in yb.LIUHAI: expect = "六穿"
                elif pair in yb.BANHE: expect = "半合"
                elif pair in {"丑戌", "戌未"}: expect = "刑"
                self.assertEqual(got, expect, f"{z1}{z2} 应{expect} 实{got}")

    def test_zhi_rel_key_cases(self):
        """关键案例：鸣潮巳亥冲/申亥穿、原神辰戌冲、泰勒子丑合/寅亥合。"""
        self.assertEqual(yb.zhi_rel("巳", "亥"), "六冲")
        self.assertEqual(yb.zhi_rel("申", "亥"), "六穿")
        self.assertEqual(yb.zhi_rel("辰", "戌"), "六冲")
        self.assertEqual(yb.zhi_rel("子", "丑"), "六合")
        self.assertEqual(yb.zhi_rel("寅", "亥"), "六合")
        self.assertEqual(yb.zhi_rel("子", "未"), "六穿")
        self.assertEqual(yb.zhi_rel("午", "未"), "六合")

    def test_suiyun_gan_he_detected(self):
        """岁运天干五合必须生效（v7.9 修复：此前查 LIUHE 永远失配）。

        泰勒 2024 甲辰年大运己卯：甲己合 → '岁运干合'。
        鸣潮 2028 戊申年大运己巳：丙辛合？(戊≠丙) 用 2028 前的己巳运无合；
        用泰勒案例即可。另测地支：2029 己酉 大运庚辰 → 酉辰六合。
        """
        tags = yb.suiyun_rel("甲辰", "己卯")
        self.assertIn("岁运干合", tags)
        tags2 = yb.suiyun_rel("己酉", "庚辰")
        self.assertIn("岁运支合", tags2)
        tags3 = yb.suiyun_rel("丙午", "己巳")
        self.assertNotIn("岁运干合", tags3)


class TestBuildPredictions(unittest.TestCase):

    def test_future_grade_and_non_low_info_biz(self):
        import argparse
        chart = taylor_chart()
        rows = yb.yearly_rows(chart, 2006, 2031)
        ns = argparse.Namespace(name="Taylor Swift", datetime=TAYLOR["dt"],
                                tz=TAYLOR["tz"], lon=TAYLOR["lon"],
                                future_from=2026, biz_years=[2027, 2029, 2031])
        doc = yb.build_predictions(ns, chart, rows)
        a = [p for p in doc["predictions"] if p["evidence_grade"] == "A"]
        self.assertEqual(len(a), 13)
        counted = [p for p in a if not p.get("low_information")]
        self.assertEqual(len(counted), 3)
        self.assertTrue(all(p["id"].endswith("-biz") for p in counted))


class TestScoring(unittest.TestCase):

    def test_score_fills_only_years_with_facts(self):
        import argparse
        with tempfile.TemporaryDirectory() as d:
            chart = taylor_chart()
            rows = yb.yearly_rows(chart, 2006, 2027)
            ns = argparse.Namespace(name="T", datetime=TAYLOR["dt"],
                                    tz=TAYLOR["tz"], lon=TAYLOR["lon"],
                                    future_from=9999, biz_years=[])
            doc = yb.build_predictions(ns, chart, rows)
            pred_path = os.path.join(d, "p.json")
            facts_path = os.path.join(d, "f.json")
            with open(pred_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False)
            facts = {"years": [{"year": 2006, "new_album": True, "tour_launch": False}]}
            with open(facts_path, "w", encoding="utf-8") as f:
                json.dump(facts, f, ensure_ascii=False)
            ns2 = argparse.Namespace(predictions=pred_path, score=facts_path)
            yb.score(ns2)
            with open(pred_path, encoding="utf-8") as f:
                out = json.load(f)
            by_id = {p["id"]: p for p in out["predictions"]}
            self.assertEqual(by_id["T-2006-album"]["verdict"], "hit")
            self.assertEqual(by_id["T-2006-tour"]["verdict"], "miss")
            self.assertEqual(by_id["T-2027-album"]["verdict"], "pending",
                             "事实表未覆盖的年份不得回填")


class TestCareerModel(unittest.TestCase):
    """rulebook v1：事业指数与显著高峰年判据。"""

    def test_career_index_age_prior(self):
        rows = yb.yearly_rows(taylor_chart(), 1989, 2024)
        by = {r["year"]: r for r in rows}
        idx_1989, p_1989, _ = yb.career_index(by[1989], 1989)
        idx_2024, p_2024, _ = yb.career_index(by[2024], 1989)
        self.assertLessEqual(p_1989, 0.03 + 1e-9, "童年高峰概率应为下限 0.03")
        self.assertGreater(idx_2024, idx_1989)
        self.assertTrue(0.03 <= p_2024 <= 0.75)

    def test_career_predictions_grades(self):
        import argparse
        chart = taylor_chart()
        rows = yb.yearly_rows(chart, 1989, 2031)
        ns = argparse.Namespace(name="T", datetime=TAYLOR["dt"], tz=TAYLOR["tz"],
                                lon=TAYLOR["lon"], future_from=2026, birth_year=1989)
        doc = yb.build_career_predictions(ns, chart, rows)
        a = [p for p in doc["predictions"] if p["evidence_grade"] == "A"]
        self.assertEqual(len(a), 5)
        self.assertTrue(all(not p.get("low_information") for p in a),
                        "2027—2031 高峰概率应高于基线 0.20")

    def test_score_career_keeps_missing_years_pending(self):
        import argparse
        with tempfile.TemporaryDirectory() as d:
            chart = taylor_chart()
            rows = yb.yearly_rows(chart, 1989, 2027)
            ns = argparse.Namespace(name="T", datetime=TAYLOR["dt"], tz=TAYLOR["tz"],
                                    lon=TAYLOR["lon"], future_from=9999, birth_year=1989)
            doc = yb.build_career_predictions(ns, chart, rows)
            pred_path = os.path.join(d, "p.json")
            facts_path = os.path.join(d, "f.json")
            with open(pred_path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
            facts = {"high_threshold": 4,
                     "years": [{"year": 2023, "score": 9}]}
            with open(facts_path, "w", encoding="utf-8") as fh:
                json.dump(facts, fh, ensure_ascii=False)
            ns2 = argparse.Namespace(predictions=pred_path, score_career=facts_path)
            yb.score_career(ns2)
            with open(pred_path, encoding="utf-8") as fh:
                out = json.load(fh)
            by_id = {p["id"]: p for p in out["predictions"]}
            self.assertEqual(by_id["TS2-2023-high"]["verdict"], "hit")
            self.assertEqual(by_id["TS2-2027-high"]["verdict"], "pending")


if __name__ == "__main__":
    unittest.main(verbosity=2)
