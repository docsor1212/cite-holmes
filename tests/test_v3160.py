#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.16.0 测试:卡片转化率版——desc 首行需求词前置(品牌修辞后置)/版本。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


class TestCardFirstLine(unittest.TestCase):
    """desc（SH 搜索索引源）首行=需求词逐字前置，品牌修辞后置。"""

    def _desc(self):
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        fm = zh.split("---")[1]
        import re
        m = re.search(r"description: >-\n((?:  .*\n)+)", fm)
        return " ".join(l.strip() for l in m.group(1).splitlines())

    def test_first_line_starts_with_demand_words(self):
        d = self._desc()
        self.assertTrue(d.startswith("引用核查与参考文献验真工具"), d[:40])

    def test_demand_words_in_head(self):
        d = self._desc()
        for kw in ("查文献", "核验论文引用", "检测 AI 幻觉引用", "编造 DOI",
                   "投稿前参考文献一键终检"):
            self.assertIn(kw, d[:130], kw)

    def test_brand_phrasing_not_first(self):
        d = self._desc()
        self.assertNotIn("像福尔摩斯", d[:60])
        self.assertIn("像福尔摩斯", d)  # 品牌记忆点保留在正文

    def test_length_bound(self):
        self.assertLessEqual(len(self._desc()), 1024)

    def test_metadata_single_block(self):
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertEqual(zh.split("---")[1].count("metadata:"), 1)
        self.assertIn("文献管理×AI幻觉检测", zh)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "4.6.0")
        self.assertIn("version: 4.6.0",
                      open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
