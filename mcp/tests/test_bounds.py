#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G5 边界加固单测:批量上限/截断/坏输入(独立于产品 tests/,随 mcp/ 分发)。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # mcp/ 目录
import server  # noqa: E402


class TestBounds(unittest.TestCase):

    def test_batch_over_50_rejected(self):
        claims = [{"title": f"paper {i}", "doi": "10.1000/x"} for i in range(51)]
        out = server.verify_references_impl(claims, 1)
        self.assertIn("error", out)
        self.assertIn("> 50", out["error"])
        self.assertIn("分批", out["hint"])

    def test_batch_exactly_50_accepted(self):
        claims = [{"title": f"paper {i}", "doi": "10.1000/x"} for i in range(50)]
        with unittest.mock.patch.object(
                server.vr, "verify_one",
                side_effect=lambda ref, i, o, t, m: {
                    "index": i, "title": ref["title"], "verdict": "verified",
                    "note": "", "needs_human_check": False}):
            out = server.verify_references_impl(claims, 1)
        self.assertNotIn("error", out)
        self.assertEqual(out["scorecard"]["total"], 50)

    def test_long_strings_clipped(self):
        long_note = "x" * 5000
        with unittest.mock.patch.object(
                server.vr, "verify_one",
                side_effect=lambda ref, i, o, t, m: {
                    "index": i, "title": ref["title"], "verdict": "partial",
                    "note": long_note, "needs_human_check": False}):
            out = server.verify_references_impl(
                [{"title": "t", "doi": "10.1/x"}], 1)
        note = out["results"][0]["note"]
        self.assertLess(len(note), server._CLIP_STR + 60)
        self.assertIn("chars]", note)  # 截断标记在,长度可追溯

    def test_structured_checks_also_clipped(self):
        blob = "y" * 4000
        with unittest.mock.patch.object(
                server.vr, "verify_one",
                side_effect=lambda ref, i, o, t, m: {
                    "index": i, "title": "t", "verdict": "verified",
                    "note": "", "checks": {"doi_metadata": {"raw": blob}}}):
            out = server.verify_references_impl(
                [{"title": "t", "doi": "10.1/x"}], 1)
        raw = out["results"][0]["checks"]["doi_metadata"]["raw"]
        self.assertLess(len(raw), server._CLIP_STR + 60)

    def test_empty_and_junk_input(self):
        self.assertIn("error", server.verify_references_impl([], 1))
        out = server.verify_references_impl(["junk"], 1)
        self.assertEqual(out["results"][0]["verdict"], "invalid")

    def test_json_output_size_bounded(self):
        blob = "z" * 2000
        with unittest.mock.patch.object(
                server.vr, "verify_one",
                side_effect=lambda ref, i, o, t, m: {
                    "index": i, "title": ref["title"], "verdict": "verified",
                    "note": blob, "checks": {"deep": {"deeper": blob}}}):
            out = server.verify_references_impl(
                [{"title": f"t{i}", "doi": "10.1/x"} for i in range(10)], 1)
        size = len(json.dumps(out))
        # 10 条 × 截断后 <1k/条:总输出 < 64KB 数量级(MCP 消息安全)
        self.assertLess(size, 64 * 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)
