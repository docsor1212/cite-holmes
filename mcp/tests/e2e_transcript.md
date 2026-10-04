# cite-holmes MCP E2E transcript（DoD2 证据，正式版）

- 时间: 2026-10-04 22:49:50 CST
- 环境: 82 机 / Python 3.11.15 (uv) / fastmcp 4.0.10 / uv 0.11.21
- 命令: `cd mcp && uv run --with fastmcp python tests/e2e_run.py`
- 判定: **E2E PASS**（in-memory 全原语 + stdio 子进程 2 tools）
- 附注: 配对已核真（好 DOI/坏 DOI/真 PMID+真标题）。上一版 transcript(e2e_transcript_crossedcatch.md)记录了本 agent 自己配错标题被产品当场判 invalid——产品按设计工作的额外证据。

```

================================================================
== A. in-memory Client — full primitives
================================================================
[initialize] connected ok (in-memory transport)
[tools/list] 2 tools: ['explain_verdict', 'verify_references']
[tools/call verify_references] 3 claims (good DOI / bad DOI / PMID)...
  version=3.5.0 CiteScore=40/100 grade=D total=3
  [1] verified    Nanometre-scale thermometry in a living cell
  [2] invalid     Completely Fabricated Hallucinated Paper About Unico
  [3] verified    Lower sperm DNA fragmentation after r-FSH administra
[tools/call explain_verdict] on the result above...
  verdict=invalid | why: 标识符不存在、指向错误论文或拼接伪造——机械层确凿判死...
  action: 不得引用；从清单删除或更换信源...
[resources/read capability-matrix]
  539 chars, head: '# cite-holmes capability matrix\n\n## Mechanical layer catches\n\n- 假 DOI（DOI.org 查无'
[resources/read changelog]
  758 chars, tail: ...'ON object) + offline retraction cache; v3.3 NLI third vote panel. Current: 3.5.0'
[prompts/get fact_check_workflow]
  messages=1 head: 'Research task: SLE biotherapeutics\n\n1. Search iteratively (both langua'

================================================================
== B. stdio subprocess (uvx local) — transport-level evidence
================================================================


╭──────────────────────────────────────────────────────────────────────────────╮
│                                                                              │
│                                                                              │
│                         ▄▀▀ ▄▀█ █▀▀ ▀█▀ █▀▄▀█ █▀▀ █▀█                        │
│                         █▀  █▀█ ▄▄█  █  █ ▀ █ █▄▄ █▀▀                        │
│                                                                              │
│                                                                              │
│                                                                              │
│                                FastMCP 4.0.10                                │
│                            https://gofastmcp.com                             │
│                                                                              │
│                  🖥  Server:      cite-holmes, 4.0.10                         │
│                  🚀 Deploy free: https://horizon.prefect.io                  │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯


[10/04/26 22:50:04] INFO     Starting MCP server 'cite-holmes'  transport.py:242
                             with transport 'stdio'                             
[stdio initialize+tools/list] 2 tools via subprocess: ['explain_verdict', 'verify_references']

================================================================
== E2E PASS — all primitives exercised over real MCP client
================================================================
```
