# lunar_python 交叉验证与候选模型融合评估（v7.9）

## 1. 融合了什么

`scripts/crosscheck_lunar.py`（可选依赖 `lunar_python`，MIT，6tail 农历库）：
把成熟的外部历法库作为 **BFFT 排盘的第二个独立参照**（第一个是 iztro/MingLi-Bench 160 例）。
脚本不进入主流程与 CI，保持 BFFT 零依赖纪律。

## 2. 验证结果（464 例 = 大赛 160 + 四实体 4 + 随机 fuzz 300）

| 口径 | 年柱 | 月柱 | 日柱 | 时柱 | 四柱全同 |
|---|---|---|---|---|---|
| 默认（zi 换日 + 夏令时 auto） | 100% | 100% | 96.1% | 98.1% | 94.2% |
| 对齐（midnight + 关夏令时） | 100% | 100% | **100%** | 96.1% | 96.1% |

## 3. 差异 100% 归因（无 BFFT 排盘错误）

| 差异 | 案例 | 归因 |
|---|---|---|
| 日柱（默认口径 18 例） | 全部 23:00-23:59 出生 | **换日流派**：BFFT zi（23 点换日）vs lunar 午夜换日。--align 后 100% |
| 时柱（对齐口径 18 例） | 全部 23:00-23:59 出生 | **lunar 是混合流派**：日柱午夜换、时柱天干按子初换日后的日干起五鼠遁（1966-10-18 23:15：日柱庚戌当天、时柱戊子=次日辛日起）。BFFT 两派都是日柱/时柱联动，更自洽；默认 zi 模式下 BFFT 时柱与 lunar 完全一致 |
| 时柱（默认口径 9 例） | 1990/1987/1988 夏令时窗口出生 | **夏令时口径**：BFFT 按 1986-1991 官方表自动回拨 1 小时（正确），lunar 不回拨 |

结论：年柱/月柱双参照 100% 一致；日柱/时柱差异全部可归因为流派/口径，与 v7.6 iztro 验证（月日柱 100%）互相印证。

## 4. 候选模型扫描结论（无可抄代码，但确认了 BFFT 的定位）

扫描了 [xuziping-bazi](https://github.com/nihe0909/xuziping-bazi)（排盘依赖 sxtwl）、
[bazi-skill](https://github.com/gaoxin492/bazi-skill)（计算层+JSON+Agent 三层）、
[fortune-skill](https://github.com/ai-freer/fortune-skill)（八字+紫微，非商用协议）、
[horosa-skill](https://github.com/Horace-Maxwell/horosa-skill)（92 术数 MCP，AGPL）：

- 共同点：**排盘引擎全部依赖第三方库**（sxtwl/lunar），BFFT 是零依赖自研且能力更全
  （真太阳时/ΔT 分段/历法声明/换日流派/夏令时地域化），v7 时代已用 sxtwl+lunar_python
  做过交叉验证、v7.6 又过 iztro 160 例、本次再过 lunar_python 464 例——**三重独立参照**。
- 协议考量：fortune-skill 非商用、horosa-skill AGPL，均不适合融合进 MIT 系仓库。
- 可借鉴理念（不抄码）：bazi-skill 的"命盘存档/持续追问"（BFFT 每次重排盘，无档案层）、
  horosa-skill 的"AI 不许乱补参数"（BFFT 的 CLI 已实现：非法参数直接报错）。
- **行业空白确认**：没有找到"游戏/IP 实体寿命预测"类开源命理模型——J-08/J-09 的
  本体/IP 分层是本仓库独有设计。

## 5. 复现

```bash
pip install lunar_python
python scripts/crosscheck_lunar.py            # 默认口径
python scripts/crosscheck_lunar.py --align    # 对齐口径（midnight+no-dst）
```
