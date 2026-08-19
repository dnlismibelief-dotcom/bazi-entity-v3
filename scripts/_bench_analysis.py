# -*- coding: utf-8 -*-
"""BFFT 错题归因分析：按类别统计准确率、选项偏差、错题清单。"""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

pack = json.load(open("data/mingli_bench/mingli-pack.json", encoding="utf-8"))
ans = json.load(open("data/mingli_bench/mingli-pack-ans.json", encoding="utf-8"))
truth_data = json.load(open("data/mingli_bench/data.json", encoding="utf-8"))

items = pack["items"]
ans_map = {a["id"]: a for a in ans["items"]}
truth_map = {q["id"]: q for q in truth_data["questions"]}
print(f"pack items: {len(items)}, ans items: {len(ans_map)}, truth items: {len(truth_map)}")

rows = []
for it in items:
    a = ans_map.get(it["id"])
    t = truth_map.get(it["id"])
    if a is None or t is None:
        continue
    rows.append({
        "id": it["id"],
        "cat": it.get("category", "?"),
        "model": a.get("answer"),
        "truth": t.get("answer"),
    })

by_cat = {}
for r in rows:
    c = by_cat.setdefault(r["cat"], {"n": 0, "ok": 0})
    c["n"] += 1
    if r["model"] == r["truth"]:
        c["ok"] += 1

print("\n=== 按类别准确率 ===")
for cat, c in sorted(by_cat.items(), key=lambda kv: kv[1]["ok"] / max(kv[1]["n"], 1)):
    print(f"  {cat}: {c['ok']}/{c['n']} ({c['ok']/c['n']:.0%})")

total_ok = sum(1 for r in rows if r["model"] == r["truth"])
print(f"\n总计: {total_ok}/{len(rows)} ({total_ok/len(rows):.0%})  随机基线 25%")

print("\n=== 模型选项分布（看有没有偏好偏差）===")
print("  model:", dict(Counter(r["model"] for r in rows)))
print("  truth:", dict(Counter(r["truth"] for r in rows)))

print("\n=== 错题清单 ===")
for r in rows:
    if r["model"] != r["truth"]:
        q = next((x.get("question", "") for x in items if x["id"] == r["id"]), "")
        print(f"  {r['id']} [{r['cat']}] 模型答 {r['model']} / 真值 {r['truth']}  |  {q[:50]}")
