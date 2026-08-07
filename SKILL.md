---
name: BFFT
description: Apply Chinese BaZi (四柱八字/命理) to any entity — person, game, product, or company — to read life trajectory, popularity, revenue, and lifespan windows. Use for birth-chart analysis, for a game/product launch date (e.g. 鸣潮, 三角洲行动), or to calibrate past predictions against real events.
---

# BFFT · BaZi Entity Analysis (v7) — 万物命理

## Overview

v6 = v5 的工程体系 ＋ 第二轮五书贯通
（《三命通会》集大成规则库 ＋《渊海子平》子平本源 ＋《神峰通考》病药八法与谬说批判
＋《协纪辨方书》择吉/历法考据 ＋《果老星宗》平行星命参照），
并对 v4 已融合的《千里命稿》《子平真诠》《滴天髓》回头复核。
八书解读、可验证性分级与不采用清单见 [classics-v6.md](references/classics-v6.md)。

层次原则：**强弱 < 格局 < 气象 < 调候**。神煞不作格局成败依据；调候为急可超越中和；
结论带置信度与条件句。门派分歧并列输出，不作独断。

v6 新增最要紧的三条：**病药八法**（雕枯旺弱 × 损益生长，M3）、
**岁运四分类**（战冲和好，M5）与**断语三级制**（S 结构化规则 / C 文化注记 / X 不采用，M6）。
工程层 v7：真太阳时、夏令时（只对东八区）、换日两派、胎元两派、
输入历法声明（`--calendar`）、节气核对、预测事前登记。
v7 修正了 ΔT 适用年限与节气求根收敛 —— v6 及以前 1680 年前的盘月柱可能整月错位。

## Workflow

### 1. 确定实体类型与锚点

先定 `entity_type`（human / game / product / company），再收集锚点时间（缺失先问，不猜）。
human 用真实性别与**出生地经度**；game/product 默认 male（阳年男顺排）。

### 2. 排盘

```bash
# 人盘：务必给经度，否则时柱可能整根错
python scripts/pai_pan.py "1990-01-01 10:00" --lon 116.4 --gender female --lucky 10 --years 12

# 游戏/产品：用公测或上线时刻
python scripts/pai_pan.py "2024-05-23 10:00" --name 鸣潮 --lon 113.3 --lucky 10 --years 12

# 换日流派存疑时两派都看
python scripts/pai_pan.py "2001-03-05 23:30" --lon 121.5 --day-boundary midnight
python scripts/pai_pan.py "2017-03-02 10:00" --lon 116.4 --json    # 喂后续模块
```

读输出时先看三处：`⚠ 警告`（未给经度／逢夏令时／距节气不足 1 小时）、
`day_pillar_alt`（另一换日流派的日柱）、`month_jie_time`（交节时刻）。
距节气 1 小时内务必与权威万年历核对。

### 3. 模块管线（先读 references/model-v6.md）

- **M0 锚点与历法纪律**：锚点时间必须可复核（分钟级、带时区、来源可查）；择吉神煞只作
  文化注记，不参与决策；可选输出胎元（300 日法）与命宫（三命通会法），低置信旁证。
- **M1 排盘与根气**：天覆地载、根重次序（长生禄刃 > 墓库余气 > 比肩）、得时不旺/失时不弱、
  阳干逢库即根（不求冲开）。
- **M2 格局引擎**：月令定格、顺逆、成败、带忌/救应、相神、纯杂高低、变化、杂气、
  墓库刑冲、外格用舍、病药并入格局判定。
- **M3 体用喜忌**：多级体用、用神/相神、病药八法（雕枯旺弱 × 损益生长）、强弱降权、
  四吉神破格/四凶神成格、盖头说（运干先论）。
- **M4 气象调候**：源流、通关、寒暖燥湿、众寡、顺逆从化、清浊、真神假神、隐显、
  形象方局、战局合局、八"过"检查表、四季五行分野。
- **M5 时序引擎**：大运成格变格、流年/月建干支并看、岁运四分类（战冲和好）、
  太岁纪律（岁运并临/伏吟返吟/征太岁/晦气）、盖头动静、透清、贞元代际、寿元三关。
