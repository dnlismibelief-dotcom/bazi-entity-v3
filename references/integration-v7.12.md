# v7.12 外部 Skill 整合报告（小红书三篇笔记追踪）

> 日期：2026-08 ｜ 触发：用户提供三篇小红书笔记（公认 skill 清单 / 赛博算卦提示词 /
> Bazi-Analysis Skill 上线），要求拉取对应 git 项目、整合可用代码、多轮极端测试并 push。

## 0. 小红书笔记追踪结果

| 笔记 | 解析结果 |
|---|---|
| 1「十几个公认好用的Skill包含蒸馏自己」（香蕉岛AI） | 笔记正文为图片清单，未登录抓不到图；从 GitHub 生态还原了公认清单（见 §1），其中命理相关的全部拉取审查 |
| 2「Ai 算卦提示词 赛博算卦」（Alex Space） | 纯提示词笔记，无独立 git 项目；无代码可整合 |
| 3「Bazi-Analysis Skill 已上线」（AI小旅） | 对应仓库 **maochengsun16-code/bazi-analysis-skill**（★89），已拉取并审查 |

## 1. 拉取并审查的仓库

| 仓库 | ★ | 形态 | 审查结论 |
|---|---|---|---|
| maochengsun16-code/bazi-analysis-skill | 89 | 纯文档 skill | 框架文档优质（决策树/冲突消解/置信度/校验清单），无代码；文档精华吸收见 §3 |
| jinchenma94/bazi-skill | 2546 | 纯文档 skill | 小规模口诀型（大运规则/时辰表/五行表），与 BFFT 排盘口径一致，无增量 |
| qianye-wuyu/yueyuan-bazi（跃渊） | 104 | 文档 skill + 100 案例 | 理念与 BFFT 同源（预注册预测=事前登记、反证、规则分层）；**人元司令分野表**为 BFFT 缺失功能（已代码化）；变格四态状态机精华吸收见 §3 |
| dzcmemory-web/bazi-ziwei-skill | 812 | TypeScript 计算器 | 排盘走第三方库（lunar-*），**不算法自主**，与 BFFT 零依赖路线不同；HTML 海报为产品层功能，暂不吸收 |
| china-testing/bazi | 1466 | Python 单体 | 冲刑合会评判规则齐全（天干冲/三刑/自刑/六害/半合），**天干冲与完整刑表为 BFFT 缺失**（已吸收）；代码为 120KB 单体无测试，仅抽规则表 |
| reed1898/bazi-tool | 3 | Python 模块化 | relationships.py 结构清晰，作为关系表对照源（吸收项一致） |
| openfate-ai/bazi-engine | 7 | TypeScript | 依赖 lunar-javascript；interactions 关系规则作对照（吸收项一致） |
| shizhilya/yuan | 179 | Python 引擎 | 依赖 pyswisseph（瑞士星历）；口径为"真太阳时不修正"，与 BFFT 相反；**仅作口径差异记录，不吸收** |
| Ficere/tianji | 25 | Python skill | weight-tables.md 引入固定数值权重——与 BFFT"禁止伪量化权重"（calibration.md）纪律冲突，**明确拒绝** |
| FANzR-arch/Numerologist_skills | 938 | — | clone 失败（仓库名/URL 变更），列入后续待查 |

## 2. 代码级吸收（本轮实现）

### 2.1 完整干支关系表（`scripts/pai_pan.py` 新增）

对照四家（china-testing/bazi、reed1898/bazi-tool、openfate-ai/bazi-engine、
yueyuan-bazi）与《三命通会》卷二，补齐 BFFT 缺失：

- **天干冲**：甲庚/乙辛/丙壬/丁癸（此前只有五合）
- **完整三刑**：寅巳/巳申/寅申/子卯（此前只有丑戌/戌未）
- **完整半合 12 对**：四局各三对（生旺半合＋拱）
- **自刑**：辰/午/酉/亥（与伏吟区分）
- **破**：子酉/午卯/辰丑/戌未 + 巳申、寅亥合中带破双标签
- `calc()` 新增输出 `relations`（六对天干对、六对地支对、三合局检测）

纪律：独立于 `yearly_bazi.py` 的 v0 rulebook（后者已冻结，回测样本回测
技巧分数 +0.224 依赖其固定权重）——新表只做关系输出，不改回测。

### 2.2 人元司令分野（`calc()` 新增 `ren_yuan` 字段）

《渊海子平》流派表（寅戊7丙7甲16 … 十二支合计 30 天），按出生日
距当月节令天数定"用事之神"。标注 `[SCHOOL]` 各版本天数有出入，
仅作当月用事之神定性参考，不进入格局成败判定。

## 3. 文档层吸收（合并进 references/classics-v6.md 精神，详见下文清单）

- **跃渊变格四态状态机**（biange.md）：专旺/从格/化气判定按
  "成立条件＋破坏条件＋双轨并列"组织，并入 M4 外格判定的表达纪律：
  从格嫌疑须"身弱 vs 从格"双轨并列，不强行二选一。
- **bazi-analysis 置信度指南**：结论分级与 BFFT 断语三级制（S/C/X）对照，
  采纳其"有分歧必须并列"的表述纪律。
- **bazi-analysis 校验清单**：与 BFFT M6 多书互证合并——关键格局/岁运
  结论至少两书一致，冲突并列注明出处。
- **明确拒绝**：tianji 固定数值权重表（违反伪量化禁令）；yuan 的
  真太阳时不修正口径；各家的第三方排盘库依赖（BFFT 零依赖不破）。

## 4. 测试与稳定性

- 新增 `tests/test_relations.py` 19 条：66 地支对穷举、10 干对穷举、
  合冲刑害破半合自刑逐表校验、双向对称、三合检测、人元 12 支合计 30 天、
  游戏甲(示例)巳月丙火用事案例。
- 多轮极端测试（本次执行）：全套 unittest ×3（119 条全绿）＋
  stress_test ×3（2000 盘 fuzz/轮，全部通过，约 1100 盘/s）。
- 未发现新 bug；引擎性能无退化（0.3ms 级/盘）。

## 5. 待办（记录备查）

- FANzR-arch/Numerologist_skills（反幻觉工程框架，★938）clone 失败，
  下次重试并审查其防幻觉机制是否可并入 M6。
- bazi-ziwei-skill 的 HTML 水墨海报（产品层）如需可另立项，不动核心引擎。
