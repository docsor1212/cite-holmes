#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.7.0 测试:--check-document(解析/绑定/锚词)+ RIS 导出 + --preflight 参数面。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402

DOC = """
Thermometer reliability in living cells was demonstrated [1].
Follow-up work extended the technique [1, 2].
Penguin populations breed exclusively on Antarctic ice [3].
Narrative citation (Kucsko et al., 2013) supports this sentence.
Direct DOI link form https://doi.org/10.1038/nature12373 was also cited.
"""


class TestExtract(unittest.TestCase):

    def test_numeric_range_and_list(self):
        cits = vr.extract_citations(DOC)
        markers = {c["marker"] for c in cits}
        self.assertIn("[1]", markers)
        self.assertIn("[1, 2]", markers)
        self.assertIn("[3]", markers)

    def test_author_year_and_doi(self):
        cits = vr.extract_citations(DOC)
        kinds = {c["kind"] for c in cits}
        self.assertIn("author-year", kinds)
        self.assertIn("doi", kinds)

    def test_sentence_extraction(self):
        cits = vr.extract_citations(DOC)
        sent = next(c for c in cits if c["marker"] == "[1]")
        self.assertIn("Thermometer", sent["sentence"])


def _results():
    return [
        {"index": 1, "title": "Nanometre-scale thermometry in a living cell",
         "verdict": "verified", "year": 2013, "doi": "10.1038/nature12373",
         "checks": {"doi_metadata": {"matched": True, "adjust": "", "csl": {
             "title": "Nanometre-scale thermometry in a living cell",
             "authors": ["KUCSKO G"]}}}},
        {"index": 2, "title": "Follow-up thermometry applications",
         "verdict": "verified", "year": 2024, "doi": "10.1000/follow",
         "checks": {}},
        {"index": 3, "title": "Unicorn quantum healing review",
         "verdict": "verified", "year": 2026, "doi": "10.1000/unicorn",
         "checks": {}},
    ]


class TestBindAndAnchor(unittest.TestCase):

    def test_numeric_binding_and_anchor(self):
        cd = vr.check_document(DOC, _results())
        by_marker = {c["marker"]: c for c in cd["citations"]}
        first = by_marker["[1]"]
        self.assertTrue(first["bound"])
        self.assertEqual(first["ref_index"], 1)
        self.assertGreaterEqual(first["anchor_rate"], 0.34)  # 同题句应高锚
        unicorn = by_marker["[3]"]
        self.assertTrue(unicorn["bound"])
        self.assertLess(unicorn["anchor_rate"], 0.34)  # 独角兽句对治疗综述=低锚

    def test_low_anchor_flagged(self):
        cd = vr.check_document(DOC, _results())
        low = [c for c in cd["citations"]
               if c["bound"] and c["anchor"] == "low"]
        self.assertTrue(low)  # [3] 必须被标

    def test_summary_counts(self):
        cd = vr.check_document(DOC, _results())
        self.assertEqual(cd["n_citations"], len(cd["citations"]))
        self.assertEqual(cd["anchor_threshold"], 0.34)


class TestRISExport(unittest.TestCase):

    def test_ris_verified_only_and_fields(self):
        rows = [_res_like(1, "verified", with_csl=True),
                _res_like(2, "partial", with_csl=True, adjust=""),
                _res_like(3, "invalid", with_csl=True)]
        n = vr.export_ris(rows, "/tmp/_ris_test.ris")
        self.assertEqual(n, 2)
        txt = open("/tmp/_ris_test.ris", encoding="utf-8").read()
        self.assertIn("TY  - JOUR", txt)
        self.assertIn("DO  - 10.1000/x", txt)
        self.assertIn("ER  - ", txt)
        self.assertNotIn("invalid", txt)


def _res_like(idx, verdict, with_csl=False, adjust="partial"):
    r = {"index": idx, "title": f"Paper {idx}", "verdict": verdict,
         "year": 2024, "source": "J", "url": "https://doi.org/10.1000/x",
         "doi": "10.1000/x", "pmid": "", "arxiv": "", "note": "",
         "needs_human_check": False, "checks": {}}
    if with_csl:
        r["checks"]["doi_metadata"] = {"matched": True, "adjust": adjust,
                                       "csl": {"title": f"Paper {idx}",
                                               "authors": ["DOE J"],
                                               "container": "J of Tests",
                                               "year": 2024}}
    return r


if __name__ == "__main__":
    unittest.main(verbosity=2)
