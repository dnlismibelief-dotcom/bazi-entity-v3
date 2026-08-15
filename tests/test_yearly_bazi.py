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


if __name__ == "__main__":
    unittest.main(verbosity=2)
