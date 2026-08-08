# Table generation 数据集与评估策略调研

> 调研日期：2026-08-08。本文把“table generation”限定为生成可编辑、可验证的表格产物，并特别关心 `raw experimental data -> publication table`。它不等同于通用表格识别、table-to-text 或统计图生成。

## 执行摘要

目前没有一个成熟的公开数据集，能完整覆盖“多轮实验数据 + 论文上下文 + 作者意图 -> 可编辑的出版级表格”。现有资源分别覆盖了图像到结构、文本到事实表、表格到创意可视化、图到代码、以及主观设计偏好，但都只是目标的一个切面。

因此，PaperTable 不应复制某个现有 leaderboard，而应构建分层 benchmark：

1. **科学正确性硬门槛**：数值、单位、不确定性、比较组和统计语义任一关键项错误，整个样例失败。
2. **结构与可执行性**：代码可运行，生成的逻辑网格、表头层级、标注和强调范围正确。
3. **视觉与传播效果**：不仅问“是否像原表”，还要问“是否让读者更快、更准地看到作者要表达的 claim”。
4. **交互行为**：单独测试 SKILL 能否识别关键缺失信息、提出高信息价值问题，并在信息足够时停止追问。

最重要的评估原则是：**参考表 `y` 是一个有价值的作者选择，但不是唯一正解。** 精确拷贝 `y` 会压制合理创新；只看“美观”又可能奖励数值错误的产物。

## 1. 任务边界：同名领域实际上有六种问题

| 任务 | 典型映射 | 主要目标 | 与 PaperTable 的关系 |
|---|---|---|---|
| Table detection / structure recognition | 页面或表格图像 -> cell grid / HTML | 恢复位置、行列、跨行跨列和文本 | 可用于构建真实论文表的 `y`，不能评价从实验数据到设计的能力 |
| Image-to-code / table-to-LaTeX | 表格图像 -> LaTeX | 生成可编辑、可重渲染的代码 | 可训练排版能力，但输入图像已泄漏了完整设计 |
| Text/evidence-to-table | 文本、问题或检索证据 -> 事实表 | 抽取、整合并生成事实单元格 | 可借用 cell provenance 和内容 F1，但并不涉及论文结果表的视觉设计 |
| Interactive table editing | 现有表 + 多轮指令 -> 修改后表 | 理解增、删、改、重组操作 | 与作者对话有关，但通常没有“主动询问”的标注 |
| Table-to-visualization / chart generation | 表格 + 简述 -> 图或信息图 | 数据到视觉编码的忠实性和美观度 | 适合表格图形化的分支，但不能取代精确查值的传统表格 |
| Experimental-data-to-publication-table | 原始 runs + 语义 + claim -> 可编辑论文表 | 科学正确性、内容选择、结构、强调和设计 | **PaperTable 的核心任务，仍缺少公认 benchmark** |

这个分类决定了数据能否直接用于评测。例如，一个 image-to-LaTeX 模型能完美复刻边框和字体，也不说明它知道不同随机种子应该汇总为 SD 还是 SE，或者知道哪些方法构成有效比较组。

## 2. 数据集 landscape

### 2.1 图像、结构与代码恢复

