# Competitive Landscape（内部参考，2026-09-16）

> 用途：评测应对、运营话术、差异化声明的事实底稿。**不进 SKILL.md 正文**（SH 概述会渲染正文）。

## 定位图（agent skills 生态，引用研究赛道）

| Skill | 定位 | 相对规模 | 与本 skill 关系 |
|---|---|---|---|
| deep-research-pro | 深度研究（多源检索+报告） | ~59k dl | 只研不验：引用自产自信。是「被替代对象」而非竞品——用户被假引用伤过就会找我们 |
| smartlib | 引用核验工具 | ~6.9k dl | 只验不研：没有研究流程。与我们是相邻功能，可共存 |
| **cite-holmes** | **研究 + 逐条自证引用（唯一组合）** | 8k+ dl（双平台，09-16） | 差异化 = 五态判定 + 官方数据库逐条核验 + CiteScore + 医学模式 + 审计导出 |

## 差异化声明（可对外说的）

1. 全场唯一「深度研究 + 机器自证引用」结合体：报告里每条引用带五态判定与人工复核区。
2. 核验走官方数据库（DOI.org / NCBI E-utilities / export.arxiv.org / archive.org），非启发式。
3. 可机检伪造类型已覆盖 9 类（假 DOI/错引/假 PMID/假 arXiv/拼接/期刊名/作者名/死链/重复），
   边界诚实：指向真实可信页面的精心伪造由语义层把关。
4. 纯标准库零依赖、跨平台、可离线结构检查；BibTeX/CSV/HTML 三种交付物。

## 跟随策略

- 评测失分点即下一版 backlog（TRACE 4.6→4.8 的路径已验证有效：按评测重排优先级）。
- 竞品发版脉冲是曝光窗口：对方发版当日我们在 SH 的搜索关联曝光会抬头（观察过两次）。
- 不做功能对标军备竞赛；守住「每条引用都核验 + 诚实边界」的核心心智。

## 关联

- 诊断真源：归墟 note_1789221108_9d4922（v1.1.1 停滞 29 天根因分析）
- 评测轨迹：v1.3 4.6 → v1.5 4.6（结构变化：T 滑坡暴露国内适配）→ v1.6 4.8（R 满分）

## 2026-09-19 增补（v1.9 自调研，引用经本体验证 CiteScore 55/C，8/8 可达）

### 学术界定调（背书素材）

- **Nature 2026-04**：数万篇 2025 年论文可能含 AI 生成的无效引用；**Nature 2026-05**：
  四个仓库 2025 年论文/预印本合计 **14 万+假引用**（社科预印本最高）。
- **arXiv 2026-06 政策**：论文若显示未检查的 AI 输出（含幻觉引用）→ 作者禁投一年。
  = 我们「投稿前结论」行（v1.9）的政策锚点；话术："arXiv 会因幻觉引用禁投作者——
  投稿前先跑一遍 cite-holmes"。
- **Badalova & Mayr, arXiv 2607.22693（2026-07）**：评测五家检测工具
  （CheckIfExist / HalluCiteChecker / Hallucinator / HalRef / RefChecker），
  结论=没有一家可无人监督运行；共性短板=引用提取错误、元数据不全、库覆盖有限、
  校验不一致；作者呼吁 **transparent multi-source detection systems**。
  → cite-holmes 已是七源（DOI.org/E-utilities/arXiv/archive.org/Crossref-RW/
  OpenAlex/S2）+ auditjson 透明工作底稿，方向被第三方背书。

### 竞品动作

- **Paperpile Citation Checker（2026-05-27 发布）**：免费 web 工具，粘贴 BibTeX
  逐条核查。入口=`.bib` 文件 → 我们 v1.9 已补齐 BibTeX 导入，且多了研究流程整合
  与审计台账。
- **GPTZero Hallucination Detector**：从检测写作 AI 痕迹扩展到幻觉引用检测
  （NeurIPS 2025 扫描出 100+ 假引用即其研究）。

### 基础设施变化（已落地应对）

- **OpenAlex 2026-02 起生产调用需 API key**（每日免费额度）→ v1.9 支持
  `--openalex-key`/`OPENALEX_API_KEY` + 403 可操作提示（09-19 实测免钥仍 200）。
- **Crossref 2026-07-21 限速分层**；2026-05 Labs API 撤稿注记停更（REST 是唯一
  前进路径，v1.8 路线正确）→ v1.9 `--mailto` polite pool + 429 Retry-After。
- **S2 免钥可用但记录质量参差**（实测 10.1002/art.42566 登记为期刊目录页）→
  v1.9 设计为「只确认不降级」的第二路确认源。

