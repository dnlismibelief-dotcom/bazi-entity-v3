#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""古籍现代化增量模块测试 — BFFT v7.18."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location(
    "ce", os.path.join(ROOT, "scripts", "classics_extra.py"))
_ce = importlib.util.module_from_spec(_spec)
sys.modules["ce"] = _ce
_spec.loader.exec_module(_ce)


class TestSourceFlow(unittest.TestCase):
    def test_source_is_max(self):
        counts = {"木": 4, "火": 3, "土": 4, "金": 2, "水": 2}
        r = _ce.source_flow(counts)
        self.assertIn(r["source"], ("木", "土"))  # 并列最大取 dict 序首
        self.assertEqual(counts[r["source"]], 4)

    def test_chain_follows_sheng(self):
        """链沿生链推进，直到下一行不再旺于当前。"""
        counts = {"木": 5, "火": 5, "土": 4, "金": 3, "水": 2}
        r = _ce.source_flow(counts)
        self.assertEqual(r["source"], "木")
        self.assertEqual(r["chain"], ["木", "火"])
        self.assertEqual(r["sink"], "火")

    def test_max_source_stops_chain(self):
        """源即全局最旺且下一行更弱时, 链只含源本身。"""
        counts = {"木": 5, "火": 4, "土": 3, "金": 2, "水": 1}
        r = _ce.source_flow(counts)
        self.assertEqual(r["chain"], ["木"])

    def test_empty_counts(self):
        r = _ce.source_flow({})
        self.assertEqual(r["source"], "")

    def test_single_element(self):
        r = _ce.source_flow({"木": 3})
        self.assertEqual(r["source"], "木")
        self.assertEqual(r["chain"], ["木"])


class TestTongguan(unittest.TestCase):
    def test_five_war_pairs(self):
        r = _ce.tongguan({"木": 1, "火": 1, "土": 1, "金": 1, "水": 1})
        self.assertEqual(len(r), 5)
        wars = {x["war"] for x in r}
        self.assertIn("金木交战", wars)
        self.assertIn("水火交战", wars)

    def test_bridge_rule(self):
        """木土交战 → 火通关（木生火生土）。"""
        r = _ce.tongguan({"木": 1, "火": 1, "土": 1, "金": 0, "水": 0})
        for x in r:
            if x["war"] == "木土交战":
                self.assertEqual(x["bridge"], "火")
                self.assertTrue(x["bridge_present"])
            if x["war"] == "金木交战":
                self.assertEqual(x["bridge"], "水")
                self.assertFalse(x["bridge_present"])


class TestChangshengRead(unittest.TestCase):
    def test_read_table(self):
        self.assertEqual(_ce.changsheng_read("长生"), "创建作新")
        self.assertEqual(_ce.changsheng_read("帝旺"), "发福进财")
        self.assertEqual(_ce.changsheng_read("死"), "骨肉死丧")
        self.assertEqual(_ce.changsheng_read("墓"), "收藏入库")

    def test_all_twelve_covered(self):
        for pos in ("长生", "沐浴", "冠带", "临官", "帝旺", "衰",
                    "病", "死", "墓", "绝", "胎", "养"):
            self.assertTrue(_ce.changsheng_read(pos), pos)

    def test_unknown_empty(self):
        self.assertEqual(_ce.changsheng_read("不存在"), "")


# ---------------------------------------------------------------------------
# 第二轮精读增量测试（v7.18 追加）
# ---------------------------------------------------------------------------

def _p(gz: str) -> dict:
    """"庚戌" → {"gan": "庚", "zhi": "戌"}。"""
    return {"gan": gz[0], "zhi": gz[1]}


