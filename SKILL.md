---
name: bazi-entity-v3
description: Analyze the fortune, life trajectory, popularity, revenue, and lifespan of any entity — a person (human 八字), game, product, or company — using a calibrated BaZi (四柱八字/命理) model v3. Use when asked to apply Chinese metaphysics/八字/命理 to a person's birth chart, or to a game/product/company (e.g., 鸣潮, 英雄联盟, 三角洲行动); predict life stages, career/wealth/marriage windows, popularity or shutdown years, revenue scale; or calibrate previous predictions against real events. Includes deterministic chart calculation (scripts/pai_pan.py), entity-type lifespan scaling, 寿元星 lifespan rules, 六亲 axes for humans, multi-anchor version-chart analysis, and evidence-graded calibration workflow.
---

# BaZi Entity Analysis (v3) — 万物命理

## Overview

v3 模型 = 气学坐标（历法锚点）＋子平体用（格局/调候/旺衰）＋象法应期（寿元星/刑冲合会/库象/纳音神煞）＋实证校准（证据分级/命中率/权重迭代）。

同一套底层逻辑适用于人、游戏、产品、公司——差异只在寿命标尺、主要输出轴与校准数据源，用 `entity_type` 一个参数切换。

## Workflow

### 1. 确定实体类型与锚点

先定 `entity_type`，再收集锚点时间（缺失时先问，不要猜）：

| entity_type | 主锚 | 可选次锚 |
|---|---|---|
| human | 出生日期时间（默认 UTC+8） | 无（大运流年即应期） |
| game | 公测/上线时间 | 大版本时间、公司实体成立日 |
| product | 发布/上市时间 | 大版本、公司实体 |
| company | 成立/改名/上市时间 | 关键产品发布 |

起盘性别：game/product 默认 `male`（阳年男顺排）；human 按真实性别。

### 2. 排盘

```bash
python scripts/pai_pan.py "2024-05-23 10:00" --name 鸣潮 --lucky 10 --years 12
python scripts/pai_pan.py "1990-01-01 10:00" --name "示例人盘" --gender female --lucky 10 --years 12
python scripts/pai_pan.py "2017-03-02 10:00" --name "某公司实体" --json
```

有条件时与万年历交叉核对日柱；用 `--json` 喂给后续分层。

### 3. 按实体类型分层解读

- **human**：先读 [references/human.md](references/human.md)。输出事业/财运/婚姻/健康/子女/学业六轴、大运人生阶段、流年应期；校准靠本人反馈，注意隐私。
- **game / product / company**：先读 [references/model-v3.md](references/model-v3.md)。按 L1 多锚点 → L2 体用格局 → L3 象法应期 → L4 实证校准执行。
- 通用四层：L1 锚点校验；L2 体用格局（体＝日主/本体，用＝财官/调候）；L3 寿元星＋冲穿制绝＋库象＋天地合/伏吟＋半定量；L4 证据分级（A 事前可查 / B 复盘 / C 模糊）。

### 4. 按实体类型做寿命缩放

统一规则：寿元星三关（一创＝重伤可过，二创＝衰退，三创＝大限）；大运刻度 10 年不变，但“主程”与“暮年”窗口随类型缩放：

| entity_type | 寿命基准 | 主程（前几步大运） | 大限窗口 |
|---|---|---|---|
| human | 70—90 年 | 前 6—7 步（少年到晚年） | 第 8 步以后 |
| game | 5—15 年 | 前 2 步 | 第 10—13 年 |
| product | 5—20 年 | 前 2 步 | 第 10—15 年 |
| company | 20—100 年 | 前 4—6 步 | 第 6 步以后 |

### 5. 输出格式

- 定性结论：热度/成就等级、格局形态（如灯烛之火/太阳之火）、体用关系。
- 应期表：年份 | 干支 | 对寿元星/用神作用 | 判断。
- 半定量：量级区间（human 用“旺/平/弱”档位；game/company 用公开口径校准，±30% 算方向命中）。
- 判据清单：至少 3 条 A 级事前预测，每条含时间窗、判定标准、数据源（human 用可回访的本人事件）。

## Resources

- [references/model-v3.md](references/model-v3.md) — 完整模型规范（四层架构、寿元星、库象、术语、行业映射）。game/product/company 必读。
- [references/human.md](references/human.md) — 人盘专用规范（六亲、人生阶段、健康/婚姻/事业轴、隐私纪律）。human 必读。
- [references/calibration.md](references/calibration.md) — 校准档案 schema、鸣潮 worked example、权重调整规则。做校准或调权重时读。
- [scripts/pai_pan.py](scripts/pai_pan.py) — 排盘 CLI（四柱/纳音/藏干/十神/长生/神煞/大运/流年，支持 JSON），人、游戏、公司通用。

## Guardrails

- 文化娱乐性质：不宣称科学预测，不作为投资/医疗/婚恋决策依据。
- 证据分级：校准档案只计 A 级（事前、可查证）命中；B/C 级只作参考。
- 隐私：human 盘不落盘个人可识别信息（姓名/生日可脱敏）；校准记录只存事件与干支。
- 不虚构事实：事件、流水、销量必须引用公开可查来源并注明口径。
- 歧义时声明假设（性别/换日时辰/真太阳时/时区），并在判据中留出误差空间。
