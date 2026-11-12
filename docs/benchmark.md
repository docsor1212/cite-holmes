# 留出集评测口径（公开基准方法论）

> **30 秒导航**：本页是 cite-holmes 的自评基准——任何人可用一条命令复现；
> 先看指标定义，再看最新数字与历史表；诚实边界在末尾（离线/在线两档口径）。

## 为什么有这页

AI 研究工具的引用质量是行业性短板（学术媒体与图书馆界 2025-2026 年已有
多份错引率实测报道）。本工具的立身之本是判定可信，因此把自评口径公开：
数据是什么、指标怎么算、数字怎么复现，全部摊开——**不接受无口径的数字**。

## 数据

- **内置金标集**：`examples/demo_refs.json`——8 条引用，其中 3 处预埋伪造
  （#6=良构假 DOI、#7=编造 URL（着陆页不存在、无任何注册库标识符）、
  #8=无任何标识符与 URL 的裸条目）。该文件随包分发，公开可查：
  offline 结构层的实锤对象是 #8（缺 url 且无可解析标识符——结构层判
  invalid）；#6/#7 的伪造属性 offline 下诚实降为 partial（见诚实边界 1）。
- **外部标注集**：任何 JSON 均可——`{"refs": [...], "expected":
  {"1": "planted", "2": "clean", ...}}`，跑同一核验栈。

## 指标定义

| 指标 | 定义 | 方向 |
|---|---|---|
| capture_rate | 预埋伪造被判**非 verified** 的比例 | 越高越好 |
| strict_capture | 预埋伪造被判 **invalid** 的比例（结构层实锤力） | 越高越好 |
| false_kill_rate | 非伪造条目被判 **invalid** 的比例（误伤） | 越低越好 |
| distribution | 五态判定分布 | 参考态 |

## 复现命令

```bash
python tools/run_eval.py                 # 内置金标集 · offline 结构层口径
python tools/run_eval.py --refs your_labeled.json --net   # 自备标注集 · 在线口径
```

## 最新数字与历史

| 版本 | 口径 | capture | strict_capture | false_kill | 分布 |
|---|---|---|---|---|---|
| v5.3.0（2026-10-26 实测） | 内置金标 · offline | 100%（3/3） | 33%（1/3） | 0%（0/5） | partial 7 · invalid 1 |

## 独立留出集（v6.2.0：examples/holdout_real.json，16 条）

内置金标集（8 条）之外的第二评测面：**clean 条目经真实网络逐条核验后入集**
（2026-11-06 直连注册库实测，构造中凭记忆书写的 8 条 DOI 因真网核验不过被
全部剔除——真实数据铁律的现场实证）。口径与内置金标一致，复现命令：

```bash
python tools/run_eval.py --refs examples/holdout_real.json          # offline
python tools/run_eval.py --refs examples/holdout_real.json --net    # 真网
```

| 口径 | capture | strict_capture | false_kill | 备注 |
|---|---|---|---|---|
| offline（2026-11-06 实测） | 100%（8/8） | 25%（2/8） | 0%（0/8） | 裸条目/泛题名结构层实锤 |
| net（2026-11-06 实测） | 100%（8/8） | 62.5%（5/8） | 0%（0/8） | 错配/拼接/假 arXiv/良构假 DOI 全实锤 |

形态覆盖：良构假 DOI/编造 URL/裸条目/泛题名/真题名配假 DOI（错引）/真 DOI
配错 PMID（拼接）/假 arXiv×2——8 种伪造形态。**诚实边界**：预埋位置公开
（边界 4 继续适用）；net 口径数字随注册库漂移（边界 2）；clean 集真网核验
状态有时效性（站点可达性变化属 unreachable 诚实态，非误杀）。

## 元数据忠实度腐蚀集（v6.4.0：examples/holdout_fidelity.json，6 条）

M5 忠实度分级的留出评测面：真实 DOI 的受控腐蚀（exact 原样对照/minor 字段级
漂移[major/major 窗见 planted_notes]/major 题名改写），预埋标签公开。真网校准
三轮（2026-11-13）：**年份±1 属引擎设计相容（非漂移）**；轻改写 sim 仍 >0.82
一致区（窗上界实证）；批内缓存按 DOI 复用判定（既有设计）——**腐蚀条目须单条
独立跑批**（--no-cache 单跑）。实测（v6.4.0 代码+真网）：6/6 分级命中
（#4 sim 0.78→minor、#5 sim 0.65→major、原样三条 sim 1.00→无标签），腐蚀
全部落 partial 非 invalid（"完全编造"由 invalid 独占）。判定语义零改动。

## 诚实边界（必读）

1. **offline 口径只测结构层**：良构的假 DOI/假 arXiv ID（格式合法）与
   编造 URL（结构合法的着陆页地址）offline 下
   **不能**实锤——诚实降为 partial，只有 online 注册库比对能判 invalid；
   offline 能实锤的仅「缺标识符/结构不合法」类（如 #8）。这不是漏抓，是不装懂
   （查无永不判死铁律）。在线路径对无标识符引用走题名反查（partial/
   unverified），与 offline 结构层判 invalid 的口径差异如实声明。
2. **online 数字随上游漂移**：注册库（DOI.org/PubMed/arXiv）数据每日变化，
   在线口径的数字只对运行当日快照负责，本页只登记 offline 口径的可复现数字。
3. **本口径测的是机械层**：「来源是否支撑论断」是语义层职责（模型在研究
   流程中做出，机械层结构化透出），不在本评测范围。
4. 内置金标集是**设计性夹具**（预埋伪造的位置公开），它测的是判定的方向
   正确性与零误伤，不是真实世界伪造率——真实世界表现请用自备标注集跑。

关联：完整判定语义见 `references/verification-details.md`；判定与线索的
边界纪律见 `docs/adr/0005-signals-annotate-never-verdicts.md`。
