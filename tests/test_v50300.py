#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.3.0 测试：可验证性跃迁（F32 公开评测 runner + F33 持久研究档案）。

F32=留出集评测公开口径（内置金标：捕获/实锤/误伤/分布，可复现）；
F33=--research-profile 三键默认值注入（显式旗标优先，绝不改判定语义）。
全部 sealed（金标集 offline，零真网）。"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
sys.path.insert(0, os.path.join(SK, "tools"))
import verify_refs as vr  # noqa: E402
import run_eval  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


class F32_RunEval(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_golden_metrics(self):
        m = run_eval.run_eval()
        self.assertEqual(m["n"], 8)
        self.assertEqual(m["capture_rate"], 1.0)      # 3/3 预埋伪造非 verified
        self.assertEqual(m["strict_capture"], round(1 / 3, 4))  # #8 无标识符实锤
        self.assertEqual(m["false_kill_rate"], 0.0)   # 5 条干净零误伤
        self.assertEqual(m["distribution"], {"partial": 7, "invalid": 1})
        self.assertEqual(m["mode"], "offline 结构层")

    def test_custom_labeled_set(self):
        refs = [{"title": "A clean real reference about topic X", "url":
                 "https://example.org/a", "year": 2020},
                {"title": "Fabricated looking reference entry", "doi":
                 "10.9999/fake-doi-xx", "year": 2021}]
        doc = {"refs": refs, "expected": {"1": "clean", "2": "planted"}}
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "labeled.json")
            json.dump(doc, open(p, "w", encoding="utf-8"))
            m = run_eval.run_eval(p)
        self.assertEqual(m["n"], 2)
        self.assertIn("capture_rate", m)

    def test_md_render(self):
        m = run_eval.run_eval()
        md = run_eval.render_md(m)
        self.assertIn("capture_rate", md)
        self.assertIn("docs/benchmark.md", md)
        self.assertIn("复现", md)


class F33_ResearchProfile(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _args(self, **kw):
        import argparse
        a = argparse.Namespace(preset="", source_policy="", export=None,
                               research_profile="")
        for k, v in kw.items():
            setattr(a, k, v)
        return a

    def _write(self, td, doc):
        p = os.path.join(td, "p.json")
        json.dump(doc, open(p, "w", encoding="utf-8"))
        return p

    def test_defaults_applied(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, {"preset": "deep", "export": "bibtex"})
            a = self._args(research_profile=p)
            applied = vr.apply_research_profile(p, a)
            self.assertIn("preset=deep", applied)
            self.assertIn("export=bibtex", applied)
            self.assertEqual(a.preset, "deep")
            self.assertEqual(a.export, "bibtex")

    def test_explicit_flags_win(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, {"preset": "submission", "export": "ris"})
            a = self._args(preset="deep", export="csv", research_profile=p)
            applied = vr.apply_research_profile(p, a)
            self.assertEqual(applied, [])          # 全被显式旗标覆盖
            self.assertEqual(a.preset, "deep")     # 用户显式值不动
            self.assertEqual(a.export, "csv")

    def test_hard_fails(self):
        with tempfile.TemporaryDirectory() as td:
            a = self._args()
            self.assertIsNone(vr.apply_research_profile(
                self._write(td, {"preset": "bogus"}), a))
            self.assertIsNone(vr.apply_research_profile(
                self._write(td, {"source_policy": "nonsense"}), a))
            self.assertIsNone(vr.apply_research_profile(
                self._write(td, {"export": "pdf"}), a))
            self.assertIsNone(vr.apply_research_profile(
                os.path.join(td, "missing.json"), a))
            self.assertIsNone(vr.apply_research_profile(
                self._write(td, [1, 2]), a))

    def test_unknown_key_noted_not_failed(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, {"language": "zh", "export": "csv"})
            a = self._args(research_profile=p)
            applied = vr.apply_research_profile(p, a)
            self.assertIn("export=csv", applied)   # language 被注记忽略

    def test_cli_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._write(td, {"export": "csv"})
            out = os.path.join(td, "r.md")
            rc = vr.main_with_args(["--demo", "--offline", "--research-profile",
                                    p, "--out", out])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out.rsplit(".", 1)[0] + ".csv"))


class Docs(unittest.TestCase):
    def test_budget_and_anchors(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)
        self.assertIn("--research-profile", en)
        self.assertIn("--research-profile", zh)
        bm = open(os.path.join(SK, "docs", "benchmark.md"), encoding="utf-8").read()
        self.assertIn("capture_rate", bm)
        self.assertIn("100%（3/3）", bm)       # 真实实测数字在档
        self.assertIn("诚实边界", bm)
        self.assertTrue(os.path.exists(os.path.join(SK, "tools", "run_eval.py")))


if __name__ == "__main__":
    unittest.main()
