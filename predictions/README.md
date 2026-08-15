# 预测登记（Predictions Registry）

## 为什么要有这个目录

校准纪律要求"只统计 A 级（事前、可查证）判据"，但 A 级的真正瓶颈不是方法，是**举证**——
怎么证明一条预测是事前写的，而不是事后补的？

答案是版本库本身。每条预测作为独立 commit 落在这里，**git 的首次提交时间戳就是不可篡改的时间锚**。
`scripts/verify.py` 会自动比对"文件首次提交时间"与"预测窗口起点"，早于窗口起点的才计 A 级。
这一步几乎零成本，却让整个项目从自说自话变成可审计。

## 文件格式

用 JSON 而不是 YAML——本项目坚持纯标准库、零第三方依赖，而 `yaml` 需要装 pyyaml。

```
predictions/<entity>.json
```

每条 prediction 的必填字段（缺任何一项 `verify.py --strict` 会失败）：

| 字段 | 含义 |
|---|---|
| `id` | 判据编号，如 J-03 |
| `window` | `["起始日", "截止日"]`，预测事件应发生的区间 |
| `claim` | 判据内容，必须具体到可核对 |
| `probability` | 模型给出的发生概率 0..1 |
| `base_rate` | **不用本模型、仅凭行业常识的发生概率** |
| `base_rate_source` | 基线的出处或估计依据 |
| `falsify` | 什么情况明确算失败（含过期未发生即 miss） |
| `deadline` | 回填截止日 |
| `evidence_grade` | A / B / C |
| `verdict` | `pending` / `hit` / `miss` / `void` |

可选：`low_information`（当 `base_rate` ≥ `probability` 时应置 true，该条不计入命中统计）、
`assumptions`、`revised_from`。

## 为什么 base_rate 是最要紧的一栏

"运营中的手游年内会有一次重磅企划官宣"——这条命中率接近 100%，但它不含任何信息，
因为不用八字也能这么说。只有当**模型概率显著偏离基线**、并且结果站在模型这边时，
才能说模型提供了信息。

`verify.py` 因此不只报命中率，还报 Brier 分数与**技巧分数**：

```
技巧分数 = 1 - BS_模型 / BS_基线
  > 0   优于照基线报数
  = 0   没有提供信息
  < 0   比基线更差
```

命中率高但技巧分数 ≤ 0，等于没有价值。这是本项目衡量自己的唯一硬标准。

## 工作流

1. **登记**：新建或追加 `predictions/<entity>.json`，`verdict` 一律先写 `pending`。
   注意：事前性锚点是**文件首次提交时间**——给已有文件追加新判据会继承旧文件
   的首提时间，窗口起点早于本次追加时间的判据会被错误认证为"事前"。因此
   追加判据请新建 `predictions/<entity>-<yyyymm>.json`，保证每批判据的锚点正确。
2. **提交**：单独 commit，信息写清 `predict(<entity>): J-0x ...`。**必须在窗口起点之前提交。**
3. **等待**：不要在窗口内改写 claim、probability、falsify。要修正只能新增一条并在
   旧条目上标 `revised_from`，保留原记录。
4. **回填**：到 `deadline` 后把 `verdict` 改成 `hit`/`miss`，附 `source`（公开可查链接或口径）。
   同一事件只记一次，不做事后改写。
5. **统计**：`python scripts/verify.py`，季度跑一次；技巧分数连续为负则按
   `references/model-v5.md` 的 M2/M3/M4 归因，先改假设再动权重。

## 检查

```bash
python scripts/verify.py            # 报告
python scripts/verify.py --strict   # schema/事前性不过则退出码 1（CI 用）
python scripts/verify.py --json     # 机器可读
```
