#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐年岁运预测生成器（BFFT v7.5 工具）。

对一张人盘，把 M5 时序引擎操作化为**确定性的逐年规则**，生成每年两类
可公开核验的判据：
  T-<年>-album  该年发行一张全新录音室专辑（不含重录版）
  T-<年>-tour   该年启动新全球巡演
以及按需追加的商业节点判据（--biz-years）。

设计约束：
  * 规则只吃排盘输出（干支/十神/大运/流年），不读任何事实数据；
  * 概率 = 固定基准 + 固定权重（规则表见源码），生成前不改参数；
  * 过去年份一律 evidence_grade=B（事后回测，verify.py 不计 A 级）；
  * 未来年份（--future-from 之后）evidence_grade=A，commit 即事前登记。

用法:
  python scripts/yearly_bazi.py "1989-12-13 08:36" --tz -5 --lon -75.93 \
      --gender female --name "Taylor Swift" --from 2006 --to 2031 \
      --write predictions/taylor.json

打分（在预测 commit 之后，另读事实表）:
  python scripts/yearly_bazi.py ... --score data/taylor_facts.json \
      --predictions predictions/taylor.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("pai_pan", os.path.join(ROOT, "scripts", "pai_pan.py"))
pp = importlib.util.module_from_spec(spec)
sys.modules["pai_pan"] = pp
spec.loader.exec_module(pp)

# ---- 固定规则表（生成后不再改；改动须另起版本号并重跑）----
RULEBOOK_VERSION = "v0"
ALBUM_BASE = 0.30
TOUR_BASE = 0.20
GAN_W = {            # (album, tour)
    "正印": (0.08, 0.00), "偏印": (0.08, 0.00),
    "比肩": (0.04, 0.02), "劫财": (0.04, 0.02),
    "食神": (0.12, 0.06), "伤官": (0.12, 0.06),
    "正财": (0.06, 0.03), "偏财": (0.06, 0.03),
    "正官": (0.04, 0.08), "七杀": (0.04, 0.08),
}
ZHI_W = {            # (album, tour) 相对日支
    "伏吟": (0.03, 0.06),
    "六合": (0.04, 0.04), "半合": (0.04, 0.04),
    "六冲": (0.05, 0.05),
    "六穿": (0.02, 0.02), "刑": (0.02, 0.01),
}
LIUHE = {"子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"}
LIUCHONG = {"子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"}
LIUHAI = {"子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"}
BANHE = {"卯未": "亥卯未木局", "亥卯": "亥卯未木局", "亥未": "亥卯未木局"}


def zhi_rel(z1: str, z2: str) -> str:
    """z1（流年支）相对 z2（日支）的关系标签。"""
    if z1 == z2:
        return "伏吟"
    pair = "".join(sorted((z1, z2)))
    if pair in LIUHE:
        return "六合"
    if pair in LIUCHONG:
        return "六冲"
    if pair in LIUHAI:
        return "六穿"
    if pair in BANHE:
        return "半合"
    if pair in {"丑戌", "戌未"}:
        return "刑"
    return ""


def suiyun_rel(year_gz: str, luck_gz: str) -> list[str]:
    tags = []
    yg, yz, lg, lz = year_gz[0], year_gz[1], luck_gz[0], luck_gz[1]
    if yg == lg:
        tags.append("岁运干并临")
    if yz == lz:
        tags.append("岁运支并临")
    if "".join(sorted(yg + lg)) in LIUHE:
        tags.append("岁运干合")
    pair = "".join(sorted((yz, lz)))
    if pair in LIUCHONG:
        tags.append("岁运支冲")
    elif pair in LIUHE:
        tags.append("岁运支合")
    elif pair in BANHE:
        tags.append("岁运支半合")
    return tags


def clamp(x: float) -> float:
    return round(max(0.10, min(0.80, x)), 3)