class TestCongHua(unittest.TestCase):
    def test_qianli_cong_cai(self):
        """千里命稿从财例：庚戌 乙酉 丙申 己丑 —— 日主全无一点生气, 是为从财。"""
        r = _ce.cong_hua_judge("丙", "酉", [_p("庚戌"), _p("乙酉"), _p("丙申"), _p("己丑")])
        self.assertEqual(r["verdict"], "真从财")

    def test_qianli_cong_sha(self):
        """千里命稿从杀例：戊戌 辛酉 乙酉 乙酉 —— 无印滋身, 只得从杀。"""
        r = _ce.cong_hua_judge("乙", "酉", [_p("戊戌"), _p("辛酉"), _p("乙酉"), _p("乙酉")])
        self.assertEqual(r["verdict"], "真从杀")

    def test_qianli_cong_er(self):
        """千里命稿从儿例：丁卯 壬寅 癸卯 丙辰 —— 伤食当旺, 从儿格成矣。"""
        r = _ce.cong_hua_judge("癸", "寅", [_p("丁卯"), _p("壬寅"), _p("癸卯"), _p("丙辰")])
        self.assertEqual(r["verdict"], "真从儿")

    def test_true_hua(self):
        """甲己合, 化神土当令(辰月)且见辰(龙) —— 化得真。"""
        r = _ce.cong_hua_judge("甲", "辰", [_p("壬子"), _p("己辰"), _p("甲子"), _p("戊辰")])
        self.assertEqual(r["verdict"], "真化土")

    def test_false_hua(self):
        """甲己合但化神不当令(寅月木旺) —— 假化。"""
        r = _ce.cong_hua_judge("甲", "寅", [_p("壬子"), _p("己寅"), _p("甲子"), _p("戊戌")])
        self.assertEqual(r["verdict"], "假化土")

    def test_normal_pattern(self):
        """日主有强根, 不入从化。"""
        r = _ce.cong_hua_judge("甲", "寅", [_p("庚申"), _p("丙寅"), _p("甲子"), _p("壬申")])
        self.assertEqual(r["verdict"], "普通格局")

    def test_jia_cong_with_strong_root(self):
        """财势满盘但暗根过多, 从之不真。"""
        r = _ce.cong_hua_judge("丙", "酉", [_p("庚戌"), _p("乙酉"), _p("丙午"), _p("庚丑")])
        self.assertEqual(r["verdict"], "假从财")


class TestChongRead(unittest.TestCase):
    def test_shengfang_pa_dong(self):
        r = _ce.chong_read("寅", "申", "子")
        self.assertTrue(r["is_chong"])
        self.assertEqual(r["kind"], "生方")
        self.assertIn("怕动", r["read"])

    def test_siku_yi_kai(self):
        r = _ce.chong_read("丑", "未", "寅")
        self.assertEqual(r["kind"], "四库")
        self.assertIn("宜开", r["read"])

    def test_baidi_wang_chong_shuai(self):
        """子月水旺, 子冲午 —— 旺者冲衰, 衰者(午)被拔。"""
        r = _ce.chong_read("子", "午", "子")
        self.assertEqual(r["kind"], "四败")
        self.assertEqual(r["wang"], "子")
        self.assertEqual(r["ba"], "午")
        self.assertIn("被拔", r["read"])

    def test_not_chong(self):
        r = _ce.chong_read("子", "卯", "子")
        self.assertFalse(r["is_chong"])


class TestQingzhuo(unittest.TestCase):
    def test_guansha_hunza(self):
        """甲日主透庚(杀)辛(官) —— 官杀混杂。"""
        r = _ce.qingzhuo_check("甲", [_p("庚子"), _p("辛丑"), _p("甲寅"), _p("壬辰")])
        names = {c["name"]: c["present"] for c in r["checks"]}
        self.assertTrue(names["官杀混杂"])

    def test_shangguan_jian_guan_no_cai(self):
        r = _ce.qingzhuo_check("甲", [_p("丁卯"), _p("辛丑"), _p("甲寅"), _p("壬辰")])
        names = {c["name"]: c["present"] for c in r["checks"]}
        self.assertTrue(names["伤官见官"])

    def test_shangguan_jian_guan_with_cai(self):
        """透财则财通关, 伤官见官不为祸。"""
        r = _ce.qingzhuo_check("甲", [_p("丁卯"), _p("辛丑"), _p("甲寅"), _p("戊辰")])
        names = {c["name"]: c["present"] for c in r["checks"]}
        self.assertFalse(names["伤官见官"])

    def test_qing_ju(self):
        r = _ce.qingzhuo_check("甲", [_p("戊子"), _p("甲辰"), _p("甲寅"), _p("丙午")])
        self.assertEqual(r["grade"], "清")

    def test_zhuo_grade(self):
        """官杀混杂 + 伤官见官(无财) —— 浊。"""
        r = _ce.qingzhuo_check("甲", [_p("庚子"), _p("辛丑"), _p("甲寅"), _p("丁卯")])
        self.assertEqual(r["grade"], "浊")


