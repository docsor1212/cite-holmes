#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DoD2 E2E:真实 MCP 客户端(fastmcp Client)全原语跑通。
两面证据:①in-memory Client 全原语(tools/list+call/resources/prompts)
②stdio 子进程传输(uvx 本地路径)initialize+tools/list(传输层证据)。
产出:stdout 全文 → e2e_transcript.md(人工附时间戳与环境说明后归档)。"""
import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

CLAIMS = [
    {"title": "Nanometre-scale thermometry in a living cell",
     "doi": "10.1038/nature12373", "source": "Nature", "year": 2013},
    {"title": "Completely Fabricated Hallucinated Paper About Unicorn Quantum Healing",
     "doi": "10.9999/bogus.12345", "source": "Journal of Made Things", "year": 2026},
    {"title": "Lower sperm DNA fragmentation after r-FSH administration in "
              "functional hypogonadotropic hypogonadism", "pmid": "23435529",
     "source": "J Assist Reprod Genet", "year": 2013},
]


def section(t):
    print(f"\n{'=' * 64}\n== {t}\n{'=' * 64}", flush=True)


async def main():
    section("A. in-memory Client — full primitives")
    async with Client(server.mcp) as c:
        tools = await c.list_tools()  # initialize 在 connect 时隐式完成
        print("[initialize] connected ok (in-memory transport)")
        names = sorted(t.name for t in tools)
        print(f"[tools/list] {len(tools)} tools: {names}")
        assert names == ["explain_verdict", "verify_references"], names

        print("[tools/call verify_references] 3 claims (good DOI / bad DOI / PMID)...")
        res = await c.call_tool("verify_references",
                                {"claims": CLAIMS, "timeout": 20})
        payload = json.loads(res.content[0].text)
        sc = payload["scorecard"]
        print(f"  version={payload['version']} CiteScore={sc['score']}/100 "
              f"grade={sc.get('grade')} total={sc['total']}")
        for r in payload["results"]:
            print(f"  [{r['index']}] {r['verdict']:11s} {(r.get('title') or '')[:52]}")
        assert len(payload["results"]) == 3

        print("[tools/call explain_verdict] on the result above...")
        one = payload["results"][1]
        res2 = await c.call_tool("explain_verdict", {"result": one})
        ex = json.loads(res2.content[0].text)
        print(f"  verdict={ex['verdict']} | why: {ex['why'][:60]}...")
        print(f"  action: {ex['suggested_action'][:60]}...")

        print("[resources/read capability-matrix]")
        rm = await c.read_resource("cite-holmes://capability-matrix")
        cap = rm[0].text
        print(f"  {len(cap)} chars, head: {cap[:80]!r}")

        print("[resources/read changelog]")
        rc = await c.read_resource("cite-holmes://changelog")
        print(f"  {len(rc[0].text)} chars, tail: ...{rc[0].text[-80:]!r}")

        print("[prompts/get fact_check_workflow]")
        pr = await c.get_prompt("fact_check_workflow", {"topic": "SLE biotherapeutics"})
        print(f"  messages={len(pr.messages)} head: {pr.messages[0].content.text[:70]!r}")

    section("B. stdio subprocess (uvx local) — transport-level evidence")
    from fastmcp.client.transports import StdioTransport
    t = StdioTransport("uvx", ["--from", os.path.dirname(HERE := os.path.dirname(
        os.path.abspath(__file__))), "cite-holmes-mcp"])
    async with Client(t) as c:
        tools = await c.list_tools()
        print(f"[stdio initialize+tools/list] {len(tools)} tools via subprocess: "
              f"{sorted(x.name for x in tools)}")

    section("E2E PASS — all primitives exercised over real MCP client")


if __name__ == "__main__":
    asyncio.run(main())