def yearly_rows(chart: dict, start_year: int, end_year: int) -> list[dict]:
    day_gan = chart["day_pillar"][0]
    day_zhi = chart["day_pillar"][1]
    rows = []
    for y in range(start_year, end_year + 1):
        gz, lichun = pp.liunian_ganzhi(y, chart["tz_hours"])
        gan_rel = pp.shishen(day_gan, gz[0])
        zrel = zhi_rel(gz[1], day_zhi)
        # 当年主运：以年中 6 月 30 日为界（交运日跨年时以该日归属为准）
        mid = f"{y}-06-30"
        luck = None
        for step in chart["lucky"]:
            if step["start"] <= mid:
                luck = step
        if luck is None:
            # 交运前：起运前的行运即月柱（v7.8 修复——此前退化成 lucky[0]，
            # 把第一步大运错误套到交运前年份，权重偏差最多 ±6 分 raw；
            # 泰勒交运早且童年先验低所以回测数值恰好未受影响）
            luck = {"ganzhi": chart["month_pillar"], "start": ""}
        dayun_change = any(s["start"][:4] == str(y) for s in chart["lucky"])
        tags = suiyun_rel(gz, luck["ganzhi"])
        a_w = GAN_W.get(gan_rel, (0.0, 0.0))[0] + ZHI_W.get(zrel, (0.0, 0.0))[0]
        t_w = GAN_W.get(gan_rel, (0.0, 0.0))[1] + ZHI_W.get(zrel, (0.0, 0.0))[1]
        if any("并临" in t for t in tags):
            a_w += 0.03
            t_w += 0.03
        if any("合" in t or "冲" in t for t in tags):
            a_w += 0.02
            t_w += 0.02
        rows.append({
            "year": y,
            "liunian": gz,
            "liunian_gan_relation": gan_rel,
            "day_zhi_relation": zrel or "静",
            "dayun": luck["ganzhi"],
            "dayun_gan_relation": pp.shishen(day_gan, luck["ganzhi"][0]),
            "dayun_zhi_relation": zhi_rel(luck["ganzhi"][1], day_zhi) or "静",
            "dayun_since": luck["start"],
            "dayun_change": dayun_change,
            "suiyun": tags,
            "lichun": lichun.strftime("%Y-%m-%d %H:%M"),
            "p_album": clamp(ALBUM_BASE + a_w),
            "p_tour": clamp(TOUR_BASE + t_w),
        })
    return rows


# ---- v1 事业指数规则（生成后不再改；改动须另起版本号并重跑）----
CAREER_RULEBOOK = "v1"
CAREER_LUCK_GAN_W = {"正印": 8, "偏印": 8, "食神": 6, "伤官": 6, "正财": 4,
                     "偏财": 4, "正官": 5, "七杀": 5, "比肩": 2, "劫财": 2}
CAREER_LUCK_ZHI_W = {"六合": 6, "半合": 4, "六冲": 3, "伏吟": 2, "六穿": -3,
                     "刑": -3, "静": 0}
CAREER_YEAR_GAN_W = {"正印": 9, "偏印": 9, "食神": 7, "伤官": 7, "正财": 5,
                     "偏财": 5, "正官": 6, "七杀": 6, "比肩": 3, "劫财": 3}
CAREER_YEAR_ZHI_W = {"六合": 8, "半合": 6, "六冲": 5, "伏吟": 4, "六穿": -4,
                     "刑": -3, "静": 0}
CAREER_HIGH_BASE = 0.20


def age_factor(birth_year: int, year: int) -> float:
    """年龄先验：童年不可能有事业高峰，18 岁起权重 1.0。"""
    age = year - birth_year
    if age < 8:
        return 0.05
    if age < 13:
        return 0.20
    if age < 16:
        return 0.50
    if age < 18:
        return 0.75
    return 1.0


