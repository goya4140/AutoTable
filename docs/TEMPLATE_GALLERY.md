# 主实验表格模板库

模板的本质是“选择与排序配置”，不是五套互不兼容的渲染代码。以下 config 均可直接复制修改。

## 1. 多数据集 × 多指标（默认主表）

适合 SOTA comparison。行是 method，列是 dataset × metric；每个数据集下重复相同的主指标。

```json
{
  "title": "Main benchmark results",
  "metrics": {
    "accuracy": {"label": "Acc.", "direction": "max", "precision": 1, "priority": 1},
    "f1": {"label": "F1", "direction": "max", "precision": 1, "priority": 2}
  },
  "selection": {"metrics": ["accuracy", "f1"]}
}
```

## 2. 质量—效率联合主表

适合核心 claim 同时涉及效果和成本的论文。不要跨列综合排名；每列按自己的方向强调。

```json
{
  "title": "Quality and efficiency comparison",
  "metrics": {
    "accuracy": {"label": "Acc.", "direction": "max", "unit": "%", "precision": 1, "priority": 1},
    "latency_ms": {"label": "Latency", "direction": "min", "unit": "ms", "precision": 1, "priority": 2},
    "memory_gb": {"label": "Memory", "direction": "min", "unit": "GB", "precision": 1, "priority": 3}
  },
  "selection": {"metrics": ["accuracy", "latency_ms", "memory_gb"]}
}
```

## 3. 模型规模 / 数据规模 / 推理设置

输入增加 `setting` 列，例如 `Small / Base / Large` 或 `1-shot / 5-shot`。渲染器自动生成 `dataset / setting` 分组表头。

```json
{
  "title": "Scaling comparison",
  "metrics": {"accuracy": {"label": "Acc.", "direction": "max", "precision": 1}},
  "selection": {"settings": ["Small", "Base", "Large"], "metrics": ["accuracy"]}
}
```

## 4. 鲁棒性主表

把不同 corruption/domain 当作 dataset，按 clean → hard 的阅读顺序排列；最后可以加入平均指标作为独立 dataset=`Average`。

```json
{
  "title": "Robustness under distribution shifts",
  "metrics": {"accuracy": {"label": "Acc.", "direction": "max", "precision": 1}},
  "selection": {
    "datasets": ["Clean", "Noise", "Blur", "Weather", "Average"],
    "metrics": ["accuracy"]
  }
}
```

## 5. 单数据集紧凑主表

当 dataset 只有一个时，外层表头会自动折叠，只保留 metrics。

```json
{
  "title": "Main results on ImageNet",
  "metrics": {
    "top1": {"label": "Top-1", "direction": "max", "unit": "%", "precision": 1},
    "top5": {"label": "Top-5", "direction": "max", "unit": "%", "precision": 1}
  },
  "selection": {"datasets": ["ImageNet"], "metrics": ["top1", "top5"]}
}
```

## 主表压缩规则

主表的优先级通常应是：核心 claim 指标 → 标准主指标 → 效率约束 → 次要诊断指标。把 `priority: 1,2,3...` 写入 metrics，并显式设置 `selection.max_columns`。被裁掉的列会出现在 `manifest.json.omitted_columns`，可直接用于生成 appendix 表，而不会在主表流水线里消失。

