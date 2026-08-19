#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MingLi-Bench LLM 依据审计 — BFFT v7.19.

不再只记 ABCD：每题输出"依据 + 答案"，供人工复盘判据用得对不对。
分数仅作趋势参考，不作为调参目标（项目定位：可证伪的事前预测，
MingLi-Bench 选择题只是弱信号）。

凭据：环境变量 DEEPSEEK_API_KEY；否则读 $DSH_HOME/.credentials.yaml。

用法:
    python scripts/mingli_bench_llm.py --label audit-001 --limit 5
    python scripts/mingli_bench_llm.py --label audit-001 --model deepseek-chat
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_PATH = os.path.join(ROOT, "dist", "mingli-pack.json")
TRUTH_PATH = os.path.join(ROOT, "data", "mingli_bench", "data.json")
RESULT_DIR = os.path.join(ROOT, "data", "mingli_bench", "results")
DSH_HOME = os.environ.get("DSH_HOME", r"E:\data\DeepSeekHarness\home")


def api_key() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    cred = os.path.join(DSH_HOME, ".credentials.yaml")
    if os.path.exists(cred):
        text = open(cred, encoding="utf-8").read()
        m = re.search(r"^DEEPSEEK_API_KEY:\s*[\"']?([^\"'\s]+)", text, re.M)
        if m:
            return m.group(1)
    raise SystemExit("未找到 DEEPSEEK_API_KEY（环境变量或 .credentials.yaml）")


def ask_one(item: dict, base_url: str, model: str, effort: str) -> tuple[str | None, str]:
    """返回 (答案字母或 None, 依据文本)。"""
    options = "\n".join(f"{o['letter']}. {o['text']}" for o in item["options"])
    prompt = (
        "你是资深命理师。基于四柱盘面与 BFFT 判据（clues）推演。\n"
        "格式严格如下，先依据后答案：\n"
        "依据：<30字内，点名所据判据>\n"
        "答案：<A/B/C/D>\n\n"
        f"题目：{item['question']}\n"
        f"选项：\n{options}\n\n"
        f"四柱：{item['chart']['four_pillars']}\n"
        f"日主：{item['chart']['day_master']}\n\n"
        f"判据：{item.get('clues', '')}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 4000,
    }
    if effort:
        payload["reasoning_effort"] = effort
    req = urllib.request.Request(base_url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key()}",
    })
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    text = (data["choices"][0]["message"].get("content") or "").strip()
    reason = ""
    m = re.search(r"依据\s*[:：]\s*(.+)", text)
    if m:
        reason = m.group(1).split("答案")[0].strip()[:200]
    ans = None
    m = re.search(r"答案\s*[:：]\s*([A-Da-d])", text)
    if m:
        ans = m.group(1).upper()
    else:
        m = re.search(r"\b([A-D])\b", text)
        ans = m.group(1).upper() if m else None
    return ans, reason


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="audit-001")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--base-url", default=os.environ.get("BFFT_LLM_URL", "https://api.deepseek.com/chat/completions"))
    ap.add_argument("--model", default=os.environ.get("BFFT_LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--effort", default=os.environ.get("BFFT_LLM_EFFORT", ""))
    args = ap.parse_args()

    pack = json.load(open(PACK_PATH, encoding="utf-8"))
    truth = {q["id"]: q["answer"] for q in json.load(open(TRUTH_PATH, encoding="utf-8"))["questions"]}
    items = pack["items"][: args.limit] if args.limit else pack["items"]

    detail = []
    for i, it in enumerate(items, 1):
        ans, reason = ask_one(it, args.base_url, args.model, args.effort)
        ok = ans == truth.get(it["id"])
        detail.append({"id": it["id"], "cat": it["category"], "answer": ans,
                       "truth": truth.get(it["id"]), "correct": ok, "reason": reason})
        print(f"[{i}/{len(items)}] {it['id']} [{it['category']}] 答 {ans or '-'} / 真 {truth.get(it['id'])} "
              f"{'✓' if ok else '✗'}  依据: {reason[:40]}", flush=True)

    n = len(detail)
    correct = sum(1 for d in detail if d["correct"])
    by_cat = {}
    for d in detail:
        c = by_cat.setdefault(d["cat"], {"n": 0, "ok": 0})
        c["n"] += 1
        if d["correct"]:
            c["ok"] += 1

    out = {
        "label": args.label,
        "mode": "依据审计（分数仅趋势参考，不为调参目标）",
        "model": args.model,
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else 0,
        "random_baseline": 0.25,
        "by_category": {k: {"ok": v["ok"], "n": v["n"], "acc": round(v["ok"] / v["n"], 4)}
                        for k, v in by_cat.items()},
        "detail": detail,
    }
    os.makedirs(RESULT_DIR, exist_ok=True)
    path = os.path.join(RESULT_DIR, f"mingli-pack-ans.{args.label}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{args.label}: {correct}/{n}（趋势参考）  → 审计明细 {path}", flush=True)
    for k, v in sorted(by_cat.items(), key=lambda kv: kv[1]["ok"] / max(kv[1]["n"], 1)):
        print(f"  {k}: {v['ok']}/{v['n']}", flush=True)


if __name__ == "__main__":
    main()
