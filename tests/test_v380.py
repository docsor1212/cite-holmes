#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.8.0 测试:上下文核验进 md/html 报告 + 端到端样例/索引/反模式完备性(离线)。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402

_ROOT = os.path.dirname(HERE)
RESULTS = [{"index": 1, "title": "Nanometre-scale thermometry in a living cell",
            "verdict": "verified", "year": 2013, "doi": "10.1038/nature12373",
            "url": "https://doi.org/10.1038/nature12373", "note": "",
            "tier": "official", "http_status": 200, "needs_human_check": False,
            "checks": {"doi_metadata": {"matched": True, "adjust": "", "csl": {
                "title": "Nanometre-scale thermometry in a living cell",
                "authors": ["KUCSKO G"], "container": "Nature", "year": 2013}}}}]
CC = vr.check_document(
    "Kucsko et al. (2013) demonstrated nanoscale thermometry.", RESULTS)
CC_LOW = vr.check_document(
    "Penguin populations breed exclusively on Antarctic ice [1].", RESULTS)


class TestContextInReports(unittest.TestCase):

    def test_md_renders_context_section(self):
        md = vr.render_md(RESULTS, True, "general", context_check=CC)
        self.assertIn("上下文核验（正文 in-text 引用）", md)
        md_low = vr.render_md(RESULTS, True, "general", context_check=CC_LOW)
        self.assertIn("疑似错配引文", md_low)  # 低锚条目产出复核提示

    def test_md_without_context_no_section(self):
        md = vr.render_md(RESULTS, True, "general")
        self.assertNotIn("上下文核验（正文 in-text 引用）", md)

    def test_html_renders_context_section(self):
        html = vr.render_html(RESULTS, True, "general", context_check=CC)
        self.assertIn("上下文核验（正文 in-text 引用）", html)


class TestDocsCompleteness(unittest.TestCase):

    def test_references_index_exists(self):
        p = os.path.join(_ROOT, "references", "INDEX.md")
        self.assertTrue(os.path.isfile(p))
        txt = open(p, encoding="utf-8").read()
        self.assertIn("faq.md", txt)

    def test_antipatterns_consolidated(self):
        p = os.path.join(_ROOT, "references", "anti-patterns.md")
        txt = open(p, encoding="utf-8").read()
        self.assertIn("触发词误触发", txt)
        self.assertIn("跨语言", txt)

    def test_e2e_sample_complete(self):
        e2e = os.path.join(_ROOT, "examples", "end-to-end")
        for f in ("README.md", "research_refs.json", "paper_excerpt.md",
                  "report.md", "exports/report.bib", "exports/report.ris"):
            self.assertTrue(os.path.isfile(os.path.join(e2e, f)), f)

    def test_faq_new_entries(self):
        faq = open(os.path.join(_ROOT, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("触发词误触发", faq)
        self.assertIn("中英混合引用", faq)


if __name__ == "__main__":
    unittest.main(verbosity=2)
