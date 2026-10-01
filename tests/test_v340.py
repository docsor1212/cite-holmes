# -*- coding: utf-8 -*-
"""v3.4 池:PMID 元数据核验+期刊缩写展开 单元测试(离线确定性)"""
import importlib.util, os, sys, unittest

spec = importlib.util.spec_from_file_location(
    "vr", os.path.expanduser("~/ZCodeProject/skill/ch_pool_dev/trunk/scripts/verify_refs.py"))
vr = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(vr)
except SystemExit:
    pass


class TestJournalConsistent(unittest.TestCase):
    def test_opaque_jama(self):
        self.assertTrue(vr._journal_consistent("JAMA", "Journal of the American Medical Association"))

    def test_opaque_pnas(self):
        self.assertTrue(vr._journal_consistent("PNAS", "Proceedings of the National Academy of Sciences"))

    def test_opaque_bmj(self):
        self.assertTrue(vr._journal_consistent("BMJ", "British Medical Journal"))

    def test_nlm_abbrev(self):
        self.assertTrue(vr._journal_consistent("N Engl J Med", "New England Journal of Medicine"))

    def test_exact(self):
        self.assertTrue(vr._journal_consistent("Nature", "NATURE"))

    def test_mismatch(self):
        self.assertFalse(vr._journal_consistent("Nature", "New England Journal of Medicine"))

    def test_empty_skip(self):
        self.assertTrue(vr._journal_consistent("", "Nature"))
        self.assertTrue(vr._journal_consistent("Nature", ""))

    def test_cross_language_skip(self):
        self.assertTrue(vr._journal_consistent("中华内科杂志", "Chinese Journal of Internal Medicine"))


class TestJournalAcroExpand(unittest.TestCase):
    def test_expand(self):
        self.assertEqual(vr._journal_acro_expand("JAMA"),
                         "journal of the american medical association")
        self.assertEqual(vr._journal_acro_expand("Nature"), "Nature")

    def test_punct_insensitive(self):
        self.assertEqual(vr._journal_acro_expand("JAMA."), "journal of the american medical association")


if __name__ == "__main__":
    unittest.main()
