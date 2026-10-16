#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.13.0 测试:方法论基建版——GLOSSARY 正词表/ADR 公开层/out-of-scope/
openai.yaml/CALIBRATE 三规则。含领头羊红线泄漏审查(内部项目关键词零命中)。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


class TestGlossary(unittest.TestCase):
    def test_exists_with_canonical_terms(self):
        t = open(os.path.join(SK, "references", "GLOSSARY.md"), encoding="utf-8").read()
        for term in ("**verified**", "**partial**", "**unreachable**", "**invalid**",
                     "**unverified**", "**claim-triplet**", "**CiteScore**",
                     "**克隆引用对**", "**清单画像**", "**跨语言桥接**"):
            self.assertIn(term, t, term)

    def test_avoid_lists_present(self):
        t = open(os.path.join(SK, "references", "GLOSSARY.md"), encoding="utf-8").read()
        self.assertGreaterEqual(t.count("_Avoid_"), 12)

    def test_zero_implementation_details(self):
        # GLOSSARY 纯度铁律:不出现实现细节(文件名/函数名/参数)
        t = open(os.path.join(SK, "references", "GLOSSARY.md"), encoding="utf-8").read()
        for bad in ("def ", "import ", "verify_refs.py --", "args.", "--fast-judge-url"):
            self.assertNotIn(bad, t, bad)


class TestADR(unittest.TestCase):
    def test_index_and_seven_adrs(self):
        rd = open(os.path.join(SK, "docs", "adr", "README.md"), encoding="utf-8").read()
        self.assertIn("ADR-0001", rd)
        self.assertEqual(rd.count("]("), 7)
        for i in range(1, 8):
            p = os.path.join(SK, "docs", "adr", f"000{i}-" )
            self.assertTrue(any(f.startswith(f"000{i}-")
                                for f in os.listdir(os.path.join(SK, "docs", "adr"))), p)

    def test_adrs_public_layer_only(self):
        # 领头羊红线:公开 ADR 不含内部审计项目细节(F12/F13/静默伪装族/盲测轮为论文资产)
        import glob
        for f in glob.glob(os.path.join(SK, "docs", "adr", "*.md")):
            t = open(f, encoding="utf-8").read()
            for kw in ("F12", "F13", "静默伪装", "盲测", "N073", "CONFOUNDED",
                       "臂 B", "可行性悬崖", "gold-anchor", "NUMBERS"):
                self.assertNotIn(kw, t, f"{os.path.basename(f)}: {kw}")

    def test_each_adr_has_decision_and_consequence(self):
        import glob
        for f in glob.glob(os.path.join(SK, "docs", "adr", "0*.md")):
            t = open(f, encoding="utf-8").read()
            self.assertIn("## 决策", t, f)
            self.assertIn("## 后果", t, f)
            self.assertIn("状态: Accepted", t, f)


class TestOutOfScope(unittest.TestCase):
    def test_entries_with_reasons(self):
        t = open(os.path.join(SK, "references", "out-of-scope.md"), encoding="utf-8").read()
        self.assertGreaterEqual(t.count("| 不做什么"), 1)
        # 关键非目标在案
        for kw in ("PDF/Word", "万方", "自动求星", "unreachable"):
            self.assertIn(kw, t, kw)

    def test_no_internal_project_keywords(self):
        t = open(os.path.join(SK, "references", "out-of-scope.md"), encoding="utf-8").read()
        for kw in ("F13", "盲测", "静默伪装"):
            self.assertNotIn(kw, t)


class TestCalibrateAndMeta(unittest.TestCase):
    def test_calibrate_three_rules_bilingual(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn('phrased so "yes" accepts it', en)
        self.assertIn("order questions by dependency", en)
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("措辞让\"是\"即接受推荐", zh)
        self.assertIn("决策永远留给用户", zh)

    def test_openai_yaml(self):
        y = open(os.path.join(SK, "agents", "openai.yaml"), encoding="utf-8").read()
        self.assertIn("display_name", y)
        self.assertIn("short_description", y)

    def test_index_and_files_wiring(self):
        idx = open(os.path.join(SK, "references", "INDEX.md"), encoding="utf-8").read()
        self.assertIn("GLOSSARY.md", idx)
        self.assertIn("out-of-scope.md", idx)
        sk = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("references/GLOSSARY.md", sk)
        self.assertIn("docs/adr/", sk)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "4.2.0")
        self.assertIn("version: 4.2.0",
                      open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
