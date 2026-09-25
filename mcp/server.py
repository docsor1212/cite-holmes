#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cite-holmes MCP server (v2.0.0) — 三原语形态(tools/resources/prompts)。

运行(需 FastMCP 环境):
    uvx --from "git+https://github.com/docsor1212/cite-holmes#subdirectory=mcp" cite-holmes-mcp
    # 或自行准备 FastMCP 环境后: python mcp/server.py   # stdio 模式
分发(免安装直跑):
    uvx --from "git+https://github.com/docsor1212/cite-holmes#subdirectory=mcp" cite-holmes-mcp

设计原则:
- 核心验证逻辑 verify_references_impl / explain_verdict_impl 不依赖 fastmcp
  (纯调用 scripts/verify_refs.py),无 fastmcp 环境下本模块仍可安全 import 与测试。
- 零密钥:verify_references 默认检查不需要 API key;可选 key 经环境变量
  OPENALEX_API_KEY / S2_API_KEY / NCBI_API_KEY 传入(只附加到用户自己的请求)。
- 语义层(来源是否支撑论断)不在机械工具范围,由 agent 自行判定后可用
  semantic 字段回灌 CLI 做封顶。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))

import verify_refs as vr  # noqa: E402

try:
    from fastmcp import FastMCP
    _MCP_OK = True
except ImportError:  # pragma: no cover - 无 fastmcp 环境下仅使用 impl
    _MCP_OK = False


def verify_references_impl(claims: list, timeout: float = 15.0) -> dict:
    """机械验证一组引用(纯实现,无 MCP 依赖)。

    claims: [{"title": str, "url"?: str, "doi"?: str, "pmid"?: str,
              "arxiv"?: str, "source"?: str, "year"?: int}, ...]
    返回: {"version", "scorecard": {score, grade, counts}, "results": [...]}
    """
    if not isinstance(claims, list) or not claims:
        return {"error": "claims must be a non-empty array of reference objects",
                "hint": 'e.g. [{"title": "...", "doi": "10.xxxx/..."}]'}
    vr._net_reset()
    results = []
    for i, ref in enumerate(claims, 1):
        if not isinstance(ref, dict):
            results.append({"index": i, "title": str(ref)[:48], "verdict": "invalid",
                            "note": "条目不是对象", "needs_human_check": True})
            continue
        try:
            r = vr.verify_one(ref, i, False, float(timeout), False)
        except Exception as e:
            r = {"index": i, "title": str(ref.get("title") or "")[:48],
                 "verdict": "invalid", "note": f"处理异常（{type(e).__name__}）",
                 "needs_human_check": True}
        results.append(r)
    vr.mark_duplicates(results)
    vr.apply_semantic_cap(results)
    sc = vr.compute_scorecard(results)
    return {"version": vr.VERSION, "scorecard": sc, "results": results}


def explain_verdict_impl(result: dict) -> dict:
    """五态判定语义解释器:verdict+checks → 中文判定依据 + 建议动作。

    输入为 verify_references 返回的单条 result(含 checks 明细)。
    纯静态映射,零网络调用——LLM 友好的解释原语。
    """
    v = result.get("verdict")
    checks = result.get("checks") or {}
    notes = (result.get("note") or "")
    base = {
        "verified": ("来源存在、处于权威层级、字段完整，且通过官方注册库交叉核验",
                     "可支撑正文结论；引用时保留原始链接与判定时间"),
        "partial": ("来源可达但存在降级因素（社区层级/字段缺失/元数据存疑/撤稿/语义否定）",
                    "降级使用：正文引用需注明保留意见，或先人工复核再升级"),
        "unreachable": ("本次抓取失败（404/超时/反爬），不等于不存在",
                        "先开报告附带的 Wayback 存档链对照；关键来源反复失败则更换信源"),
        "invalid": ("标识符不存在、指向错误论文或拼接伪造——机械层确凿判死",
                    "不得引用；从清单删除或更换信源"),
        "unverified": ("未执行检查（离线模式或跳过）",
                       "联网环境重跑以获得真实判定"),
    }.get(v)
    if base is None:
        return {"error": f"unknown verdict: {v}"}
    why, action = base
    steps = []
    c = checks or {}
    if c.get("doi_metadata", {}).get("matched"):
        steps.append("DOI.org 注册元数据比对一致（标题/年份）")
    if c.get("arxiv_metadata", {}).get("matched"):
        steps.append("arXiv 官方 API 元数据比对一致")
    if c.get("s2", {}).get("matched"):
        steps.append("Semantic Scholar 第三源交叉确认")
    if c.get("retraction", {}).get("retracted"):
        steps.append("⚠️ Crossref/Retraction Watch 命中撤稿记录")
    if c.get("openalex", {}).get("confirmed"):
        steps.append("OpenAlex 书目级存在性确认")
    if c.get("url", {}).get("reachable") is True:
        steps.append(f"来源页可达（HTTP {c.get('url', {}).get('status')}）")
    if c.get("url", {}).get("status") == 403:
        steps.append("着陆页 403（注册库已确认存在性，未受反爬影响）")
    if c.get("wayback", {}).get("archive_found"):
        steps.append("Wayback 存档对照可用")
    if not steps:
        steps.append("（无已执行的结构化检查记录——offline 模式或早期返回）")
    return {"verdict": v, "why": why, "evidence_steps": steps,
            "suggested_action": action,
            "raw_note": notes[:300]}


