# 短论文推进清单

日期：2026-11-17  
依据：`SHORT_PAPER_DRAFT.md`、`PAPER_DIRECTION.md`

---

## 1. 当前冻结资产

```text
数据：
  dust2 5H / 5B
  nuke  5H / 5B
  aim_botz 6H cross-map

模型：
  old = deployment default
  new = experimental only

分析：
  F2 baseline / confounder / invariant / matching
  old/new detector audit
```

当前不需要新采集数据，也不需要训练分类器。

---

## 2. 我可以直接推进的工作

### A. 数字与表格冻结

- [ ] 核对论文中所有数字与 CSV/JSON 一致：
  - F2 balanced 10H/10B；
  - nuke/dust2 per-map；
  - confounder residualization；
  - invariant features；
  - matching；
  - old/new detector audit。
- [ ] 生成 `paper_tables.md` 或 CSV 导出，标注每个数字的来源文件。
- [ ] 统一 accuracy / balanced accuracy / AUC 的口径和模型名。

### B. 图表

- [ ] 图 1：P0-B → tiled detection → P0-C → QC/analysis 流程图。
- [ ] 图 2：old vs new 模型在 POV 上的 head 检测对比。
- [ ] 图 3：F2 在 dust2/nuke/平衡集上的 AUC 对比。
- [ ] 图 4：F2-only / confounders-only / residualized 的 AUC 对比。
- [ ] 可选：dataset composition 地图/类别堆叠图。

### C. 论文结构压缩

- [ ] 将当前草稿压到 4–6 页（workshop/short paper）。
- [ ] 把细节移到 appendix 或 artifact README。
- [ ] 明确 contributions 和 negative-result framing。
- [ ] 写 claim-evidence 对照表，防止过度声称。

### D. Reproducibility / artifact

- [ ] 整理可公开的脚本、session ID、map 标签、feature 定义。
- [ ] 写 artifact README / reproduction commands。
- [ ] 标明 weights/raw video 的可发布边界。
- [ ] 准备 artifact appendix（不含受限原始视频）。

### E. Related work 候选

- [ ] 检索 game bot detection、aim behavior、screen-only capture、
      measurement validity、dataset confound 相关工作。
- [ ] 先做候选引用表，不直接写死引用。
- [ ] 写 related-work 段落草稿。

### F. 投稿准备

- [ ] 选 2–3 个 venue 候选，列 page limit、deadline、indexing。
- [ ] 生成 LaTeX/Word 模板骨架。
- [ ] 做投稿前 checklist。

---

## 3. 需要你主动提供的内容

这些会阻塞最终定稿，但不阻塞我继续做图表/压缩/artifact。

### 必填

- [ ] 作者姓名、顺序、单位、通讯作者。
- [ ] 目标语言：英文 workshop / 中文期刊 / 两者。
- [ ] 目标 venue 类型：
  - workshop；
  - conference short paper；
  - 中文核心/学报；
  - 英文应用期刊。
- [ ] 是否用于毕业/评奖/申博，以及单位对 short paper/workshop 的认定。
- [ ] 是否有基金、项目号、致谢。
- [ ] 利益冲突声明。
- [ ] 伦理/知情同意信息：
  - 人类参与者是否知情；
  - 是否允许使用匿名 session 数据；
  - 是否需要 IRB/伦理审批编号。

### 发布边界

- [ ] 是否公开：
  - 协议与脚本；
  - 特征 CSV；
  - session 元数据；
  - 原始视频；
  - old/new 模型权重。
- [ ] 若不能公开原始视频/权重，论文中如何写 data availability。

### 选题/定位

- [ ] 是否同意“negative/benchmark paper”是主定位。
- [ ] 是否保留 aim_botz 6H 作为 cross-map 数据，还是完全不写入论文。
- [ ] 是否接受“不能声称检测真实外挂”的表述。

---

## 4. 需要你审核的内容

### 科学内容

- [ ] 论文是否准确描述：
  - 无真实外挂；
  - H/B 是 proxy labels；
  - 数据量小；
  - 结果不支持泛化。
- [ ] 是否同意把 F2 residualized 作为核心负结果。
- [ ] 是否同意 body 漏检作为 accepted limitation 写入。
- [ ] 是否同意不报告“最高 accuracy”作为主结论。

### 数字和图表

- [ ] 核对论文表格与最终 CSV。
- [ ] 审核 3–4 张主图是否清楚、没有误导。
- [ ] 审核 title/abstract 的措辞。

### 作者与合规

- [ ] 作者顺序/单位/通讯作者。
- [ ] 伦理、数据、模型许可表述。
- [ ] 是否需要在 GitHub 公开 artifact。

### 投稿

- [ ] 最终 venue 和模板。
- [ ] 投稿账号/系统由谁操作。
- [ ] 提交前是否允许我生成最终 PDF 草稿。

---

## 5. 建议顺序

```text
1. 我先做：数字冻结 + 图表 + artifact + 压缩草稿
2. 你提供：作者/venue/语言/伦理/发布边界
3. 我补：related work 候选 + 模板
4. 你审核：claim-evidence 表 + 主图 + 最终 PDF
5. 投稿
```

## 6. 当前不需要

```text
不采新数据
不训练分类器
不改 old/new 默认
不发布权重
```

---

## 7. 最小可投稿包

```text
4–6 页短论文
3–4 张主图
1 个数据集/协议表
1 个负结果表
related work 8–15 篇
artifact README
ethics/data availability 声明
```