- **M6 实证校准**：证据分级 A/B/C、基线对照、假设—反证归因、断语三级制
  （S 结构化规则 / C 文化注记 / X 不采用）、多书互证、概率化输出。

human 盘另读 [references/human.md](references/human.md)（六亲双轨、人生阶段、隐私纪律）。

### 4. 实体寿命缩放

| entity_type | 寿命基准 | 主程（前几步大运） | 大限窗口 |
|---|---|---|---|
| human | 70—90 年 | 前 6—7 步 | 第 8 步以后 |
| game | 5—15 年 | 前 2 步 | 第 10—13 年 |
| product | 5—20 年 | 前 2 步 | 第 10—15 年 |
| company | 20—100 年 | 前 4—6 步 | 第 6 步以后 |

寿元星三关：一创＝重伤可过；二创＝衰退；三创＝大限。库护寿元难杀。

### 5. 登记判据（v5 起为必做）

分析里的每条时间窗预测都要落进 `predictions/<entity>.json`，**并在窗口起点之前 commit**——
git 首次提交时间就是"事前"的证明，这是判据能否算 A 级的唯一依据。

每条必须写 `base_rate`（不用本模型、仅凭行业常识的发生概率）。若 `base_rate ≥ probability`，
标 `low_information: true`，该条不计入命中统计——因为它即使命中也不说明模型有效。

```bash
python scripts/verify.py            # 命中率 + Brier + 技巧分数
python scripts/verify.py --strict   # CI 用
```

判据写法与回填纪律见 [predictions/README.md](predictions/README.md)。

### 6. 输出格式

- 排盘与根气表（含警告、另一派日柱、胎元/命宫）；格局判定（含相神与带忌/救应）；
  体用喜忌（病药八法，含置信度与备选方案）；气象分析（源流/通关/调候/八过）；
  时序表（大运成格变格、流年干支并看、岁运战冲和好、寿元三关）。
- 判据清单：至少 3 条 A 级事前预测，每条含时间窗、判定标准、**基线概率**、数据源、所依赖假设。
- 六亲（human）：双轨并列（父印系 vs 父偏财系）＋宫位法。

## Resources

- [references/classics-v6.md](references/classics-v6.md) — 八部文献逐书解读、现代分层与不采用清单。
- [references/model-v6.md](references/model-v6.md) — v6 完整规范（M0—M6 增量、断语三级制）。
- [references/model-v5.md](references/model-v5.md) — v5 完整规范（六模块、六亲双轨、版本变更）。深度分析必读。
- [references/human.md](references/human.md) — 人盘专用（六亲、人生阶段、隐私）。
- [references/calibration.md](references/calibration.md) — 校准 schema、判据写法要求、鸣潮 worked example。
- [references/model-v3-deprecated.md](references/model-v3-deprecated.md) — v3 旧规范，仅供旧记录追溯。
- [scripts/pai_pan.py](scripts/pai_pan.py) — 排盘 CLI（真太阳时/夏令时/换日可切换/JSON）。
- [scripts/verify.py](scripts/verify.py) — 校准统计与事前性核验。
- [tests/](tests/) — 不变量测试；`python -m unittest discover -s tests`。

## Guardrails

- 文化娱乐性质：不宣称科学预测，不作为投资/医疗/婚恋决策依据。
- 断语三级制：S 级（结构化规则）可作结论骨架；C 级（神煞/纳音/歌诀/择吉）必须标注
  "文化注记"；X 级（历史性别观断语、医疗断语、生肖定生死）禁止出现在最终输出。
- 证据分级：校准只计 A 级（事前、可查证、非低信息量）；B/C 级只作参考。
- **命中率必须与基线并列报告**；技巧分数 ≤ 0 即视为模型未提供信息。
- 隐私：human 盘不落盘可识别信息；校准记录只存事件与干支，日期脱敏到"日"。
- 不虚构事实：事件、流水、销量引用公开可查来源并注明口径。
- 门派分歧（六亲、强弱、墓库、换日）并列输出，不作独断。
- 排盘精度有边界：黄经用低精度式，距节气 1 小时内的盘须外部核对；1986—1991 出生者
  须确认记录是否已扣夏令时。