### 国内需求侧

- 科技部 2025-11 撤稿论文专项整治（抄袭/造假/买卖论文/虚构同行评审）；
  卫健委 2026-05「论文工厂」通报零容忍。= 中文市场对撤稿检测/引用验真的需求
  政策背书（SKILL_ZH 概述可呼应，不直接引用政策文号做营销）。

### 分发（发布后任务，非 v1.9 范围）

- agent skills 生态目录：skills.sh / SkillsMP / AgenticSkills / Skills Directory /
  Awesome Skills（2026-09 已有对比测评）。ClawHub+SH 之外逐个铺。

## 2026-09-20 增补（v1.10 自调研,11 检索;评测 v1.9.0 综合 4.8,T4.5 唯一失分）

### 评测驱动

- v1.9.0 评测（09-20 自拉）：综合 **4.8** 回升（T4.5↓/R4.8/A4.8↑/C**5.0 满分**/E4.8↑）。
  C 维瘦身修复二次确认见效（4.6→4.7→5.0）；T 维「跨国数据库慢/国内不稳/存档受限」
  成为唯一明显失分 → v1.10 全部火力对准速度与降级体验（并行/降级模式/缓存）。
- SH 数据（09-20）：下载 259、收藏 2、双实验室安全报告无风险。

### 新事实

- **OpenAlex mailto polite pool 已随 key 制退役**（2026-02）；无 key=100 credits/天。
  Crossref 的 mailto polite pool 不受影响（两回事，别混淆）。→ v1.10 补 429/403
  话术（100 credits 数字入文案）。
- **Crossref 2026-07-21 起 REST 限速按请求类型分层**（polite pool 仍经 mailto）；
  Retraction Watch→Crossref REST 集成稳定（2025-01 起定期更新）。
- **S2 `/paper/search` title 端点**：单篇最近匹配；官方文档确认**连字符词查询无
  结果**（需空格化）→ v1.10 title-search 确认源已按此实现。
- **GPTZero（2026-01）**：ICLR 2026 在审论文抓 50 条、NeurIPS 2025 抓 100 条幻觉
  引用——「引用检查进评审流程」成新场景，对我们有利（验证需求侧扩大）。
- **Paperpile（2026-05）**：arXiv 新投稿约 **0.4% 引用为幻觉**且在增长。
- **Phantom References（arXiv 2607.22693）**：~1/20 的 NeurIPS/USENIX Security
  2025 论文含 ≥2 条疑似幻觉引用（已入引用台账并经本体验证 verified）。
- **CASRAI（2026-08）**：五工具皆不可无人监督（与 2607.22693 同调）——透明多源
  +人工复核定位继续有效。
- **cite/name 不匹配骗过检查器**（haqq.ai 法律 AI 案例）：全行业盲点，本工具
  v1.4 起的标题比对（真 DOI 假论文→invalid）正是对症能力，差异化声明保留。
- **skills 生态**：三大目录合计 49 万+技能（2026-03）；多目录分发成常态。
- **NCBI 无 2026 变化**（免钥 3 req/s；key 10 req/s）——不需要接 NCBI key。


## 学界评估坐标（2026-09-21 增补）

GESIS 立场论文 arXiv:2607.22693《Detecting Hallucinated and Suspicious
Citations》（2026-07）实测五款检测工具：RefChecker / CheckIfExist 高假阳性
（错杀真引用）、HalluCiteChecker 高假阴性（放过真编造）、Hallucinator 精确率/
召回率平庸、HalRef 在元数据不全时大量误报。四大通病：引用抽取错误、元数据不全、
数据库覆盖不足、**同一引用跨工具甚至同工具重跑打分不一致**。作者呼吁
「transparent, multi-source detection systems——combining several verification
signals and disclosing their own uncertainty」，实践定位是「早期预警分诊层」而非
自动 pass/fail 闸门。

**对我方的意义**：cite-holmes 的五态判定 + CiteScore + auditjson 工作底稿 +
「未验证引用只进人工复核区」与该呼吁逐条对应，可直接作为差异化话术（SKILL.md
Honest limits 已引用）。v1.11 的 arXiv fallback 链直接回应「重跑不一致」通病；
semantic_audit 把「disclosing uncertainty」落成机器可读。竞品坐标补充：学界
工具（RefChecker=Amazon Science 开源管线、HalRef、Hallucinator）面向批量论文
流水线；本 skill 面向 agent 研究流程，逐条实时核验，赛道不同、话术错位竞争。