def career_index(row: dict, birth_year: int) -> tuple[int, float, dict]:
    """逐年事业指数（0—100）与「显著高峰年」概率。

    指数 = 50 + 大运十神/大运支关系 + 流年十神/流年支关系 + 岁运项，
    再乘年龄先验。概率 p_high = 0.03 + 0.006*(index-20)，截断 [0.03, 0.75]。
    """
    raw = 50.0
    raw += CAREER_LUCK_GAN_W.get(row["dayun_gan_relation"], 0)
    raw += CAREER_LUCK_ZHI_W.get(row["dayun_zhi_relation"], 0)
    raw += CAREER_YEAR_GAN_W.get(row["liunian_gan_relation"], 0)
    raw += CAREER_YEAR_ZHI_W.get(row["day_zhi_relation"], 0)
    for t in row["suiyun"]:
        if "并临" in t:
            raw += 4
        elif "合" in t or "半合" in t:
            raw += 3
        elif "冲" in t:
            raw += 2
    if row.get("dayun_change"):
        raw += 2
    raw = max(0.0, min(100.0, raw))
    idx = int(round(raw * age_factor(birth_year, row["year"])))
    # 高峰概率下限 0.03（童年年份），与 album/tour 的 0.10 下限区分开
    p_high = round(max(0.03, min(0.75, 0.03 + 0.006 * (idx - 20))), 3)
    comp = {"raw": round(raw, 1), "age_factor": age_factor(birth_year, row["year"]),
            "index": idx, "p_high": p_high}
    return idx, p_high, comp