| 数据集 | 规模与监督信号 | 常用评估 | 能借用什么 | 核心局限 |
|---|---|---|---|---|
| [TableBank](https://github.com/doc-analysis/TableBank) | 417K 张来自 Word/LaTeX 的弱监督表格图像 | detection AP；序列识别指标 | 大规模科学排版外观、明确 split | 主要是检测/识别，无原始实验和作者 claim |
| [PubTabNet](https://github.com/ibm-aur-nlp/PubTabNet) | 568K+ 生物医学表格图像 + HTML | TEDS / TEDS-Struct | HTML tree、内容和跨单元格对齐 | 领域和样式偏置；HTML 已给定结构真值 |
| [PubTables-1M](https://github.com/microsoft/table-transformer) | 575,305 个检测页；947,642 个全标注表，含 cell/header 角色与坐标 | AP/AR；GriTS-Top/Con/Loc | 标准化逻辑网格、表头角色和完整几何 | 生物医学 PDF 为主；仍是恢复任务 |
| [SciTSR](https://arxiv.org/abs/1908.04729) | 15,000 个科学表，含 cell 间水平/垂直关系；12K train / 3K test | relation precision/recall/F1 | 复杂跨行跨列和 adjacency 表示 | 数据老且较小；原始 arXiv 来源需做 item-level 许可审核 |
| [TABLE2LATEX-450K](https://yuntiandeng.com/papers/Deng2019ICDAR.pdf) | 465,957 个渲染表图像 + LaTeX | exact match / edit / render similarity | 表格代码生成和大规模预训练 | 数字渲染、字体和基线变化有限；目标样式完全泄漏 |
| [TabLeX](https://arxiv.org/abs/2105.06400) | 超过 3M 个 structure 样例、超过 1M 个 content 样例，图像 + LaTeX | BLEU / edit / exact类指标 | 科学表的字体、宽高比与 LaTeX 语法 | 主要评估信息抽取，不评估设计决策 |
| [Tab2LaTeX / LATTE](https://huggingface.co/datasets/lt-asset/tab2latex) | 97,513 个 2018-2023 arXiv 表图像 + LaTeX | pixel exact match、CW-SSIM、BLEU-4、column-wise edit | 用重渲染 delta 做迭代修复 | 仍然是 image-to-code，不能测试科学选择和视觉策略 |

这一类数据适合预训练 parser、学习 LaTeX 排版模式、或将论文 PDF 中的表构建为可比较的逻辑网格。它们不应直接成为 PaperTable 的主测试集，因为输入图像已经包含了所有视觉决策。

### 2.2 内容生成、事实忠实性与交互

| 数据集/工作 | 输入 -> 输出 | 评估信号 | 对 PaperTable 的价值 | 不足 |
|---|---|---|---|---|
| [Text-to-Table](https://aclanthology.org/2022.acl-long.180/) | 长文本 -> 未预先定义 schema 的表 | exact match、BLEU/BERTScore 等 | 内容抽取、表头生成、长表错误传播 | 使用 E2E、WikiBio、WikiTableText、RotoWire 等反向构造任务，不是实验结果设计 |
| [WikiTIG](https://aclanthology.org/2023.acl-short.162/) | 标题（可加图像）-> Wikipedia 实体表 | Table-F1、Corpus-F1、ROUGE | 204,460 个 table-generation 样例，可测表头-值关联 | 主要测试模型的参数化事实知识 |
| [WikiTabGen](https://aclanthology.org/2025.knowledgenlp-1.4/) | 表描述 -> 完整 Wikipedia 表 | cell/table accuracy | 119 个人工筛选表，暴露了行级生成和数值内容的困难 | 数量小，不涉及排版或论文 claim |
| [TANQ](https://aclanthology.org/2025.tacl-1.23/) | 开放域问题 + 多源检索 -> 答案表 | 表级/cell F1，每个 cell 附源引用 | **cell provenance** 是 PaperTable 可直接借用的强设计 | 数据来自外部事实检索，不是一次实验的 raw runs |
| [iTBLS](https://aclanthology.org/2025.trl-1.6/) | 学术表 + 3-turn 对话 -> 解释/修改/生成 | exact match、BERTScore 等 | 接近多轮表格协作，可用于修改操作测试 | 对话由任务指令驱动，没有主动询问的 gold policy |
| [SciGen](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/149e9677a5989fd342ae44213df68868-Abstract-round2.html) | 科学表 -> 需要算术推理的描述 | 自动 NLG 指标 + 人类正确性评估 | 可反向帮助评估表是否支持 claim | 输出是文本，不是表格设计 |
| [TabXBench / TabXEval](https://aclanthology.org/2025.findings-acl.1176/) | 参考表 + 预测表 -> 对齐后差异评分 | 50 个 clean 表，每表 5 个扰动，16 种错误；表/行/列/cell 分层 rubric | 非常适合借用“先对齐、再分解错误”的思路 | 规模小；评分依赖 LLM 语义对齐；不包含视觉设计 |

这一类最有价值的遗产是：把数据正确性分解为 schema、row/column、cell、unit 和 provenance，而不是对串行化表格只算一个 BLEU。

### 2.3 可视化、代码生成与学术设计

| 数据集/工作 | 规模与任务 | 评估策略 | 能借用什么 | 不足 |
|---|---|---|---|---|
| [ChartMimic](https://chartmimic.github.io/) | 4,800 个人工编写的 figure/instruction/Python triplet；22 类图 | 代码执行；code tracer 抽取 text/layout/type/color F1；GPT-4o 高层相似度 | **代码执行追踪 + 多粒度评估** | 是 chart-to-code 复刻；高层分仍依赖单一 VLM judge |
| [PaperBananaBench](https://arxiv.org/abs/2601.23265) | 292 个 NeurIPS 2025 method diagram 测试样例；另构造 240 个 plot 测试 | VLM 比较 faithfulness/conciseness/readability/aesthetics；50 样例做人类校准和 blind A/B | 学术上下文、参考驱动策划、分轴人评 | 主 benchmark 是 diagram；plot 输入从参考代码反解数据；不是作者 raw runs |
| [TableVisBench / ShowTable](https://openaccess.thecvf.com/content/CVPR2026/papers/Liu_ShowTable_Unlocking_Creative_Table_Visualization_with_Collaborative_Reflection_and_Refinement_CVPR_2026_paper.pdf) | 800 个人工核验的 table-to-infographic 测试样例；[dataset](https://huggingface.co/datasets/lntzm/TableVisBench) 为 CC BY-NC 4.0 | DA 数据准确性、TR 文本渲染、RR 相对比例、AA 附加信息、AQ 美学 | 把事实错误拆成可定位的子项，并与美学分开 | 产物是信息图；四个事实维度由 MLLM QA analyst 判定，AQ 由美学模型判定 |
| [TASTE](https://arxiv.org/abs/2605.20731) | 10 名专业设计师、4 个生成系统、9 个设计维度；每维 1,600 次排序 | Kendall's tau、多数派概率、Condorcet cycle、position bias、与专家多数派一致率 | 专家偏好标注和位置偏差控制的模板 | 是通用 graphic design，不是学术表；现成 VLM judge 对专家多数派的 macro agreement 未超过 0.55 |
| [AesEval-Bench](https://arxiv.org/abs/2603.01083) | graphic design 的 4 个维度、12 个指标、3 种任务 | 美学判断 accuracy、错误区域选择 accuracy、bbox IoU | “不仅评好坏，还要指出错在哪里”的 critic 设计 | 平面设计扰动不等于论文表格的可读性和科学有效性 |

PaperBanana 对我们有两个特别重要的经验。第一，统计产物需要数值精度，所以它明确选择可执行代码而不是纯图像生成。第二，它的人类校准只在 50 个样例上进行，VLM-人的 Kendall's tau 约为 0.41-0.57，说明 VLM 适合扩大日常评测，但不应被当成美学真值。

## 3. 现有评估指标的适用范围

### 3.1 可以直接复用或改造的部分

#### 执行与产物健康度

- 渲染代码是否无人工修改地执行成功。
- LaTeX 是否编译，是否存在 overfull box、缺失字体、裁切、重叠或不合规的宏包。
- 输出是否保留可编辑性，是否能在固定随机种子和环境下重现。

这应该是 pass/fail gate，而不是被平均到视觉总分中。

#### 内容和结构对齐

- **Cell provenance**：每个输出 cell 连接到原始 run IDs、聚合函数或输入 cell。
- **Typed token matching**：区分数值、单位、范围、正负号、百分比、科学计数法、p-value 和缺失值，而不是只抽取数字字符串。
- **Logical-grid alignment**：将生成代码解析为规范 cell grid，再评估 row/column/header/span/note；可借用 GriTS 的 topology/content 分解和 TabXEval 的先对齐后比较。
- **Order-invariant matching**：如果行顺序不影响语义，允许用 bipartite matching 对齐；对有排名意义的表才保留顺序惩罚。

#### 统计与科学语义

这是现有通用表格 benchmark 最缺失的层。建议作为独立硬门槛：

- 汇总函数、`n`、样本 SD/SE/CI 和分母是否正确。
- 是否伪造了未观测的 runs，或把模拟值当成实验值。
- metric direction、单位换算、absolute/relative delta 和精度是否一致。
- best/second-best、显著性、超越 baseline 的强调是否只在合法 comparison group 内进行。
- oracle/upper bound、不同 backbone、不同 data regime 是否被错误混合排名。

### 3.2 只能作为弱代理的指标

| 指标 | 为什么不能单独使用 |
|---|---|
| LaTeX/code exact match | 同一张表可以用完全不同的宏、环境和代码顺序实现；代码不同不等于产物错 |
| BLEU/ROUGE/edit distance | 惩罚等价语法，且对一个关键负号或单位错误不足够敏感 |
| Pixel exact match / SSIM / CW-SSIM | 字体 anti-aliasing、DPI 和轻微间距即可显著改变分数；高相似也可以包含错数字 |
| CLIP/LPIPS/普通美学分 | 更擅长自然图像语义，对小字、符号和逻辑层级不可靠 |
| OCR token recall | 无法保证 token 出现在正确 cell，也可能忽略重复、上下标和负号 |
| 单一 VLM-as-a-judge 总分 | 可能有位置、长度、自身模型和语言风格偏差；且 TASTE 表明现成系统对设计师多数派的一致率仍很低 |
| 对参考图的视觉相似度 | 会把作者当时的偶然样式当成唯一答案，不鼓励更清晰的合理方案 |

### 3.3 视觉质量应如何评估

建议将“美观”拆成可解释维度，并用成对比较而非绝对打分：

1. **Typography**：目标版宽下的最小字号、字重层级、小数点对齐、行高和标注密度。
2. **Hierarchy**：读者能否区分 dataset / setting / method / metric / note，是否出现错误的视觉分组。
3. **Readability at target width**：在真实单栏或双栏宽度渲染，不应用任意放大的 crop 评分。
4. **Claim salience**：强调是否帮助读者首先看到预先声明的 claim，而不是单纯“显眼”。
5. **Visual restraint**：颜色、粗体、下划线、底色和边框是否过载，灰度打印是否仍可区分。
6. **Overall preference**：作为总体选择，但不取代前五个可解释子项。

人评应左右位置随机化、隐藏系统名称，每对至少 3 人，其中有一部分是真正撰写过 ML 论文的作者。报告 majority preference、Bradley-Terry/Thurstone 偏好分、bootstrap CI、Krippendorff's alpha 或 Kendall's W，并显式报告 position-bias rate 和争议样例。

比“美观”更接近真实目标的是一个小型用户研究：给读者定时问题，例如“哪个方法在合法比较组内最好？”、“提升是否超出误差？”，测量答案正确率、用时和信心。这可以区分“视觉华丽”和“真正帮助科学阅读”。

## 4. 主动询问是一个独立任务，不应只写在 prompt 里

现有 table benchmark 几乎不测试主动询问。iTBLS 提供了多轮表格操作，但是用户已经给出指令；它不测试系统能否发现“没有随机种子，因此不能声称误差”。

建议为 InquiryBench 构建可控场景：从一个完整 case 出发，人为隐藏一到三个信息，并标注它们是 `blocking`、`valuable_nonblocking` 还是 `cosmetic`。

### 建议的缺失场景

- 只给 mean，不给每个 seed 或不给误差类型。
- 给了 `±`，但不说是 SD、SE 还是 CI，也不给 `n`。
- 不给 metric direction、单位或 absolute/relative delta 定义。
- baseline 身份、配对/非配对设计、评测集大小缺失。
- 表中有不同 backbone、dataset 或 oracle，但没有说明哪些可比。
- 数据完整，但没有 claim；这是高价值问题，通常不必阻止生成保守默认版。
- 只缺颜色喜好或个人字体；这是低价值问题，不应阻止工作流。

### 交互评估指标

| 指标 | 定义 |
|---|---|
| Critical-question recall | 所有 blocking 缺失中，被询问并正确理解的比例 |
| Question precision | 所有询问中，确实与科学解释或设计选择有关的比例 |
| Information-gain weighted recall | 按缺失信息会改变统计结论、结构还是只改变样式赋权 |
| Unsupported-inference count | 不询问而擅自假设 `n`、误差类型、可比组或显著性的次数 |
| Over-questioning cost | 获得足够信息所需的额外轮数和低价值问题数 |
| Stop correctness | 当信息足够时是否停止，当 blocking 信息仍缺失时是否拒绝过度声称 |
| Answer utilization | 作者回答后，最终 spec 和表是否真正使用这些信息 |

这些指标应从对话 trace 评分，而不是从最终图片反推。

## 5. PaperTable 建议的 benchmark 结构

### 5.1 三层数据，不混成一个排行榜

在三个评估层之外，PaperTable-Discovery 只负责真实论文表的候选发现和结构压力测试。2024 NeurIPS diversity-capped 索引含 200 条、30 篇论文，单篇最多 8 条；其中 121 条来自 17 篇旧索引未出现的论文。用途、形式和质量标志都是可重建的规则弱标注，必须保留 `gold: false`；没有结构化 `x` 的 crop 不能用于数值重建评分或生成 leaderboard。

#### A. `PaperTable-Real`：真实 `(x, y)` 作者对

- 优先纳入有作者释放 raw runs、处理脚本和发表 PDF 的 NeurIPS/ICLR/ICML 表。
- 将输入明确分为 `raw_runs`、`canonical_table`、`recovered_table`，三者只在同层内比较。
- `y` 同时保存论文 crop、可获得时的 LaTeX 源码、规范 cell grid、标题/注释、页码、表号、paper/repository commit 和 hash。
- 拆分单位至少为 paper，更保守的方案是同一作者团队或同一代码模板不跨 train/test。

这一层是外部有效性最强、但成本最高的核心测试集。早期目标应是高质量和来源可审计，而不是先追求数十万个弱配对。

#### B. `PaperTable-Controlled`：程序化扰动和能力单元测试

从规范 spec 生成可严格判分的任务，例如：

- 交换可交换行，验证系统不被输入顺序控制。
- 注入一个负号、单位、精度、重复 seed、错误 CI 或无效 comparison group。
- 增加无关列、缺失值、超长 method name、双层表头、不同 metric direction 或超宽表。
- 隐藏一个关键元数据，形成 InquiryBench 场景。

这一层适合 CI 和回归测试，可以扩展到数千例；但它不能证明设计在真实论文中受欢迎。

#### C. `PaperTable-Preference`：多解的视觉与传播偏好

- 对同一个 `x` 生成 2-4 个都通过科学硬门槛的不同设计。
- 让作者/论文读者按 typography、hierarchy、readability、claim salience 和 overall 分别排序。
- 保存理由和区域标注，不只保存一个 1-5 分。
- 预留重复样例以评估同一评者稳定性，交换左右以评估 position bias。

### 5.2 每个 case 应包含的真值

```text
provenance
  paper / venue / year / page / table / source URL / license / hashes
input
  raw records or canonical cells / run IDs / units / metric direction
  comparison groups / aggregation and uncertainty semantics / claim
interaction
  deliberately hidden fields / gold need-to-ask class / acceptable defaults
reference
  published image / normalized logical grid / optional source code
constraints
  venue width / grayscale / required notes / forbidden comparisons
evaluation
  cell lineage / aggregation audit / allowed row permutations
  human preference records / rater metadata / randomization seed
```

关键改动是不再只存 `x.json + y.png`，而是存储**可判分的语义合同**。对于视觉上存在多个正解的部分，保存 constraints 和 preference；对于数值和统计语义，保存唯一可验证 lineage。

### 5.3 推荐的报告形式

不建议一开始发布一个“PaperTable Score”。每个系统应报告一张 scorecard：

| 轨道 | 核心指标 | 是否硬门槛 |
|---|---|---|
| Execution | render/compile success, deterministic reproduction | 是 |
| Fidelity | typed-cell precision/recall, provenance coverage, hallucination count | 是 |
| Statistics | aggregation, uncertainty, valid comparison and emphasis correctness | 是 |
| Structure | header/span/group/note F1 or GriTS-like scores | 否，但必须分项报告 |
| Layout | fit rate, overlap/crop, min font size, grayscale distinguishability | 基本缺陷是硬门槛 |
| Communication | claim-answer accuracy/time/confidence, human pairwise preference | 否 |
| Inquiry | critical recall, precision, unsupported inference, turns, stop correctness | 关键科学缺失为硬门槛 |
| Cost | latency, model calls, tokens, retry/render iterations | 否 |

只对通过前三个科学门槛的样例计算人类视觉偏好，以防止一张数字错误但非常漂亮的表获得高排名。

## 6. 对 SKILL 设计的直接启示

这里只给出调研导出的策略，不在本阶段把它固化为最终实现。

1. **不用一个大 prompt 同时做统计、设计和渲染。** 应把 pipeline 分为 provenance/ingest、inquiry gate、statistical compiler、design planner、deterministic renderer 和 verifier。
2. **主动询问是状态机。** 每个缺失字段有 blocking/value/cosmetic 类别，必须能记录已回答内容、更新 spec，并在足够时停止。
3. **先生成 canonical semantic spec，再生成 LaTeX/HTML/table-chart。** 评估和多后端渲染都应围绕这个 spec，而不是从最终图片猜回数据。
4. **视觉 planner 应允许多解。** 对复杂 case 先提供两个通过硬门槛的策略，说明它们分别服务“精确查值”还是“突出趋势/claim”。
5. **所有数字都需要 lineage。** 观测值、聚合值、派生 delta、显著性和模拟值必须有不同类型；模拟值不能进入实验证据表。
6. **critic 必须输出可定位修改，而不是一个美学分。** 例如“表头第 2 组与第 3 组间层级不足”、“双栏宽度下字号低于阈值”、“粗体跨越了无效 comparison group”。
7. **参考检索只学设计模式，不能泄漏目标论文。** 检索集和测试集至少 paper-level 隔离，目标 `y` 必须在 `y'` 冻结后才能进入 evaluator。

从 skill-creator 的角度，这意味着 `SKILL.md` 只保留程序步骤和决策门；统计语义、设计规则和 benchmark 协议应进入按需读取的 `references/`；聚合、渲染和验证这些脆弱步骤应使用确定性 scripts。

## 7. 建议的下一阶段

1. 先把现有 PaperBench schema 从“图像对”升级为“语义合同”，增加 lineage、allowed transformations、claim、hidden inquiry fields 和 venue rendering constraints。
2. 用现有 4 个 case 构建第一批 controlled perturbations，先验证评估器能不能稳定抓住负号、单位、误差、比较组和错误粗体。
3. 手工编写 20-30 个 InquiryBench 场景，测试当前 SKILL 是否真正会问、是否问对、以及是否会停。
4. 继续从作者仓库寻找 `raw_runs`，但将高成本真实对放在 held-out test，不用它们调 prompt。
5. 等科学硬门槛稳定后，再进行第一轮小规模、随机化、多评者的视觉偏好实验。

这个顺序可以避免我们过早优化一个不稳定的 VLM 美学分，同时快速建立可以在 CI 里稳定回归的科学正确性基线。
