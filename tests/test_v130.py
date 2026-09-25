#!/usr/bin/env python3
import re
# -*- coding: utf-8 -*-
"""v1.3.0（可发现版）：EN desc 任务词根 + MCP server。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "mcp"))
import verify_refs as vr  # noqa: E402

SKILL = os.path.join(HERE, "..", "SKILL.md")
ROOTS = ["citation verification", "verify citations", "citation checker",
         "hallucinated references", "fact check"]


class TestV130(unittest.TestCase):
    def setUp(self):
        vr._net_reset()

    def test_version_is_130(self):
        self.assertEqual(vr.VERSION, "2.0.0")

    def test_en_description_contains_all_task_roots(self):
        s = open(SKILL, encoding="utf-8").read()
        fm = s.split("---")[1]
        m = re.search(r"description:\s*>-?\n((?:[ \t]+.*\n?)+)", fm) \
            if (re := __import__("re")) else None
        block = m.group(1) if m else ""
        low = " ".join(l.strip() for l in block.splitlines()).lower()
        for r in ROOTS:
            self.assertIn(r, low, f"EN desc 缺任务词根: {r}")

    def test_en_description_length_safe(self):
        import re
        s = open(SKILL, encoding="utf-8").read()
        fm = s.split("---")[1]
        m = re.search(r"description:\s*>-?\n((?:[ \t]+.*\n?)+)", fm)
        self.assertLessEqual(len(m.group(1)), 1024, "desc 超 1024 会被平台静默丢弃")

    def test_frontmatter_five_keys_present(self):
        import re
        fm = open(SKILL, encoding="utf-8").read().split("---")[1]
        for k in ("name:", "version:", "author:", "license:",
                  "description:", "when_to_use:"):
            self.assertIn(k, fm, f"frontmatter 缺键 {k}")
        # 块标量结尾必须换行接下一键(doc-holmes 粘连案例)
        self.assertNotIn("built in.when_to_use", open(SKILL, encoding="utf-8").read())

    def test_mcp_impl_verifies_and_scores(self):
        import server
        claims = [{"title": "Real Paper About X", "doi": "10.1000/real",
                   "source": "J", "year": 2026}]
        with unittest.mock.patch.object(
                server.vr, "verify_one",
                side_effect=lambda ref, i, o, t, m: {
                    "index": i, "title": ref["title"], "verdict": "verified",
                    "note": "", "needs_human_check": False}):
            out = server.verify_references_impl(claims, 5)
        self.assertEqual(out["scorecard"]["total"], 1)
        self.assertEqual(out["results"][0]["verdict"], "verified")

    def test_mcp_impl_handles_bad_input(self):
        import server
        out = server.verify_references_impl([], 5)
        self.assertIn("error", out)
        out2 = server.verify_references_impl(["junk"], 5)
        self.assertEqual(out2["results"][0]["verdict"], "invalid")

    def test_mcp_server_file_syntax(self):
        p = os.path.join(HERE, "..", "mcp", "server.py")
        src = open(p, encoding="utf-8").read()
        compile(src, "server.py", "exec")
        self.assertIn("verify_references_impl", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