class TestZhonggua(unittest.TestCase):
    def test_qiang_zhong_di_gua(self):
        r = _ce.zhonggua_read("甲", {"木": 7, "火": 1, "土": 1, "金": 1, "水": 1})
        self.assertIn("去其寡", r["read"])
        self.assertEqual(r["top"], "木")

    def test_qiang_gua_di_zhong(self):
        r = _ce.zhonggua_read("甲", {"木": 6, "金": 6, "火": 1, "土": 1, "水": 1})
        self.assertIn("成乎众", r["read"])

    def test_liang_ting(self):
        r = _ce.zhonggua_read("甲", {"木": 2, "火": 2, "土": 2, "金": 2, "水": 2})
        self.assertIn("众寡不显", r["read"])


class TestZhenjia(unittest.TestCase):
    def test_zhen_shen(self):
        """寅月人元甲丙戊, 透甲 —— 真神得用。"""
        r = _ce.zhenjia_check("寅", [_p("甲子"), _p("丙寅"), _p("戊辰"), _p("壬戌")])
        self.assertIn("甲", r["zhen"])
        self.assertTrue(r["zhen_primary"])

    def test_jia_shen(self):
        """寅月不透人元, 透金党多 —— 假神乱真。"""
        r = _ce.zhenjia_check("寅", [_p("辛丑"), _p("乙卯"), _p("癸酉"), _p("庚辰")])
        self.assertEqual(r["zhen"], [])
        self.assertNotEqual(r["jia"], [])

    def test_tigang_bu_zhao(self):
        """寅月不透人元, 亦无党多假神 —— 暗处寻真。"""
        r = _ce.zhenjia_check("寅", [_p("壬子"), _p("乙卯"), _p("丁未"), _p("庚戌")])
        self.assertEqual(r["zhen"], [])
        self.assertEqual(r["jia"], [])
        self.assertIn("暗处寻真", r["read"])


class TestYinxian(unittest.TestCase):
    def test_use_exposed(self):
        """用神火透干 —— 吉神太露, 起争夺之风。"""
        r = _ce.yinxian_read("甲", [_p("戊子"), _p("庚戌"), _p("甲辰"), _p("丙申")], "火")
        self.assertTrue(r["use_exposed"])

    def test_ji_hidden(self):
        """忌神水藏支不透 —— 凶物深藏, 成养虎之患。"""
        r = _ce.yinxian_read("甲", [_p("戊子"), _p("庚戌"), _p("甲辰"), _p("丙申")], "火")
        self.assertTrue(r["ji_hidden"])

    def test_use_hidden(self):
        """用神藏支不露 —— 不招争夺。"""
        r = _ce.yinxian_read("甲", [_p("戊子"), _p("庚戌"), _p("甲辰"), _p("壬申")], "火")
        self.assertFalse(r["use_exposed"])


class TestSuiyunRelation(unittest.TestCase):
    def test_zhan(self):
        r = _ce.suiyun_relation("庚申", "丙午")
        self.assertIn("战", r["gan"])
        self.assertIn("岁伐运", r["gan"])

    def test_chong(self):
        r = _ce.suiyun_relation("甲子", "戊午")
        self.assertIn("冲", r["zhi"])

    def test_he(self):
        r = _ce.suiyun_relation("乙丑", "庚午")
        self.assertIn("和", r["gan"])

    def test_hao(self):
        r = _ce.suiyun_relation("庚申", "辛未")
        self.assertIn("好", r["gan"])


class TestShengkeOrder(unittest.TestCase):
    def test_guan_ge_shang_xian_cai_hou(self):
        """官格 伤先财后（丁先戊后）—— 先凶后吉。"""
        r = _ce.shengke_order(["丁", "戊", "甲", "壬"], "甲", "官格")
        self.assertEqual(r["verdict"], "先凶后吉")

    def test_guan_ge_cai_xian_shang_hou(self):
        """官格 财先伤后（戊先丁后）—— 先吉后凶。"""
        r = _ce.shengke_order(["戊", "丁", "甲", "壬"], "甲", "官格")
        self.assertEqual(r["verdict"], "先吉后凶")

    def test_shi_ge_xiao_xian_cai_hou(self):
        """食格 枭先财后（庚先丙后）—— 晚运必亨。"""
        r = _ce.shengke_order(["庚", "丙", "壬", "甲"], "壬", "食格")
        self.assertEqual(r["verdict"], "先凶后吉")

    def test_sha_ge_cai_xian_shi_hou(self):
        """杀格 财先食后（癸先辛后）—— 不失大贵。"""
        r = _ce.shengke_order(["癸", "辛", "己", "丁"], "己", "杀格")
        self.assertEqual(r["verdict"], "吉")

    def test_sha_ge_shi_xian_cai_hou(self):
        """杀格 食先财后（辛先癸后）—— 不贵, 后运萧索。"""
        r = _ce.shengke_order(["辛", "癸", "己", "丁"], "己", "杀格")
        self.assertEqual(r["verdict"], "凶")


