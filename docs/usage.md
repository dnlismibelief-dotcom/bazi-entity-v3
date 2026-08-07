# BFFT 使用文档

> 一套可复用的「四柱八字 × 万物」分析 skill，供任何 AI agent（Claude Code / Codex 等）调用。

## 1. 这是什么

`BFFT`（万物命理）用同一套推演分析四类实体：

| entity_type | 锚点时间 | 寿命基准 | 主要读什么 |
|---|---|---|---|
| human | 出生时刻（＋出生地经度） | 70—90 年 | 人生阶段、事业/财富/婚姻窗口、六亲 |
| game | 公测／上线时刻 | 5—15 年 | 热度、流水、争议、版本节奏、停运窗口 |
| product | 发布／上市时刻 | 5—20 年 | 市场表现、生命周期 |
| company | 成立／改名／上市时刻 | 20—100 年 | 经营、融资、危机、代际交接 |

模型来自《千里命稿》《子平真诠》《滴天髓》＋梁湘潤今註，规范见
[references/model-v5.md](../references/model-v5.md)。

## 2. 安装

零依赖，Python 3.10+ 即可。

```bash
git clone https://github.com/dnlismibelief-dotcom/bazi-entity-v3.git BFFT
```

不想 clone 也可以直接解压 `dist/BFFT.zip`（本文件即随包分发）。两种方式得到的
都是同一套 `SKILL.md` ＋ 脚本 ＋ 测试。

Claude Code / Codex 一类工具读取根目录的 `SKILL.md`。若 skill 目录与仓库位置不同，
用软链接（Windows 用目录联接 `mklink /J`）指向仓库即可，不必维护两份副本。

## 3. 调用

### 命令行直接排盘

```bash
# 人盘：务必给经度
python scripts/pai_pan.py "1995-06-15 08:30" --lon 121.5 --gender female --lucky 10 --years 12

# 游戏：用公测时刻
python scripts/pai_pan.py "2024-05-23 10:00" --name 鸣潮 --lon 113.3

# 输出 JSON 供后续模块消费
python scripts/pai_pan.py "2017-03-02 10:00" --lon 116.4 --json
```

| 参数 | 说明 |
|---|---|
| `--tz` | UTC 偏移小时，默认 8 |
| `--lon` | 出生地经度（东正西负）。**给了才做真太阳时修正**，人盘强烈建议提供 |
| `--gender` | 大运顺逆用；game/product 默认 male |
| `--day-boundary` | `zi`（23 时换日，默认）或 `midnight`（00 时换日） |
| `--dst` | `auto`（默认，自动识别 1986—1991 中国夏令时）／`on`／`off` |
| `--lucky` / `--years` | 大运步数 / 流年年数 |
| `--json` | 结构化输出 |

### 交给 AI 分析

- 人盘：> 用 BFFT 分析我的八字，出生 1995-06-15 08:30（UTC+8，女，上海），重点看事业和婚姻。
- 游戏：> 用 BFFT 分析《XXX》，公测 2024-09-26 10:00（UTC+8），输出热度、寿命关口和可验证判据。

给人盘时**报上出生城市**，否则无法做经度修正，时柱可能整根错位。

## 4. 读输出：先看三处

1. **`⚠` 警告行** — 未提供经度／命中夏令时／距节气不足 1 小时。第三种务必与权威万年历核对，
   因为太阳黄经用的是低精度式。
2. **`day_pillar_alt`** — 另一换日流派的日柱。落在子时的盘会两派并列，别只取一派。
3. **`month_jie_time`** — 交节时刻。它决定月柱，而月令定格是 M2 格局引擎的起点。

v6 起 JSON 额外输出：

- `taiyuan` — 胎元（《三命通会》300 日法：生日前 300 日为受胎之正，取其节令月柱）。
- `minggong` — 命宫（三命通会法：子位起正月逆行至生月，顺数逢卯安宫；配年干五虎遁）。

两者均为**低置信旁证**：可作"早年根基/受胎背景"类结论的参考，不参与格局成败。
命宫算法存在流派分歧（其他书有以"卯+月数+时数"或"寅宫顺数"起法），
本引擎固定采用三命通会法并在字段中标明。

## 5. 四步用法

1. 定 `entity_type` 与锚点时间（缺了先问，不猜）。
2. 排盘，读警告。
3. 走六模块管线（M1 根气 → M2 格局 → M3 体用 → M4 气象 → M5 时序 → M6 校准）。
   深度分析前先读 [model-v5.md](../references/model-v5.md)；人盘另读
   [human.md](../references/human.md)。
4. 把每条时间窗预测登记进 `predictions/`，并在窗口起点前提交。

## 6. 登记与校准（v5 硬要求）

细则见 [predictions/README.md](../predictions/README.md)。要点：

- 每条判据必须写 `base_rate`（不用本模型、仅凭常识的发生概率）与 `falsify`（什么算失败）。
- **git 首次提交时间即"事前"证明**；晚于窗口起点提交的不计 A 级。
- 衡量标准是技巧分数而非命中率——命中率高但技巧分数 ≤ 0，等于没有信息。

```bash
python scripts/verify.py            # 命中率 + Brier + 技巧分数 + 事前性
python scripts/verify.py --strict   # CI 用
```

## 7. 自检

```bash
python -m unittest discover -s tests -v
```

42 条不变量测试（节气回代黄经、月柱进位、日柱递增、大运连续性、真太阳时对称性等）。
想把绝对精度也钉死，往 `tests/fixtures.csv` 填带来源的权威万年历样本，该文件非空时
对照测试自动生效。

## 8. 已知边界与纪律

- 文化娱乐性质，不作投资／医疗／婚恋决策依据。
- 节气时刻精度约分钟级；1986—1991 出生者须确认记录是否已扣夏令时。
- 人盘不落盘可识别信息；校准记录只存事件与干支。
- 门派分歧（六亲、强弱、墓库、换日）并列输出，不作独断。
- 事件、流水、销量必须引用公开可查来源并注明口径，不虚构。

## 9. 版本

当前 v6（八书贯通），skill 正式命名为 `BFFT`。版本变更见
[CHANGELOG.md](../CHANGELOG.md)。
v3 旧规范保留在 [model-v3-deprecated.md](../references/model-v3-deprecated.md)，仅供旧校准记录追溯。
