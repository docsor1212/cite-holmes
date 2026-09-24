#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cite-holmes MCP server — 把 verify_refs.py 的机械验证引擎暴露为 MCP 工具。

运行(需 fastmcp):
    pip install fastmcp
    python mcp/server.py            # stdio 模式
分发(免安装直跑):
    uvx --from "git+https://github.com/docsor1212/cite-holmes#subdirectory=mcp" cite-holmes-mcp

设计:核心验证逻辑 verify_references_impl 不依赖 fastmcp(纯调用 scripts/verify_refs.py),
MCP 装饰层可选导入——无 fastmcp 时本模块仍可被测试/脚本安全 import。
零密钥:默认检查(注册库可达性+元数据交叉)不需要任何 API key;
可选 key 通过环境变量 OPENALEX_API_KEY / S2_API_KEY 传入(仅附加到用户自己的请求)。
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
    语义层(来源是否支撑论断)不在本工具范围——机械层只判存在性与一致性。
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


if __name__ == "__main__":
    if not _MCP_OK:
        print("fastmcp 未安装: pip install fastmcp", file=sys.stderr)
        sys.exit(1)
    mcp.run()
