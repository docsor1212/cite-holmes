# 报告模板与引用 schema（SYNTHESIZE 阶段照此输出）

## research_refs.json schema（VERIFY 阶段的输入）

研究过程中实时登记引用，每条：

```json
[
  {
    "id": 1,
    "title": "页面/文档标题",
    "url": "https://…",
    "source": "来源站点或机构（如 Anthropic / Nature / Reuters）",
    "year": 2026,
    "claim": "本报告用这条引用支撑的那句话",
    "semantic": "supports",           // supports | partial_support | not_in_source
    "found_via": "search#3",          // 哪轮搜索发现的，便于回溯
    "tier": "official"                // official | journal | preprint | media | community | blog | social
  }
]
```

`semantic` 字段由模型在语义验证时填写；机械验证由 `scripts/verify_refs.py` 完成，两层的
结果都要体现在最终引用表里。

## 置信度标记规范

| 标记 | 含义 | 判定标准 |
|---|---|---|
| 🟢 | 高置信 | ≥2 个独立来源一致，且至少一个是一手/权威源 |
| 🟡 | 中置信 | 单一权威源，或双源但均为二手 |
| 🔴 | 存疑 | 来源冲突、仅社区层证据、或数据过旧 |

标记挂在结论句末尾 + 引用编号，如：`缓存命中率提升约 40% 🟢[1][3]`。

## 报告骨架

```markdown
# {研究问题}

> 研究模式：FULL/QUICK · 检索 N 轮 · 引用 M 条（verified X / partial Y / …）
> 完成日期：YYYY-MM-DD · 覆盖时间窗：…

## 执行摘要（≤200 字，先给答案）
{直接回答研究问题的主要发现，2–4 条，每条带置信度标记}

## 主要发现
### 子问题 ①：{…}
{结论句 🟢[引用号]。证据展开：数字/事实 + 出处定位。}
{与结论相悖的证据如有，必须写。}

### 子问题 ②：{…}
…

## 分歧与存疑
{来源打架的地方：各自说法 + 各自来源 + 可能的成因（数据新旧/口径不同/立场差异）}

## 研究缺口
{预算内没能回答的问题、抓取失败的来源、需要付费/权限才能核实的数据}

## 后续值得追问
{2–3 个基于本次发现自然延伸的问题}

## 引用清单
| # | 标题 | 来源 | 年份 | 语义 | 机械验证 | 支撑论断 |
|---|---|---|---|---|---|---|
| 1 | … | … | … | supports | verified | … |

### 待人工复核（unverified / unreachable）
| # | 标题 | URL | 状态 | 原因 |
```

## 输出要求

- 正文结论**只能**引用 `semantic=supports` 且机械验证非 `invalid` 的条目。
- `partial_support` 只能支撑结论中它确实支持的那半句，并在句中注明。
- `unverified/unreachable` 一律只出现在"待人工复核"分区。
- QUICK 模式可省略"子问题"分节，直接：执行摘要 → 核查结论（含反证）→ 引用清单。
- 报告语言跟随用户提问语言；术语首次出现给中英对照。