class TestJixiongGe(unittest.TestCase):
    def test_guan_ge_po(self):
        r = _ce.jixiong_ge_check("甲", [_p("丁卯"), _p("辛丑"), _p("甲寅"), _p("壬辰")], "官格")
        self.assertTrue(r["breaks"])
        self.assertFalse(r["saves"])

    def test_guan_ge_cai_tongguan(self):
        r = _ce.jixiong_ge_check("甲", [_p("丁卯"), _p("辛丑"), _p("甲寅"), _p("戊辰")], "官格")
        self.assertFalse(r["breaks"])
        self.assertTrue(r["saves"])

    def test_cai_ge_shang_guan_jie(self):
        """财逢比劫, 伤官可解。"""
        r = _ce.jixiong_ge_check("甲", [_p("乙丑"), _p("丙寅"), _p("甲辰"), _p("戊午")], "财格")
        self.assertFalse(r["breaks"])
        self.assertTrue(r["saves"])

    def test_yin_ge_sha_cheng(self):
        """印绶根轻, 透煞为助, 煞能成格。"""
        r = _ce.jixiong_ge_check("甲", [_p("戊午"), _p("庚申"), _p("甲子"), _p("壬申")], "印格")
        self.assertIn("煞能成格", r["saves"][-1])


class TestXiaoyun(unittest.TestCase):
    def test_yang_nian_male_forward(self):
        """阳年男顺行：甲子时 1 岁乙丑, 2 岁丙寅。"""
        self.assertEqual(_ce.xiaoyun_pillar("甲", "male", "甲子", 1), "乙丑")
        self.assertEqual(_ce.xiaoyun_pillar("甲", "male", "甲子", 2), "丙寅")

    def test_yang_nian_female_backward(self):
        """阳年女逆行：甲子时 1 岁癸亥。"""
        self.assertEqual(_ce.xiaoyun_pillar("甲", "female", "甲子", 1), "癸亥")

    def test_yin_nian_female_forward(self):
        """阴年女顺行：乙亥时 1 岁丙子。"""
        self.assertEqual(_ce.xiaoyun_pillar("乙", "female", "乙亥", 1), "丙子")

    def test_gufa(self):
        self.assertEqual(_ce.xiaoyun_pillar("甲", "male", "甲子", 1, method="gufa"), "丙寅")
        self.assertEqual(_ce.xiaoyun_pillar("甲", "female", "甲子", 1, method="gufa"), "壬申")


class TestTaisui(unittest.TestCase):
    def test_ri_fan_suijun(self):
        """甲日戊年 —— 日犯岁君, 灾重。"""
        r = _ce.taisui_check("甲子", "己巳", None, "戊寅", "甲")
        self.assertTrue(any("日犯岁君" in x for x in r["relations"]))

    def test_sui_shang_rigan(self):
        """庚年甲日 —— 岁伤日干, 祸轻。"""
        r = _ce.taisui_check("甲子", "己巳", None, "庚午", "甲")
        self.assertTrue(any("岁伤日干" in x for x in r["relations"]))

    def test_zhen_taisui(self):
        r = _ce.taisui_check("甲子", "甲子", None, "甲子", "甲")
        self.assertTrue(any("真太岁" in x for x in r["relations"]))

    def test_zheng_taisui(self):
        """日支子冲岁支午 —— 征太岁。"""
        r = _ce.taisui_check("甲子", "己巳", None, "戊午", "甲")
        self.assertTrue(any("征太岁" in x for x in r["relations"]))

    def test_suiyun_binglin_qisha(self):
        """岁运并临, 七杀为凶。"""
        r = _ce.taisui_check("甲子", "己巳", "庚申", "庚申", "甲")
        self.assertTrue(any("岁运并临" in x and "七杀" in x for x in r["relations"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
