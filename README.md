# BFFT · 万物命理（v6 · 八书贯通）

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
python scripts/pai_pan.py "2024-05-23 10:00" --name 鸣潮 --lon 113.3 --json

# 换日流派存疑时两派都看
python scripts/pai_pan.py "2001-03-05 23:30" --lon 121.5 --day-boundary midnight

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

## 目录

```
SKILL.md                          skill 定义（六模块管线、寿命缩放、guardrails）
CHANGELOG.md                      版本变更（含 v4 遗留 bug 清单）
scripts/pai_pan.py                排盘 CLI：真太阳时/夏令时/换日可切换/JSON
scripts/verify.py                 校准统计：命中率 + Brier + 技巧分数 + 事前性核验
references/model-v5.md            完整模型规范（六模块 M1—M6、六亲双轨）
references/human.md               人盘专用（六亲、人生阶段、隐私纪律）
references/calibration.md         校准档案 schema、判据写法要求、鸣潮 worked example
references/model-v3-deprecated.md v3 旧规范，仅供旧记录追溯
predictions/                      预测登记（git 时间戳作事前证明）
tests/                            42 条测试（含 13 条带来源的权威万年历 fixtures）
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

## License

未指定。
