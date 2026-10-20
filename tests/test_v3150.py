#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.15.0 测试:文字系统守卫(F1,俄/希腊/日韩防误判)+耗时表/多语言边界文档(F2/F4)
+子标题(F3)+英文市场激活(F5)。"""
import importlib.util
import io
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


class TestScriptFamily(unittest.TestCase):
    def test_families(self):
        cases = {
            "Гидрогель для доставки": "cyrillic",
            "Νέες μέθοδοι φυσικής": "greek",
            "深層学習による画像認識": "kana",
            "氢键复合物中键长变化": "han",
            "Deep Residual Learning": "latin",
            "Über die Berechnung": "latin",
            "한국어 논문 제목": "hangul",
            "123 --- !!!": "none",
        }
        for s, want in cases.items():
            self.assertEqual(vr._script_family(s), want, s)

    def test_pure(self):
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            vr._script_family("anything")
            mu.assert_not_called()


class TestCrossScriptGuard(unittest.TestCase):
    META_EN = {"title": ["Deep Residual Learning for Image Recognition"],
               "issued": {"date-parts": [[2016]]}}

    def _match(self, claimed):
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(self.META_EN).encode())
            mu.return_value.code = 200
            return vr.doi_metadata_match("10.7/t", claimed, 2016, timeout=3.0)

    def test_russian_claim_not_invalid(self):
        adj, note, _, _ = self._match("Глубокое остаточное обучение образов")
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言", note)

    def test_greek_claim_not_invalid(self):
        adj, _, _, _ = self._match("Βαθιά υπολειμματική μάθηση εικόνων")
        self.assertEqual(adj, "partial")

    def test_same_family_low_sim_still_invalid(self):
        adj, _, _, _ = self._match("Completely Different English Title Here")
        self.assertEqual(adj, "invalid")  # 守卫不误扩:同族低 sim 仍判死

    def test_japanese_vs_chinese_distinct(self):
        meta = {"title": ["深度学习在医学影像中的应用研究"],
                "issued": {"date-parts": [[2020]]}}
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(meta).encode())
            mu.return_value.code = 200
            adj, _, _, _ = vr.doi_metadata_match(
                "10.9/jp", "深層学習による医療画像認識に関する研究", 2020, timeout=3.0)
        self.assertEqual(adj, "partial")

    def test_journal_guard_cross_script(self):
        # 期刊名守卫同规:俄文声称刊名 vs 拉丁登记刊名 → 期刊不符注记不出现
        meta = {"title": ["Deep Residual Learning for Image Recognition"],
                "issued": {"date-parts": [[2016]]},
                "container-title": ["Totally Different Journal"]}
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(meta).encode())
            mu.return_value.code = 200
            adj, note, _, _ = vr.doi_metadata_match(
                "10.7/j", "Глубокое остаточное обучение образов",
                2016, timeout=3.0, source="Журнал физики")
        self.assertNotIn("期刊名不符", note)  # 跨族刊名不判不符


class TestDocsAndMeta(unittest.TestCase):
    def test_timing_table(self):
        v = open(os.path.join(SK, "references", "verification-details.md"),
                 encoding="utf-8").read()
        self.assertIn("批次耗时预期", v)
        self.assertIn("--workers 4", v)

    def test_multilingual_boundary(self):
        v = open(os.path.join(SK, "references", "verification-details.md"),
                 encoding="utf-8").read()
        self.assertIn("多语言处理边界", v)
        self.assertIn("文字系统族", v)

    def test_subheads_in_skill(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("#### Mechanical layer (the script)", en)
        self.assertIn("#### Semantic layer (the model)", en)
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("#### 机械层（脚本负责）", zh)
        self.assertIn("#### 语义层（模型负责）", zh)

    def test_install_section_in_readme(self):
        r = open(os.path.join(SK, "README.md"), encoding="utf-8").read()
        self.assertIn("npx skills add docsor1212/cite-holmes", r)

    def test_zh_desc_keywords(self):
        z = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("查文献", z)
        self.assertIn("文献综述", z)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "4.6.0")
        self.assertIn("version: 4.6.0",
                      open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
