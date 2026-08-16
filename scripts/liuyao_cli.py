#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻排盘 CLI — BFFT v7.15（前端；引擎在 scripts/liuyao/paipan.py）。

用法:
  # 手动六爻编码（1=少阴 2=少阳 3=老阳动 4=老阴动，自初爻至上爻）
  python scripts/liuyao_cli.py --yao "123121" --dt "2026-08-16 23:00" --subject 问事

  # 随机摇卦（三币法）
  python scripts/liuyao_cli.py --random --dt "2026-08-16 23:00" --subject 问事

许可：本模块整合 xiongdun8/liuyao（MIT）与 Seanding1998/liuyao-frv 格局思路
（个人免费·商业授权——仅限个人/学习/研究使用，商业使用请联系原作者）。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.liuyao.paipan import liuyao_calc  # noqa: E402


def random_yao() -> list[int]:
    """三币摇卦：3 正面=老阳(3) 3 反面=老阴(4) 两正一反=少阳(2) 两反一正=少阴(1)。"""
    codes = []
    for _ in range(6):
        heads = sum(random.randint(0, 1) for _ in range(3))
        codes.append({0: 4, 1: 1, 2: 2, 3: 3}[heads])
    return codes


def main():
    ap = argparse.ArgumentParser(description="六爻排盘 (BFFT v7.15)")
    ap.add_argument("--yao", help='六爻编码 6 位(1=少阴 2=少阳 3=老阳 4=老阴), 自初爻至上爻')
    ap.add_argument("--random", action="store_true", help="三币随机摇卦")
    ap.add_argument("--dt", default="", help='起卦时间 "YYYY-MM-DD HH:MM"（默认当前时间）')
    ap.add_argument("--tz", type=float, default=8.0)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--subject", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.yao and args.random:
        ap.error("--yao 与 --random 二选一")
    if args.yao:
        codes = [int(c) for c in args.yao]
    elif args.random:
        codes = random_yao()
    else:
        ap.error("需提供 --yao 或 --random")

    from datetime import datetime
    dt_s = args.dt or datetime.now().strftime("%Y-%m-%d %H:%M")
    result = liuyao_calc(codes, dt_s, tz=args.tz, lon=args.lon, subject=args.subject)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        o, c = result["original"], result["changed"]
        print(f"排盘时间: {result['cast_time']}  日辰: {result['day_gz']}  月建: {result['month_branch']}")
        print(f"旬空: {'、'.join(result['xunkong'])}")
        print(f"本卦: {o['name']}（{o['gong']}·{o['type']}） 世{o['shi']} 应{o['ying']}")
        if c:
            print(f"变卦: {c['name']}（{c['gong']}·{c['type']}） 动: {'、'.join(result['moving_positions'])}")
        print(f"格局: {'、'.join(result['patterns']) if result['patterns'] else '—'}")
        print("爻  | 六神 | 六亲 | 地支五行 | 爻象 | 旺衰状态")
        for ln in result["lines"]:
            mark = " ○" if ln["moving"] else "  "
            ch = f" → {ln['changed_branch']}{ln['changed_liuqin'] or ''}" if ln["moving"] else ""
            print(f"{ln['pos']} | {ln['liushen']} | {ln['liuqin']} | {ln['branch']}{ln['wuxing']} | "
                  f"{ln['symbol']}{mark} | {'、'.join(ln['status']) or '—'}{ch}")
        print("（许可: MIT + liuyao-frv 个人使用授权; 娱乐参考, 不作决策依据）")


if __name__ == "__main__":
    main()
