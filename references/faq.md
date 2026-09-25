# FAQ (moved out of SKILL.md in v1.9 to keep the main guide short)

**Q: Is a `verified` citation guaranteed real?**
No. The mechanical layer catches machine-checkable fakes: nonexistent DOIs,
fabricated PMIDs (via E-utilities), fabricated arXiv IDs (via the official
arXiv API), dead links, duplicates, stitched DOI↔PMID pairs, wrong-paper
DOIs (title similarity), and retracted papers. A fabricated citation pointing
to a real, plausible page still relies on the semantic layer — never a
guarantee.

**Q: How are arXiv references checked?**
Same treatment as DOIs since v1.5: the official export.arxiv.org API returns
the registered title/year; similarity below 0.50 → `invalid` (fabricated or
wrong ID), 0.50–0.82 → `partial` (human review), above → consistent. An ID the
API has never heard of is `invalid`, not `unreachable`.

**Q: What do I do with `unreachable` references?**
Open them manually once — the report automatically attaches a Wayback Machine
archive link when one exists. If it matters and keeps failing, switch sources.

**Q: Did the PMID check fail because of my network?**
No. "不存在/编造" verdicts come from the official E-utilities API — that means the
PMID genuinely isn't in PubMed. Only "校验失败" wording means a network/API issue
(the reference is then treated as reachable and flagged).

**Q: Do I always need `--profile medical`?**
Use `--easy`: one flag auto-detects medical references, enables the medical
profile, and exports BibTeX + CSV automatically. For real clinical
conclusions, still prefer explicit `--profile medical`.

**Q: Can verified references go straight into my paper?**
Yes: `--export bibtex` exports only `verified` entries (with PMID / arXiv
eprint notes) and imports into Zotero/EndNote; `--export csv` is the full
audit ledger for advisors and editors; `--export auditjson` (v1.9) is the
machine-readable per-check working paper for institutional audit.

**Q: Which services does verification touch, and what if my network is slow or blocked?**
DOI.org (DOI metadata), NCBI E-utilities (PMID), export.arxiv.org (arXiv
metadata), archive.org (archived copies), api.crossref.org (retractions),
api.openalex.org (bibliographic confirmation), api.semanticscholar.org (third
source + title search, v1.9/v1.10). CN networks occasionally throttle several
of them. The verifier never stalls: transient failures retry once (429 honors
`Retry-After`), error notes tell you the cause with a fix (`--timeout 20` for
slow links), and a host-level circuit breaker skips a host after 2 consecutive
transport failures — with an honest note — instead of hanging the batch.
Since v1.10, references are verified in parallel (`--workers 4` by default —
roughly a quarter of the serial wall time), and when 3+ different hosts fail
at the transport layer in one run (restricted-egress signature) remaining
lookups are fast-skipped with a "全局网络降级" note and a proxy/retry
suggestion. Degraded checks are always labeled, never silently dropped.

**Q: Do I need API keys?**
No — everything runs keyless within public rate limits. OpenAlex has required
keys for *production* use since 2026-02 (free daily allowance; this skill
survives keyless but benefits from `--openalex-key` / `OPENALEX_API_KEY`).
Semantic Scholar keyless shares a rate pool; `--s2-key` / `S2_API_KEY` gets a
dedicated lane. Crossref asks heavy users to identify themselves — pass
`--mailto you@lab.edu` to join the polite pool.

**Q: MCP 模式是什么？agent 不装 skill 怎么用？**
v2.0.0 起仓库内置 `mcp/server.py`（FastMCP）：tools `verify_references`（机械验证）/
`explain_verdict`（判定解释）、resources（能力矩阵/版本史）、prompts（fact-check 工作流）。
推荐直跑：`uvx --from "git+https://github.com/docsor1212/cite-holmes#subdirectory=mcp" cite-holmes-mcp`；
或自行准备 FastMCP 环境后运行 `python mcp/server.py`。零密钥可用；可选 API key 经环境变量注入。

**Q: arXiv 论文有多个修订版怎么办？**
v2.0.0 自动备注：引用未指定版本而论文存在多个修订版 → 提示"引用未指定版本"；
引用指向旧版而存在更新版 → 提示最新版号（旧版可能含未修正内容）。同响应内取数，零额外请求。

**Q: 验证要访问哪些外部服务？国内网络慢怎么办？**
见上方服务清单——全部是官方学术注册库、全部 HTTPS。v1.12 起两件事让它在国内更可用：
① **持久磁盘缓存**默认开（7 天 TTL）：同一批引用复跑直接复用稳定判定、零外呼，
`--refresh-cache` 强制重验；② **`--proxy http://host:port`** 显式走代理（或设
`HTTPS_PROXY` 环境变量），配合网络降级模式，受限出口下也能一次跑完拿到诚实结论。

**Q: 判定结果会被缓存吗？撤稿状态更新了怎么办？**
缓存只存 verified/partial/invalid 三种稳定判定（TTL 默认 168 小时），
unreachable 永不入缓存（瞬态）；`--strict` 模式强制绕过缓存读（CI 诚实）。
撤稿状态这类可变信息以 TTL 为界——对时效敏感的批次用 `--refresh-cache` 强制重验。

**Q: Can I verify references straight from my reference manager?**
Yes, since v1.9: `--refs bibliography.bib` reads Zotero/EndNote/JabRef BibTeX
exports directly (entry types, nested braces, `\url{}` macros; DOI/PMID/arXiv
fields are picked up automatically).

## arXiv 条目 note 里出现「元数据 API 不稳，经官方着陆页标题比对确认」正常吗？

正常。arXiv 的 API 对批内多请求有反机器人窗口（偶发 406/403），与你的网络无关；
验证器已自动回退官方着陆页完成同等强度的标题比对，判定可信度不受影响。

## semantic 字段写什么？

模型逐条判定"来源是否真的支撑所引论断"后，写成结构化对象
`{"claim", "support", "quote", "note"}`（五值：supported / partial /
not_in_source / contradicted / unclear）。`not_in_source` 与 `contradicted`
会被机械验证器封顶为 `partial` 并转入人工复核区——来源存在不等于来源认同。
旧的字符串写法仍接受（仅注记）。
