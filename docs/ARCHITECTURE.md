# 生产逻辑

## 为什么这样拆

调研中真正有用的共识是把 `schema generation` 与 `value generation/rendering` 分开。这个仓库将它落实为四个纯粹阶段：

1. `ingest`：只负责异构文件到统一 observation；
2. `aggregate`：只负责同一 method/dataset/setting/metric 的重复实验聚合；
3. `planner`：选择行列、生成层级、确定 metric 方向和强调规则；
4. `render`：从 table spec 确定性生成 LaTeX/HTML/caption。

`pipeline.generate()` 只是串联这些步骤并保存中间产物。这样未来接入 LLM、检索器或 claim-aware planner 时，只需替换第三步，数值聚合和渲染无需交给模型。

## 唯一内部事实表

每条 observation 至少有：

```text
(method, dataset, metric, value)
```

可选字段为：

```text
(run, setting, group, source, dimensions)
```

聚合 key 为：

```text
(method, dataset, setting, metric, group)
```

每个 aggregate 保留原始 values、run IDs 与 source files。当前不把 sample 当 seed，也不推断实验独立性；输入给出的重复记录仅按 sample SD 汇总。

## Planner 的边界

当前 planner 是确定性 baseline：

- 行为 methods；
- 列为 dataset/setting × metric；
- 常量层级自动折叠；
- selection 控制 method/dataset/metric 的选择和顺序；
- metric priority 在显式给出 `max_columns` 时负责压缩；
- best/second 在每一个合法展示列内独立计算。

Claim 被保存在 spec 中，但不会被假装“理解”。一个后续的 claim-aware planner 可以读取 observations、claim 和版面预算，输出同一 `paper-table-spec-v1`，继续复用 render 与审计链。

## 科学边界

- 不从单次结果伪造误差；
- 不从 metric 名称生成显著性；
- 不把缺失 cell 填成 0；
- 不静默删除超过版面预算的列；
- 不用一个不可审计的总分决定表格质量；
- caption 与表格共享 spec，不单独手写第二份事实。

## 最小扩展点

若未来需要更多能力，优先保持接口不变：

- 新输入源：增加 adapter，仍输出 `Observation`；
- median/CI：增加 aggregation policy，仍输出带 lineage 的 aggregate；
- LLM schema：增加 planner，仍输出 `paper-table-spec-v1`；
- Markdown/Typst：增加 renderer，只读 spec；
- 编译与宽度检查：消费 `table.tex`，把报告写回 manifest。

