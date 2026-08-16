#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dist 打包清单测试 — BFFT v7.5."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location(
    "build_dist", os.path.join(ROOT, "scripts", "build_dist.py"))
bd = importlib.util.module_from_spec(spec)
sys.modules["build_dist"] = bd
spec.loader.exec_module(bd)


class TestBuildDist(unittest.TestCase):

    def test_collect_includes_core_and_new_files(self):
        arcs = {arc for _, arc in bd.collect()}
        for want in ("BFFT/scripts/pai_pan.py", "BFFT/scripts/cli.py",
                     "BFFT/scripts/report.py", "BFFT/scripts/fetch_entity.py",
                     "BFFT/scripts/liuyao_cli.py", "BFFT/scripts/liuyao/paipan.py",
                     "BFFT/scripts/build_dist.py", "BFFT/tests/test_liuyao.py",
                     "BFFT/references/report-template.md", "BFFT/references/liuyao.md",
                     "BFFT/LICENSE", "BFFT/SKILL.md"):
            self.assertIn(want, arcs, f"打包清单缺少 {want}")

    def test_collect_excludes_git_and_dist(self):
        arcs = {arc for _, arc in bd.collect()}
        for bad in ("BFFT/.git/", "BFFT/dist/", "BFFT/__pycache__/"):
            self.assertFalse(any(a.startswith(bad) for a in arcs),
                             f"打包清单不应包含 {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