def build_career_predictions(args, chart, rows) -> dict:
    """出生年起逐年「显著高峰年」判据（rulebook v1）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    birth_year = args.birth_year
    preds = []
    for r in rows:
        idx, p_high, comp = career_index(r, birth_year)
        future = r["year"] > int(args.future_from or 9999)
        item = {
            "id": f"TS2-{r['year']}-high",
            "window": [f"{r['year']}-01-01", f"{r['year']}-12-31"],
            "claim": "该年职业生涯处于显著高峰/大成功状态（按事实评分 rubric 得 ≥4/10）",
            "probability": p_high,
            "base_rate": CAREER_HIGH_BASE,
            "base_rate_source": "头部流行艺人出生至 36 岁期间约 1/5 年份为显著高峰年（作者先验，事实表编译前固定）",
            "falsify": f"{r['year']} 年事实评分（data/taylor_facts_v2.json 的 rubric）< 4",
            "deadline": f"{r['year'] + 1}-03-31",
            "evidence_grade": "A" if future else "B",
            "verdict": "pending",
            "grade_note": "A=事前登记（git 首次提交早于窗口起点）；B=事后回测样本，不计入技巧分数",
            "rule_notes": {
                "career_index": idx,
                "p_high": p_high,
                "components": comp,
                "liunian": r["liunian"],
                "liunian_gan_relation": r["liunian_gan_relation"],
                "day_zhi_relation": r["day_zhi_relation"],
                "dayun": r["dayun"],
                "dayun_change": bool(r.get("dayun_change")),
                "suiyun": r["suiyun"],
            },
        }
        if future and p_high <= CAREER_HIGH_BASE:
            item["low_information"] = True
            item["low_information_reason"] = (
                f"模型 {p_high:.2f} ≤ 基线 {CAREER_HIGH_BASE}，即使命中也不提供信息量")
        preds.append(item)
    return {
        "entity": args.name,
        "entity_type": "human",
        "anchor": f"{args.datetime} UTC{args.tz:+g} lon={args.lon}",
        "chart": " ".join([chart["year_pillar"], chart["month_pillar"],
                           chart["day_pillar"], chart["hour_pillar"]]),
        "chart_note": "出生时刻 DD 级；事业指数规则只依赖年/月/日三柱与两版一致的大运序列",
        "chart_engine": "scripts/pai_pan.py v7.5",
        "rulebook": f"scripts/yearly_bazi.py career rulebook {CAREER_RULEBOOK}（固定权重+年龄先验，见源码）",
        "scoring_rubric": {
            "score_max": 10,
            "high_threshold": 4,
            "items": [
                "+3 全新/重录专辑首周销量 ≥100 万；+2 50—100 万；+1 <50 万（同年多张可叠加）",
                "+2 格莱美年度专辑（AOTY）获奖；+1 AOTY 提名",
                "+3 巡演创历史级票房纪录；+2 巡演启动且总票房 ≥1 亿美元；+1 其他巡演启动",
                "+1 刷新单曲/榜单/流媒体纪录，或获年度艺人级荣誉（TIME 年度人物等）",
                "+1 重大商业里程碑（亿万身家、版权交易、厂牌变动等）",
                "-1 重大公开负面事件主导该年",
                "童年/未出道年份记 0；单项可叠加，封顶 10"
            ],
            "note": "本 rubric 与预测一并固定；事实表在预测 commit 之后按此编译"
        },
        "model": "bazi-entity-v7.5",
        "generated_at": today,
        "note": "过去年份=B 级回测（verify.py 按 git 首次提交时间标 late）；未来年份=A 级事前登记。本文件取代 taylor.json 中 album/tour 口径：专辑发行是过程，本版预测的是事业结果（高峰/大成功）。",
        "predictions": preds,
    }


def score_career(args) -> None:
    with open(args.predictions, encoding="utf-8") as f:
        doc = json.load(f)
    with open(args.score_career, encoding="utf-8") as f:
        facts = json.load(f)
    threshold = float(facts.get("high_threshold", 4.0))
    by_year = {f["year"]: f for f in facts["years"]}
    rows = []
    for p in doc["predictions"]:
        y = int(p["id"].split("-")[1])
        fact = by_year.get(y)
        if fact is None or "score" not in fact:
            continue
        high = float(fact["score"]) >= threshold
        p["verdict"] = "hit" if high else "miss"
        rows.append((p, high, float(fact["score"])))
    base = CAREER_HIGH_BASE
    bs_m = sum((p["probability"] - (1.0 if h else 0.0)) ** 2 for p, h, _ in rows) / len(rows)
    bs_b = sum((base - (1.0 if h else 0.0)) ** 2 for p, h, _ in rows) / len(rows)
    skill = 1.0 - bs_m / bs_b if bs_b else None
    print(f"[career-high] n={len(rows)} 命中={sum(h for _, h, _ in rows)} "
          f"模型Brier={bs_m:.4f} 基线Brier={bs_b:.4f} 技巧分数={skill:+.3f}")
    xs = [float(p["rule_notes"]["career_index"]) for p, _, _ in rows]
    ys = [s for _, _, s in rows]
    pear = _pearson(xs, ys)
    spear = _spearman(xs, ys)
    print(f"[career-index vs fact-score] Pearson r={pear:+.3f}  Spearman rho={spear:+.3f}")
    for p, h, s in rows:
        mark = "✓" if h else "✗"
        print(f"{mark} {p['id']} index={p['rule_notes']['career_index']:>3} "
              f"p={p['probability']:.2f} fact={s:.1f} -> {p['verdict']}")
    with open(args.predictions, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"verdicts written back to {args.predictions}")


def _pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return 0.0 if vx == 0 or vy == 0 else cov / (vx * vy)


def _spearman(xs, ys):
    def ranks(a):
        order = sorted(range(len(a)), key=lambda i: a[i])
        r = [0] * len(a)
        for pos, i in enumerate(order):
            r[i] = pos + 1
        return r
    return _pearson(ranks(xs), ranks(ys))


def build_predictions(args, chart, rows) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    preds = []
    for r in rows:
        y = r["year"]
        future = y > int(args.future_from or 9999)
        grade = "A" if future else "B"
        for kind, key in (("album", "p_album"), ("tour", "p_tour")):
            prob = r[key]
            base = 0.50 if kind == "album" else 0.32
            claim = {
                "album": "该年发行一张全新录音室专辑（不含 Taylor's Version 重录版）",
                "tour": "该年启动一轮新的全球巡回演唱会（首场举办日落在该年）",
            }[kind]
            item = {
                "id": f"T-{y}-{kind}",
                "window": [f"{y}-01-01", f"{y}-12-31"],
                "claim": claim,
                "probability": prob,
                "base_rate": base,
                "base_rate_source": "2006—2024 实测：新专辑年 10/19≈0.53 取 0.50；新巡演启动年 6/19≈0.32",
                "falsify": {
                    "album": "权威媒体/官方渠道在该年内无新录音室专辑发行记录",
                    "tour": "权威媒体/官方渠道在该年内无新巡演首场",
                }[kind],
                "deadline": f"{y + 1}-03-31",
                "evidence_grade": grade,
                "verdict": "pending",
                "grade_note": "A=事前登记（git 首次提交早于窗口起点）；B=事后回测样本，不计入技巧分数",
                "rule_notes": {
                    "liunian": r["liunian"],
                    "liunian_gan_relation": r["liunian_gan_relation"],
                    "day_zhi_relation": r["day_zhi_relation"],
                    "dayun": r["dayun"],
                    "suiyun": r["suiyun"],
                },
            }
            if future and prob <= base:
                item["low_information"] = True
                item["low_information_reason"] = (
                    f"模型 {prob} ≤ 基线 {base}，即使命中也不提供信息量")
            preds.append(item)
    for y in args.biz_years:
        row = next((r for r in rows if r["year"] == y), None)
        if row is None:
            continue
        prob = 0.45
        # 商业节点判据：换大运/日柱伏吟/岁运冲合并现时给高值
        boost = any(t in row["suiyun"] for t in ("岁运支冲", "岁运支合", "岁运干并临"))
        if row["day_zhi_relation"] == "伏吟":
            prob += 0.05
        if boost:
            prob += 0.05
        prob = clamp(prob)
        item = {
            "id": f"T-{y}-biz",
            "window": [f"{y}-01-01", f"{y}-12-31"],
            "claim": "该年出现重大商业/版权/合约层面公告（重录版权回购、厂牌变动、版权出售或同等量级）",
            "probability": prob,
            "base_rate": 0.30,
            "base_rate_source": "一名头部艺人某一特定年份发生同等量级商业公告的概率（作者估计）",
            "falsify": "该年内无任何公开报道的同等量级商业/版权/合约公告",
            "deadline": f"{y + 1}-03-31",
            "evidence_grade": "A" if y > int(args.future_from or 9999) else "B",
            "verdict": "pending",
            "grade_note": "同上",
            "rule_notes": {
                "liunian": row["liunian"],
                "day_zhi_relation": row["day_zhi_relation"],
                "dayun": row["dayun"],
                "suiyun": row["suiyun"],
            },
        }
        preds.append(item)
    return {
        "entity": args.name,
        "entity_type": "human",
        "anchor": f"{args.datetime} UTC{args.tz:+g} lon={args.lon}",
        "chart": " ".join([chart["year_pillar"], chart["month_pillar"],
                           chart["day_pillar"], chart["hour_pillar"]]),
        "chart_note": "出生时刻 DD 级（5:17 与 8:36 冲突）；本表用 08:36。逐年规则只依赖年/月/日三柱与两版一致的大运序列，时柱不参与",
        "chart_engine": "scripts/pai_pan.py v7.5",
        "rulebook": f"scripts/yearly_bazi.py rulebook {RULEBOOK_VERSION}（固定权重，见源码）",
        "model": "bazi-entity-v7.5",
        "generated_at": today,
        "note": "过去年份=B 级回测，verify.py 按 git 首次提交时间会将其标记 late、不计 A 级；未来年份=A 级事前登记。回填纪律见 predictions/README.md",
        "predictions": preds,
    }


def score(args) -> None:
    with open(args.predictions, encoding="utf-8") as f:
        doc = json.load(f)
    with open(args.score, encoding="utf-8") as f:
        facts = json.load(f)
    by_year = {f["year"]: f for f in facts["years"]}
    rows = []
    for p in doc["predictions"]:
        y = int(p["id"].split("-")[1])
        kind = p["id"].split("-")[2]
        if kind not in ("album", "tour"):
            continue
        fact = by_year.get(y)
        if fact is None:
            continue  # 事实表未覆盖的年份保持 pending，绝不回填
        outcome = bool(fact.get(f"{kind}_launch" if kind == "tour" else "new_album"))
        p["verdict"] = "hit" if outcome else "miss"
        rows.append((p, outcome))
    # Brier / 技巧分数（含全体年份的模型概率 vs 固定基线）
    for kind in ("album", "tour"):
        sub = [(p, o) for p, o in rows if p["id"].endswith(f"-{kind}")]
        base = 0.50 if kind == "album" else 0.32
        bs_m = sum((p["probability"] - (1.0 if o else 0.0)) ** 2 for p, o in sub) / len(sub)
        bs_b = sum((base - (1.0 if o else 0.0)) ** 2 for p, o in sub) / len(sub)
        skill = 1.0 - bs_m / bs_b if bs_b else None
        print(f"[{kind}] n={len(sub)} 命中={sum(o for _, o in sub)} "
              f"模型Brier={bs_m:.4f} 基线Brier={bs_b:.4f} 技巧分数={skill:+.3f}")
    for p, o in rows:
        mark = "✓" if o else "✗"
        print(f"{mark} {p['id']} p={p['probability']:.2f} -> {p['verdict']}")
    with open(args.predictions, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"verdicts written back to {args.predictions}")


def main():
    ap = argparse.ArgumentParser(description="逐年岁运预测生成/打分 (BFFT v7.5)")
    ap.add_argument("datetime")
    ap.add_argument("--name", required=True)
    ap.add_argument("--tz", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--gender", choices=["male", "female"], default="female")
    ap.add_argument("--from", dest="from_year", type=int, required=True)
    ap.add_argument("--to", dest="to_year", type=int, required=True)
    ap.add_argument("--future-from", type=int, default=9999,
                    help="该年之后的年份登记为 A 级事前；过去年份为 B 级回测")
    ap.add_argument("--biz-years", type=int, nargs="*", default=[],
                    help="额外登记商业节点判据的年份")
    ap.add_argument("--career", action="store_true",
                    help="用 rulebook v1 生成逐年事业指数/显著高峰年判据（取代专辑/巡演口径）")
    ap.add_argument("--birth-year", type=int, default=None,
                    help="出生年份（--career 模式年龄先验用）")
    ap.add_argument("--write", help="写出 predictions JSON")
    ap.add_argument("--score", help="事实表 JSON（专辑/巡演打分模式）")
    ap.add_argument("--score-career", help="事业事实表 JSON（事业打分模式）")
    ap.add_argument("--predictions", default="")
    args = ap.parse_args()

    dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    chart = pp.calc(dt, tz_hours=args.tz, lon=args.lon, gender=args.gender,
                    day_boundary="zi", calendar="gregorian", lucky_count=10)
    if args.score:
        score(args)
        return
    if args.score_career:
        score_career(args)
        return
    if args.career and args.birth_year is None:
        ap.error("--career 模式必须给 --birth-year")
    rows = yearly_rows(chart, args.from_year, args.to_year)
    if args.career:
        doc = build_career_predictions(args, chart, rows)
        if args.write:
            os.makedirs(os.path.dirname(os.path.abspath(args.write)), exist_ok=True)
            with open(args.write, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"wrote {len(doc['predictions'])} career predictions -> {args.write}")
        print(f"{'年':<6}{'流年':<5}{'干':<5}{'日支':<5}{'大运':<5}{'指数':<6}{'P高峰':<7}岁运/交运")
        for r in rows:
            idx, ph, _ = career_index(r, args.birth_year)
            extra = ("交运" if r.get("dayun_change") else "") + (
                "; " + ";".join(r["suiyun"]) if r["suiyun"] else "")
            print(f"{r['year']:<6}{r['liunian']:<5}{r['liunian_gan_relation']:<5}"
                  f"{r['day_zhi_relation']:<5}{r['dayun']:<5}{idx:<6}{ph:<7.2f}{extra or '-'}")
        return
    doc = build_predictions(args, chart, rows)
    if args.write:
        os.makedirs(os.path.dirname(os.path.abspath(args.write)), exist_ok=True)
        with open(args.write, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {len(doc['predictions'])} predictions -> {args.write}")
    print(f"{'年':<6}{'流年':<5}{'干关系':<5}{'日支':<5}{'大运':<5}{'专辑P':<7}{'巡演P':<7}岁运")
    for r in rows:
        print(f"{r['year']:<6}{r['liunian']:<5}{r['liunian_gan_relation']:<5}"
              f"{r['day_zhi_relation']:<5}{r['dayun']:<5}{r['p_album']:<7.2f}{r['p_tour']:<7.2f}"
              f"{';'.join(r['suiyun']) or '-'}")


if __name__ == "__main__":
    main()
