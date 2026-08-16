#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BFFT 分发包打包脚本。

把仓库的可分发文件打成 dist/BFFT.zip（zip 内根目录为 BFFT/），
与历史分发包结构一致；另在包根放 docs/usage.md 的同内容副本「使用文档.md」。

用法:
  python scripts/build_dist.py
"""

from __future__ import annotations

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "BFFT.zip")

EXCLUDE_DIRS = {".git", ".github", "dist", "__pycache__", ".pytest_cache",
                "node_modules"}
EXCLUDE_FILES = {".DS_Store"}
INCLUDE_SUFFIXES = (".py", ".mjs", ".md", ".json", ".csv", ".yaml")
INCLUDE_NAMES = {"LICENSE"}


def collect() -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if fn in EXCLUDE_FILES:
                continue
            if not (fn.endswith(INCLUDE_SUFFIXES) or fn in INCLUDE_NAMES):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            files.append((full, f"BFFT/{rel.replace(os.sep, '/')}"))
    return files


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    files = collect()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, arc in files:
            z.write(full, arc)
        # 历史包根目录带使用文档副本（与 docs/usage.md 同内容）
        z.write(os.path.join(ROOT, "docs", "usage.md"), "BFFT/使用文档.md")
    size = os.path.getsize(OUT)
    print(f"dist/BFFT.zip: {len(files)} 个文件 + 使用文档.md 副本，{size:,} bytes")


if __name__ == "__main__":
    main()
