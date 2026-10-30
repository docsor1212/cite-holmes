#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.8.0 测试：语义保真（程序故障≠确凿判死）+ 文档保真锁。

F46=CLI/MCP 四处未知异常兜底从 invalid 改 unverified（invalid 的语义保留给
真实伪造——评测 errorHandling 点名）；F47=MCP 文档「三原语/2 tools」旧表述
刷新 + verification-details 撤稿节旧语义刷新。全部 sealed（tmpdir 桩）。"""
import json
import os
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


class F46_CliExceptionSemantics(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _boom(self, *a, **k):
        raise RuntimeError("模拟程序故障")

    def test_serial_path_unverified_not_invalid(self):
        with unittest.mock.patch.object(vr, "verify_one", side_effect=self._boom), \
             unittest.mock.patch.object(vr.time, "sleep", lambda s: None):
            out = vr.verify_one.__self__ if False else None
        # 直接走 main 串行路径：--refs 指向一个条目，verify_one 必炸
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "refs.json")
            json.dump([{"title": "Trigger internal failure entry",
                        "url": "https://example.org/a", "year": 2020}],
                      open(refs, "w", encoding="utf-8"))
            out_path = os.path.join(td, "r.md")
            with unittest.mock.patch.object(
                    vr, "check_url", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "doi_metadata_match", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "pubmed_pmid_exists", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "arxiv_metadata_match", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "wayback_available", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "landing_title_check", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "openalex_title_check", side_effect=self._boom):
                rc = vr.main_with_args(["--refs", refs, "--out", out_path])
            self.assertEqual(rc, 0)  # 单条故障不拖垮退出码语义（非 strict）
            doc = json.load(open(out_path.rsplit(".", 1)[0] + ".json",
                                 encoding="utf-8"))
            r = doc["results"][0]
            self.assertEqual(r["verdict"], "unverified",
                             "程序故障不得伪装成判定（评测 errorHandling 点名）")
            self.assertTrue(r["needs_human_check"])
            self.assertIn("处理异常", r["note"])
            self.assertIn("--refresh-cache", r["note"])

    def test_parallel_path_unverified_not_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "refs.json")
            json.dump([{"title": "Parallel boom entry one", "url":
                        "https://example.org/p1", "year": 2020}],
                      open(refs, "w", encoding="utf-8"))
            out_path = os.path.join(td, "r.md")
            with unittest.mock.patch.object(
                    vr, "check_url", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "doi_metadata_match", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "pubmed_pmid_exists", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "arxiv_metadata_match", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "wayback_available", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "landing_title_check", side_effect=self._boom), \
                 unittest.mock.patch.object(
                     vr, "openalex_title_check", side_effect=self._boom):
                rc = vr.main_with_args(["--refs", refs, "--workers", "4",
                                        "--out", out_path])
            self.assertEqual(rc, 0)
            doc = json.load(open(out_path.rsplit(".", 1)[0] + ".json",
                                 encoding="utf-8"))
            self.assertEqual(doc["results"][0]["verdict"], "unverified")


class F46_McpExceptionSemantics(unittest.TestCase):
    """源码锚点锁（引擎层语义已由 F46_Cli 覆盖——同一 verify_one/同一兜底形态）。"""

    def test_impl_semantics_source_anchors(self):
        src = open(os.path.join(SK, "mcp", "server.py"), encoding="utf-8").read()
        # 程序故障 → unverified + 转人工（非判定结果）
        self.assertIn('"verdict": "unverified",\n'
                      '                 "note": f"处理异常（{type(e).__name__}）——非判定结果，建议重跑或反馈"',
                      src)
        # 结构非法（非对象）仍 invalid——确凿判死语义保留
        self.assertIn('"verdict": "invalid"', src)
        self.assertIn('"note": "条目不是对象"', src)
        # 全文件不再有「处理异常→invalid」的旧语义
        self.assertNotIn('"verdict": "invalid", "note": f"处理异常', src)


class F47_DocFidelity(unittest.TestCase):
    def test_no_three_primitive_wording(self):
        for f in ("mcp/server.py", "mcp/MCP_SUBMISSION.md"):
            src = open(os.path.join(SK, f), encoding="utf-8").read()
            self.assertNotIn("三原语", src, f)
        self.assertIn("5 tools（v5.6 起）+ 2 resources + 1 工作流 prompt",
                      open(os.path.join(SK, "mcp", "MCP_SUBMISSION.md"),
                           encoding="utf-8").read())

    def test_retraction_semantics_current(self):
        vd = open(os.path.join(SK, "references", "verification-details.md"),
                  encoding="utf-8").read()
        import re as _re
        _flat = _re.sub(r"\s+", " ", vd)
        self.assertIn("semantics current as of v4.1", _flat)
        self.assertIn("Expression of Concern", _flat)
        self.assertNotIn("Check failures are silently skipped", _flat)  # 旧 phrasing 不存
        self.assertIn("never silently skipped", _flat)                   # 新语义：显式标记
        faq = open(os.path.join(SK, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("unverified 而不是 invalid", faq)

    def test_no_stale_tool_counts(self):
        readme = open(os.path.join(SK, "mcp", "README.md"),
                      encoding="utf-8").read()
        self.assertNotIn("三个工具", readme)
        self.assertNotIn("3 个工具", readme)


if __name__ == "__main__":
    unittest.main()
