#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.3.1:标题清洗(clean_title)——提升元数据匹配精度。"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import verify_refs as vr  # noqa: E402


class TestCleanTitle(unittest.TestCase):
    def test_t1_strip_doi_suffix(self):
        r = vr.clean_title("AlphaFold is accurate. Nature 2021. doi:10.1038/s41586-021-03819-2")
        self.assertNotIn("doi:", r.lower())
        self.assertIn("AlphaFold", r)

    def test_t2_strip_pmid(self):
        r = vr.clean_title("Some paper title PMID: 34545033")
        self.assertNotIn("PMID", r)

    def test_t3_strip_numbering(self):
        r = vr.clean_title("1. Great paper about biology")
        self.assertTrue(r.startswith("Great"))

    def test_t4_strip_year_ending(self):
        r = vr.clean_title("A study of something. 2021")
        self.assertNotIn("2021", r)

    def test_t5_preserves_core(self):
        t = "Highly accurate protein structure prediction with AlphaFold"
        r = vr.clean_title(t)
        self.assertEqual(t, r)

    def test_t6_chinese(self):
        r = vr.clean_title("阿尔法折叠预测蛋白质结构。2021年")
        self.assertNotIn("2021", r)

    def test_t7_empty_fallback(self):
        r = vr.clean_title("")
        self.assertEqual(r, "")

    def test_t8_et_al(self):
        r = vr.clean_title("Smith J, et al. Great biology paper. 2020. Journal of Science")
        self.assertTrue("Journal" in r or "biology" in r.lower(), f"got: {r}")
        self.assertIn("smith", r.lower())

    def test_t9_version(self):
        self.assertEqual(vr.VERSION, "3.4.0")


if __name__ == "__main__":
    unittest.main()