def _capability_text() -> str:
    cap = vr.capability_matrix()
    lines = ["# cite-holmes capability matrix",
             "", "## Mechanical layer catches", ""]
    lines += [f"- {x}" for x in cap["caught"]]
    lines += ["", "## Semantic layer (model/agent judgment)", ""]
    lines += [f"- {x}" for x in cap["semantic"]]
    lines += ["", "## Unsupported inputs", ""]
    lines += [f"- {x}" for x in cap.get("unsupported", [])]
    return "\n".join(lines)


if _MCP_OK:
    mcp = FastMCP("cite-holmes")

    @mcp.tool
    def verify_references(claims: list, timeout: float = 15.0) -> str:
        """Verify a list of references for hallucinated/fabricated citations.

        Each claim object: {"title": str (required), "url"/"doi"/"pmid"/"arxiv": str (optional),
        "source": str, "year": int}. Returns CiteScore (0-100) plus per-reference verdicts:
        verified / partial / unreachable / invalid. Pure mechanical verification against
        official registries (DOI.org, PubMed E-utilities, arXiv, Crossref/Retraction Watch);
        no API keys required, no telemetry."""
        return json.dumps(verify_references_impl(claims, timeout),
                          ensure_ascii=False, indent=1)

    @mcp.tool
    def explain_verdict(result: dict) -> str:
        """Explain one verdict from verify_references in plain language.

        Pass a single result object (with its checks) back; returns why the verdict
        was reached (evidence steps), what it means, and the suggested next action.
        Zero network calls — static explanation layer."""
        return json.dumps(explain_verdict_impl(result), ensure_ascii=False, indent=1)

    @mcp.resource("cite-holmes://capability-matrix")
    def capability_matrix_resource() -> str:
        """What this verifier catches, what stays with the semantic layer,
        and which inputs are unsupported."""
        return _capability_text()

    @mcp.resource("cite-holmes://changelog")
    def changelog_resource() -> str:
        """Version history summary (major releases)."""
        return ("cite-holmes versions: v1.2 medical mode + exports; v1.3 CiteScore; "
                "v1.4 DOI cross-check; v1.5 arXiv verification + Wayback; v1.6 circuit "
                "breaker + DOI-PMID cross-check; v1.7 author check + HTML report; "
                "v1.8 retraction detection + OpenAlex; v1.9 Semantic Scholar + BibTeX "
                "import + keys; v1.10 parallel + degraded-network; v1.11 arXiv fallback "
                "+ semantic audit; v1.12 disk cache + proxy + security declaration; "
                "v1.13 task-language description; v2.0 MCP three-primitives + arXiv "
                "version note + NCBI key + evidence chain. Current: " + vr.VERSION)

    @mcp.prompt
    def fact_check_workflow(topic: str) -> str:
        """Three-step workflow: research the topic, then machine-verify every citation."""
        return (
            f"Research task: {topic}\n\n"
            "1. Search iteratively (both languages if the topic spans CN/EN); fetch the "
            "2-5 most valuable sources in full.\n"
            "2. Register every reference you cite as "
            '{"title", "url"/"doi"/"pmid"/"arxiv", "source", "year"} and call '
            "verify_references on the full list.\n"
            "3. For every non-verified verdict, call explain_verdict on that result and "
            "follow its suggested_action before writing conclusions. Never cite an "
            "unverified reference in the final text.")


if __name__ == "__main__":
    if not _MCP_OK:
        print("缺少 FastMCP 运行环境：uvx --from \"git+https://github.com/docsor1212/cite-holmes#subdirectory=mcp\" cite-holmes-mcp", file=sys.stderr)
        sys.exit(1)
    mcp.run()
