---
name: bazi-entity-v3
description: Analyze the fortune, life trajectory, popularity, revenue, and lifespan of any entity — a person (human 八字), game, product, or company — using the v4 BaZi (四柱八字/命理) model distilled from 《千里命稿》《子平真诠》《滴天髓》 and modern annotations. Use when asked to apply Chinese metaphysics/八字/命理 to a person's birth chart or to a game/product/company (e.g., 鸣潮, 英雄联盟, 三角洲行动); predict life stages, career/wealth/marriage windows, popularity or shutdown years, revenue scale; or calibrate previous predictions against real events. Includes deterministic chart calculation (scripts/pai_pan.py), six-module pipeline (root/pattern/body-use/climate/timing/calibration), entity-type lifespan scaling, 寿元星 rules, dual six-relative systems, and evidence-graded calibration workflow.
---

# BaZi Entity Analysis (v4) — 万物命理

## Overview

v4 模型 = 三书融合（《千里命稿》实用批命 ＋《子平真诠》格局体系 ＋《滴天髓》气象理气 ＋ 梁湘潤今註现代制式）＋ 现代工程化（概率化、可证伪、可归因）。

层次原则：**强弱 < 格局 < 气象 < 调候**。神煞不作格局成败依据；调候为急可超越中和；结论带置信度与条件句。

## Workflow

### 1. 确定实体类型与锚点

先定 `entity_type`（human / game / product / company），再收集锚点时间（缺失先问，不猜）。human 用真实性别；game/product 默认 male（阳年男顺排）。

### 2. 排盘

```bash
python scripts/pai_pan.py "2024-05-23 10:00" --name 鸣潮 --lucky 10 --years 12
python scripts/pai_pan.py "1990-01-01 10:00" --name "示例人盘" --gender female --lucky 10 --years 12
python scripts/pai_pan.py "2017-03-02 10:00" --name "某公司实体" --json
```

有条件时与万年历核对日柱；用 `--json` 喂后续模块。

### 3. 六模块管线（先读 references/v4-spec.md）

- **M1 排盘与根气**：天覆地载、根重次序（长生禄刃 > 墓库余气 > 比肩）、得时不旺/失时不弱。
- **M2 格局引擎**：月令定格、顺逆、成败、带忌/救应、相神、纯杂高低、变化、杂气、墓库刑冲、外格用舍。
- **M3 体用喜忌**：多级体用、用神/相神、病药三分、强弱降权、四吉神破格/四凶神成格。
- **M4 气象调候**：源流、通关、寒暖燥湿、众寡、顺逆从化、清浊、真神假神、隐显、形象方局、战局合局。
- **M5 时序引擎**：大运成格变格、流年/月建干支并看、岁运战冲和好、透清、贞元代际、寿元三关。
- **M6 实证校准**：证据分级 A/B/C、假设—反证归因、概率化输出、多方案对比。

human 盘另读 [references/human.md](references/human.md)（六亲双轨、人生阶段、隐私纪律）。

### 4. 实体寿命缩放

| entity_type | 寿命基准 | 主程（前几步大运） | 大限窗口 |
|---|---|---|---|
| human | 70—90 年 | 前 6—7 步 | 第 8 步以后 |
| game | 5—15 年 | 前 2 步 | 第 10—13 年 |
| product | 5—20 年 | 前 2 步 | 第 10—15 年 |
| company | 20—100 年 | 前 4—6 步 | 第 6 步以后 |

寿元星三关：一创＝重伤可过；二创＝衰退；三创＝大限。库护寿元难杀。

### 5. 输出格式（v4）

- 排盘与根气表；格局判定（含相神与带忌/救应）；体用喜忌（含置信度与备选方案）；气象分析（源流/通关/调候）；时序表（大运成格变格、流年干支并看、岁运战冲和好、寿元三关）。
- 判据清单：至少 3 条 A 级事前预测，每条含时间窗、判定标准、数据源、所依赖假设。
- 六亲（human）：双轨并列（父印系 vs 父偏财系）＋宫位法。

## Resources

- [references/v4-spec.md](references/v4-spec.md) — v4 完整规范（六模块、六亲双轨、v3→v4 升级清单）。深度分析必读。
- [references/model-v3.md](references/model-v3.md) — 旧版规范与行业映射（game/product/company 通用概念仍有效）。
- [references/human.md](references/human.md) — 人盘专用（六亲、人生阶段、隐私）。
- [references/calibration.md](references/calibration.md) — 校准档案 schema、鸣潮 worked example、权重规则。
- [scripts/pai_pan.py](scripts/pai_pan.py) — 排盘 CLI（支持 JSON）。

## Guardrails

- 文化娱乐性质：不宣称科学预测，不作为投资/医疗/婚恋决策依据。
- 证据分级：校准只计 A 级（事前、可查证）；B/C 级只作参考。
- 隐私：human 盘不落盘可识别信息；校准记录只存事件与干支。
- 不虚构事实：事件、流水、销量引用公开可查来源并注明口径。
- 门派分歧（如六亲、强弱、墓库）并列输出，不作独断。
