# PaperTable — Main Experiment Table Skill

[![Tests](https://github.com/goya4140/PaperTable/actions/workflows/tests.yml/badge.svg)](https://github.com/goya4140/PaperTable/actions/workflows/tests.yml)

把 CSV / TSV / JSON / JSONL 实验数据生成可投稿的 **主实验表 + caption**。这个仓库现在首先是一个 Codex Skill，其次才是 CLI：Agent 负责理解科学比较关系，确定表格布局；确定性流水线负责聚合、排名、渲染和校验，不改写实验数字。

## 真实生成效果

下列图片由仓库内的 gallery 数据通过完整流水线生成，再从 `preview.pdf` 渲染得到，不是手工画表。

### 模型 / 方法 / 可训练参数分层

![Hierarchical method and budget table](docs/assets/gallery/hierarchical-method-budget.png)

### 数据集作为行，系统作为列

![Transposed benchmark table](docs/assets/gallery/transposed-benchmark.png)

### 质量与训练成本并列表达

![Quality and efficiency table](docs/assets/gallery/quality-efficiency.png)

## 为什么不只有一个“万能表”

我们检查了 [BERT](https://aclanthology.org/N19-1423/)、[LoRA](https://openreview.net/forum?id=nZeVKeeFYf9)、[Vision Transformer](https://openreview.net/forum?id=YicbFdNTTy)、[Transformer](https://papers.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html)、[FlashAttention](https://papers.neurips.cc/paper_files/paper/2022/hash/67d57c32e20fd0a7a302cb81d36e40d5-Abstract-Conference.html)、[ResNet](https://openaccess.thecvf.com/content_cvpr_2016/html/He_Deep_Residual_Learning_CVPR_2016_paper.html)、[MAE](https://openaccess.thecvf.com/content/CVPR2022/html/He_Masked_Autoencoders_Are_Scalable_Vision_Learners_CVPR_2022_paper.html) 和 [ReAct](https://openreview.net/forum?id=WE_vluYUL-X) 的主表。跨论文稳定出现的不是一套装饰风格，而是一个语义骨架：

```text
[system identity / protocol / budget] | [measured evidence] | [optional cost or aggregate]
```

因此 PaperTable 将 `Model`、`Method`、`Pre-train Data`、`Budget`、`Protocol` 等身份字段与指标彻底分开，并根据证据结构选择方法作为行或数据集作为行。完整观察和设计映射见 [pattern catalog](references/pattern-catalog.md)。

## 六类可复用主表

| Template | 适用的科学比较 | 关键表达 |
|---|---|---|
| `benchmark-wide` | 多任务、多指标 | 方法为行，dataset × metric 多级表头 |
| `hierarchical-method-budget` | PEFT / 微调方法 | model、method、trainable params 分列 |
| `transposed-benchmark` | 数据集多、焦点系统少 | dataset 为行，system 为列，可按预训练数据分组 |
| `quality-efficiency` | 质量—成本权衡 | quality、time/FLOPs、speedup 独立呈现 |
| `scaled-variants` | 模型规模 / 深度消融 | family、variant、depth、params 分列 |
| `compact-regime-comparison` | 少量任务与多种方法机制 | prompting / acting / combined / oracle 分块 |

选择规则见 [template selection](references/template-selection.md)，每个模板都是可覆盖的 JSON config，没有隐藏的渲染分支。

## 作为 Skill 使用

把仓库放入 Codex skills 目录：

```bash
git clone https://github.com/goya4140/PaperTable.git \
  ~/.codex/skills/main-experiment-table
```

然后在 Codex 中直接说：

```text
$main-experiment-table 读取 results.csv，以参数效率为核心设计主实验表，并生成 LaTeX 和 caption。
```

Skill 会先识别比较维度和科学口径，再选择模板。具体行为和不可越过的数据约束定义在 [SKILL.md](SKILL.md)。

## CLI 快速开始

Python 3.10+，运行时无第三方 Python 依赖。

```bash
python scripts/generate_main_table.py list-templates

python scripts/generate_main_table.py generate \
  examples/gallery/hierarchical.csv \
  --template hierarchical-method-budget \
  --config examples/gallery/hierarchical.json \
  --out output/main-table
```

也可以安装 CLI：

```bash
python -m pip install -e .
papertable generate results.csv --template benchmark-wide --config table.json --out output/main-table
```

`--template` 可以是内置 template ID，也可以是自定义 JSON 路径。配置会深度覆盖模板；输入契约见 [input contract](references/input-contract.md)，布局字段见 [template schema](references/template-schema.md)。

## 产物与保证

```text
experiment files → observations → aggregates → semantic table spec
                                              ├─ table.tex
                                              ├─ table.html
                                              ├─ caption.txt
                                              └─ manifest.json
```

- `observations.json` 保留标准化后的每个观测和来源。
- `aggregates.json` 保留 mean、sample SD、`n`、run IDs 和身份维度。
- `table-spec.json` 是与 LaTeX / HTML 解耦的语义中间层。
- `manifest.json` 列出警告、被省略列和校验结果；只有 `verification.valid = true` 才是有效生成。
- 缺失值始终渲染为 `--` 并排除在排名之外；系统不会伪造误差、显著性或未报告实验。

本地有 TeX 时，可编译 `preview.tex`：

```bash
cd output/main-table
latexmk -xelatex preview.tex
```

## 测试

```bash
python -m pip install -e '.[dev]'
pytest
```
