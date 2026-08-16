# BFFT · 万物命理（v7.5 · 八书贯通 ＋ 引擎历法修正 ＋ 20 名人独立比对）

把四柱八字做成一套**可证伪**的分析框架，对象不限于人——`human` / `game` / `product` / `company`
四类实体共用同一套推演，按各自的寿命尺度缩放读取。游戏用公测时刻当"生辰"，
读人气、流水、争议与停运窗口。

模型来自八部文献：v4 三书（《千里命稿》《子平真诠》《滴天髓》＋梁湘潤今註）
＋ v6 新增五书（《三命通会》《渊海子平》《神峰通考》《协纪辨方书》《果老星宗》），
层次原则是 **强弱 < 格局 < 气象 < 调候**。逐书解读与"哪些不采用"见
`references/classics-v6.md`。

> 文化娱乐性质。不宣称科学预测，不作为投资、医疗、婚恋决策依据。

## 这个项目和别的命理内容有什么不同

它给自己定了能被判死的规矩：

1. **预测必须事前登记。** 每条判据写进 `predictions/*.json` 并单独提交，
   **git 的首次提交时间戳就是"事前"的证明**。晚于预测窗口起点提交的，一律不计 A 级。
2. **必须写基线概率。** "运营中的手游年内会有重磅联动"这种命中率接近 100% 的判据不算本事；
   只有当模型概率显著偏离基线、且结果站在模型这边，才算提供了信息。
3. **用技巧分数衡量自己。** `scripts/verify.py` 报命中率、Brier 分数和
   技巧分数 `1 - BS_模型/BS_基线`。**技巧分数 ≤ 0 即视为模型没有价值**，命中率再高也一样。

当前有 6 条待验证判据，最早一条 2027-01 到期。

## 快速开始

零依赖，纯 Python 3 标准库。

**安装**：clone 本仓库，或直接解压 `dist/BFFT.zip`（内含使用文档 `docs/usage.md`）。

```bash
# 人盘（务必给出生地经度，否则时柱可能整根错）
python scripts/pai_pan.py "1990-01-01 10:00" --lon 116.4 --gender female

# 游戏/产品，用公测时刻
python scripts/pai_pan.py "2024-05-23 10:00" --name 游戏甲(示例) --lon 113.3 --json

# 换日流派存疑时两派都看
python scripts/pai_pan.py "2001-03-05 23:30" --lon 121.5 --day-boundary midnight

# 20 位明确出生时刻（A/AA 级）名人批量排盘 + 独立参照逐柱比对
python scripts/famous20.py            # 排盘表
python scripts/famous20.py --check    # 与 lunar-javascript 参照比对（20/20 通过）

# 逐年伪事前回测/事前登记（示例：回测样本，事业结果口径 rulebook v1）
python scripts/yearly_bazi.py "1989-12-13 08:36" --name "回测样本" \
    --tz -5 --lon -75.93 --gender female --from 1989 --to 2031 \
    --future-from 2026 --birth-year 1989 --career \
    --write predictions/backtest-v2.json

# 自检
python -m unittest discover -s tests
python scripts/verify.py
```

### 为什么一定要给 `--lon`

同一时区内经度不同，真太阳时相差很大。同一钟表时刻 07:30：

| 地点 | 经度 | 真太阳时 | 时柱 |
|---|---|---|---|
| 乌鲁木齐 | 87.6°E | 04:20 | 庚寅 |
| 上海 | 121.5°E | 06:35 | 辛卯 |

不做经度修正的排盘会对这两地给出同一个时柱，其中必然有一个是错的。v5 之前的版本就是这样。

v7 修了另一类更隐蔽的错：ΔT 公式只覆盖 1900 年以后，往前外推会发散（1500 年算出 −63 天），
连带使 1680 年前的节气求根不收敛却静默返回初值。明清及更早的盘月柱会整月错位。
详见 [CHANGELOG.md](CHANGELOG.md)。

## 目录

```
SKILL.md                          skill 定义（六模块管线、寿命缩放、guardrails）
CHANGELOG.md                      版本变更（含 v4 遗留 bug 清单）
scripts/pai_pan.py                排盘 CLI：真太阳时/夏令时/换日可切换/JSON
scripts/famous20.py               20 位 A/AA 级名人批量排盘 + 独立参照比对
scripts/famous20_reference.mjs    独立参照生成器（lunar-javascript，可选）
scripts/yearly_bazi.py            逐年岁运判据生成/回填打分（album/tour v0 + 事业指数 v1）
scripts/verify.py                 校准统计：命中率 + Brier + 技巧分数 + 事前性核验
data/famous20_times.json          20 人出生时刻/时区/来源/评级/参照四柱
data/backtest_facts.json            回测样本 逐年事实表（album/tour 回测）
data/backtest_facts_v2.json         回测样本 1989—2024 逐年事业事实分（rubric 固定）
references/model-v5.md            完整模型规范（六模块 M1—M6、六亲双轨）
references/famous20-validation.md 20 人检验报告：20/20 比对 + 真太阳时口径差异
references/backtest-yearly.md       回测样本 album/tour 回测：−0.104 / +0.047（技巧分数）
references/backtest-yearly-v2.md    回测样本 事业指数回测：+0.224（技巧分数），1989—2024
references/human.md               人盘专用（六亲、人生阶段、隐私纪律）
references/calibration.md         校准档案 schema、判据写法要求、游戏甲(示例) worked example
references/model-v3-deprecated.md v3 旧规范，仅供旧记录追溯
predictions/                      预测登记（git 时间戳作事前证明）
tests/                            80 条测试（含 13 条带来源的权威万年历 fixtures）
docs/usage.md                     安装与调用说明
dist/                             打包产物（BFFT.zip，含使用文档）
```

## 已知边界

- 太阳黄经用 Meeus 低精度式，节气时刻精度约分钟级。**距节气 1 小时内的盘请与权威万年历核对**
  （脚本会告警）。
- `tests/fixtures.csv` 已内置首批 13 条带来源的权威万年历样本（节气交界、夏令时、
  23–01 点换日两派、极端经度、闰年），测试全绿；继续追加样本时请按模板写明 `source`。
- 夏令时日期表（1986—1991）依据公开资料，可能与出生地档案有差异，可用 `--dst off` 覆盖。
- 门派分歧（六亲、强弱、墓库、换日）一律并列输出，不作独断。
- `data/famous20_times.json` 只用于排盘正确性检验；名人回测不能证明命理有效，
  时柱另有"真太阳时 vs 钟表时刻"口径差异（见 `references/famous20-validation.md` §4）。

## License

未指定。
