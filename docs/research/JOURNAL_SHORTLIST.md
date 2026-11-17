# 期刊 shortlist 与投稿建议

日期：2026-11-17  
对象：`SHORT_PAPER_DRAFT.md` 的 benchmark / negative-result 方向  
说明：期刊 scope、page limit、APC、deadline 会变化，投稿前必须以官网为准。

---

## 1. 先说结论

如果目标是**期刊**，当前最合适的不是顶会/顶刊，而是：

> **ACM Digital Threats: Research and Practice (DTRAP)**  
> 但需要把当前 4–6 页短稿扩展为 10–15 页左右的研究论文。

如果坚持**短论文/4–6 页**：

> 优先投 workshop / conference short paper，而不是硬投期刊。

如果只想快速拿到 SCIE 收录：

> **IEEE Access** 是更现实的选择，但 scope 泛、APC 高、主题匹配度不如 DTRAP。

---

## 2. 候选比较

| 期刊 | 主题匹配 | 文章类型/长度 | 收录/开放 | 风险 | 推荐度 |
|---|---|---|---|---|---|
| **ACM DTRAP** | 高：数字威胁、可复现结果 | Research paper 通常 10–25 页；Field Notes 1000–1500 词 | Open Access；官网写明 Scopus 收录 | 强调 real-world threats，本文是 proxy/lab pilot | ★★★★★（扩展后） |
| **Entertainment Computing** | 中高：游戏、玩家行为、AI | 期刊 full paper | Elsevier；需查最新索引/APC | 更偏娱乐计算/玩家体验，负结果可能被认为贡献不足 | ★★★★ |
| **IEEE Access** | 中：应用型跨学科 | 常规 research paper，篇幅较灵活 | SCIE；APC | scope 泛，审稿可能质疑小样本/负结果 | ★★★ |
| **IEEE Transactions on Games** | 高：游戏 AI/分析 | 常规 full paper | IEEE；游戏领域认可度高 | 数据量/贡献强度不足，风险高 | ★★（stretch） |
| **Computers & Security** | 高：安全 | 常规 full paper | Elsevier；安全领域认可度高 | 需要更强安全贡献和更大数据 | ★★（stretch） |
| **Journal of Cybersecurity** | 中高：跨学科安全 | 常规 research paper | Oxford；开放获取 | 对实证/理论强度要求高 | ★★（stretch） |

> 表中“主题匹配”是基于期刊公开 scope 的判断；具体 indexing/APC/审稿周期
> 需在投稿前重新核验。

---

## 3. 为什么把 DTRAP 放第一

DTRAP 官方页面强调：

- 面向 digital threats 的预防、识别、缓解和消除；
- 连接学术与产业实践；
- 欢迎针对**现实威胁**、可复现的结果；
- 现已 indexed in Scopus；
-  Research paper 通常 10–25 页，30 页为 soft upper limit；
- 有 Field Notes（1000–1500 词）短案例类型；
- 鼓励提交 software/data artifacts。

来源：

- [DTRAP journal home](https://dl.acm.org/journal/dtrap)
- [DTRAP author guidelines](https://dl.acm.org/journal/dtrap/author-guidelines)

匹配点：

- game bot 是现实数字威胁；
- 我们有可复现协议、会话校验、特征和负结果；
- 负结果对“小样本 H/B 行为分析”的测量有效性有价值；
- artifact/reproducibility 与 DTRAP 的取向一致。

风险：

- 官方 scope 强调 **real-world threats**，而本文 H/B 是 proxy label，不是真实外挂；
- 需要把“game bot threat”讲清楚，并明确不声称检测真实 cheat；
- 10–25 页要求意味着当前短稿必须扩展，不能直接投。

---

## 4. 为什么 Entertainment Computing 第二

适合点：

- 游戏、玩家行为、游戏 AI/analytics 的 scope 更接近；
- 对 H/B 行为分析、瞄准行为、玩家建模有天然兴趣；
- 比安全期刊更接受“行为测量/benchmark”叙事。

风险：

- 更偏娱乐计算/玩家体验，负结果和“反作弊”可能不是核心兴趣；
- 需要更强的游戏行为洞察，而不只是 confound 负结果；
- 可能需要补充正面分析或应用价值。

---

## 5. 为什么 IEEE Access 是现实备选

适合点：

- 跨学科、应用型；
- 篇幅和主题相对灵活；
- 对“benchmark + negative result + reproducible protocol”可能比顶刊更宽容；
- 适合需要 SCIE 产出的场景。

风险：

- scope 泛，审稿人可能不熟悉 game security；
- APC 较高；
- 学术声望低于 DTRAP/ToG/C&S；
- 负结果仍可能被要求补更多数据。

---

## 6. 不推荐现在投的

### IEEE Transactions on Games

游戏领域认可度高，但当前：

```text
10H/10B
单游戏
proxy labels
负结果
```

对 full paper 来说贡献强度不足。适合作为扩展后的目标，不是首投。

### Computers & Security

安全领域强刊，但需要：

- 更大的数据；
- 更强的安全威胁建模；
- 真实/更接近真实的 cheat 数据；
- 更完整的检测或防御贡献。

当前不适合。

### Journal of Cybersecurity

跨学科、开放获取，但对实证强度/理论贡献要求高；当前 pilot 风险大。

---

## 7. 推荐投稿路径

### 方案 A：先短论文，后期刊

```text
1. 当前 4–6 页短稿 -> workshop / conference short paper
2. 根据反馈扩展 -> DTRAP research paper（10–15 页）
```

适合：

- 需要先有产出；
- 想用 short paper 锁定优先权/反馈；
- 不急于一次性投期刊。

### 方案 B：直接扩展投 DTRAP

```text
当前草稿
  + related work（15–25 篇）
  + 更完整的协议/伦理/artifact
  + 更完整的 confound 分析
  + 讨论/局限性
  -> 10–15 页 DTRAP research paper
```

适合：

- 愿意再投入 1–2 周写作；
- 希望期刊产出；
- 能接受 DTRAP 的 real-world threat 框架。

### 方案 C：快速 SCIE

```text
IEEE Access
```

适合：

- 时间优先；
- 需要 SCIE；
- 能接受 APC 和较低主题匹配。

---

## 8. 我的建议

**首选：DTRAP（扩展后）。**  
**次选：Entertainment Computing。**  
**现实备选：IEEE Access。**  
**暂不投：IEEE ToG / Computers & Security / Journal of Cybersecurity。**

如果当前只准备 4–6 页，不要直接投 DTRAP；先投 workshop/short paper，或把 DTRAP 作为扩展目标。

---

## 9. 投稿前必须核验

- [ ] 最新 aims & scope；
- [ ] 是否接受 negative/benchmark 研究；
- [ ] 页数/模板；
- [ ] APC/开放获取费用；
- [ ] 索引状态；
- [ ] 审稿周期；
- [ ] 是否要求 artifact/数据可用性；
- [ ] 伦理/人类参与者政策；
- [ ] 是否允许已发布 short paper 的扩展版本。

---

## 10. 官方链接

- [ACM DTRAP](https://dl.acm.org/journal/dtrap)
- [ACM DTRAP author guidelines](https://dl.acm.org/journal/dtrap/author-guidelines)
- [IEEE Transactions on Games](https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=7782673)
- [Entertainment Computing](https://www.sciencedirect.com/journal/entertainment-computing)
- [IEEE Access](https://ieeeaccess.ieee.org/)

> 注：在线搜索 API 当前不可用；以上以官方期刊页/作者指南和我对 scope 的
> 既有了解为基础。投稿前请再次打开官网核对最新要求。