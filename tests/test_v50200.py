#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.2.0 测试：深度研究工作流四件（Google Deep Research 借鉴）。

F28 计划工件（校验+渲染+独立模式）/F29 DEEP 档（单调抬升）/F30 信源政策
（discover 硬过滤+核验注记，绝不改判定）/F31 研究底稿（append-only）。
全部 sealed（discover 管道 patch _urlopen_retry，零真网）。"""
import io
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


class F28_PlanArtifact(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _plan(self, **kw):
        d = {"scope": "X 的现状", "timeframe": "2020-", "audience": "研究生",
             "format": "md", "subquestions": ["A 全景", "B 争议"],
             "budget_searches": 12}
        d.update(kw)
        return d

    def test_render_complete_no_warns(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "plan.md")
            warns = vr.render_plan_artifact(self._plan(), p)
            self.assertEqual(warns, [])
            s = open(p, encoding="utf-8").read()
            self.assertIn("- [ ] Q1. A 全景", s)
            self.assertIn("预算上限：12", s)
            self.assertIn("CALIBRATE 四要素", s)
            self.assertNotIn("⚠️ 未填写", s)

    def test_missing_calibrate_warns_not_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "plan.md")
            warns = vr.render_plan_artifact(
                {"subquestions": ["only"], "budget_searches": 5}, p)
            self.assertEqual(len(warns), 4)
            self.assertIn("⚠️ 未填写", open(p, encoding="utf-8").read())

    def test_hard_fails_return_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "plan.md")
            self.assertIsNone(vr.render_plan_artifact(
                {"budget_searches": 5}, p))                # subquestions 缺
            self.assertIsNone(vr.render_plan_artifact(
                {"subquestions": ["x"]}, p))               # budget 缺
            self.assertIsNone(vr.render_plan_artifact(
                {"subquestions": ["x"], "budget_searches": 0}, p))
            self.assertIsNone(vr.render_plan_artifact(["not", "dict"], p))
            # 审计 P2-1/P2-2 回归锁：巨整 budget / 不可写 plan-out 友好失败不裸崩
            self.assertIsNone(vr.render_plan_artifact(
                {"subquestions": ["x"], "budget_searches": 10 ** 5000}, p))
            self.assertIsNone(vr.render_plan_artifact(
                {"subquestions": ["x"], "budget_searches": 8}, td))  # 目录=不可写

    def test_help_syntax_matches_parser(self):
        # 审计 P1-1 回归锁：文档示例必须用解析器真语法（竖线分域）
        src = open(os.path.join(SK, "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn("allow-domain=a.org|b.org", src)
        self.assertNotIn("allow-domain=a.org,b.org", src)

    def test_md_injection_escaped(self):
        # 审计 P2-3：子问题含管道/换行不破工件结构
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "plan.md")
            vr.render_plan_artifact(
                {"subquestions": ["a | b\nc\n| d"], "budget_searches": 5}, p)
            body = open(p, encoding="utf-8").read()
            self.assertNotIn("a | b\nc", body)

    def test_cli_standalone_mode(self):
        with tempfile.TemporaryDirectory() as td:
            pj = os.path.join(td, "plan.json")
            json.dump(self._plan(), open(pj, "w", encoding="utf-8"))
            out = os.path.join(td, "plan.md")
            rc = vr.main_with_args(["--plan", pj, "--plan-out", out])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out))
            # 硬失败 exit 2
            json.dump({"subquestions": ["x"]}, open(pj, "w", encoding="utf-8"))
            self.assertEqual(vr.main_with_args(["--plan", pj, "--plan-out", out]), 2)


class F29_DeepPreset(unittest.TestCase):
    def test_cli_deep_banner_and_success(self):
        import contextlib
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = vr.main_with_args(["--preset", "deep", "--demo", "--offline",
                                        "--out", os.path.join(td, "r.md")])
            self.assertEqual(rc, 0)
            self.assertIn("[preset] deep", buf.getvalue())


class F30_SourcePolicy(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_parse(self):
        self.assertEqual(vr._parse_source_policy("journal_only,deny-domain=x.com|y.org"),
                         {"journal_only": True, "allow": [], "deny": ["x.com", "y.org"]})
        for bad in ("", "bogus", "deny-domain=", "allow-domain"):
            self.assertIsNone(vr._parse_source_policy(bad), bad)

    def test_apply_never_changes_verdict(self):
        rows = [{"url": "https://x.com/a", "note": "", "needs_human_check": False,
                 "checks": {}, "verdict": "verified", "tier": "blog"},
                {"url": "https://ok.org/b", "note": "", "needs_human_check": False,
                 "checks": {}, "verdict": "verified", "tier": "journal"}]
        n = vr.apply_source_policy(rows, vr._parse_source_policy("deny-domain=x.com"))
        self.assertEqual(n, 1)
        self.assertTrue(rows[0]["needs_human_check"])
        self.assertEqual(rows[0]["verdict"], "verified")     # 判定不变（铁律）
        self.assertFalse(rows[1]["needs_human_check"])
        self.assertIn("deny-domain", rows[0]["checks"]["source_policy"]["violation"])

    def test_allow_and_journal_only(self):
        rows = [{"url": "https://other.org/z", "note": "", "needs_human_check": False,
                 "checks": {}, "verdict": "partial", "tier": "blog"},
                {"url": "https://ok.org/y", "note": "", "needs_human_check": False,
                 "checks": {}, "verdict": "partial", "tier": "journal"}]
        self.assertEqual(vr.apply_source_policy(
            rows, vr._parse_source_policy("allow-domain=ok.org")), 1)
        self.assertIn("allow-domain", rows[0]["checks"]["source_policy"]["violation"])
        rows2 = [{"url": "https://blog.x.org/p", "note": "", "needs_human_check": False,
                  "checks": {}, "verdict": "partial", "tier": "blog"}]
        self.assertEqual(vr.apply_source_policy(
            rows2, vr._parse_source_policy("journal_only")), 1)
        self.assertIn("journal_only", rows2[0]["checks"]["source_policy"]["violation"])

    def test_discover_journal_only_filter(self):
        oa = {"results": [
            {"display_name": "A journal typed article title here long",
             "publication_year": 2023, "doi": "10.5555/j1",
             "primary_location": {"source": {"display_name": "J", "type": "journal"}},
             "cited_by_count": 5},
            {"display_name": "A repository typed preprint title long",
             "publication_year": 2023, "doi": "10.5555/r1",
             "primary_location": {"source": {"display_name": "bioRxiv",
                                             "type": "repository"}},
             "cited_by_count": 2}]}
        pm = {"esearchresult": {"idlist": []}}

        def fake(req, timeout):
            u = getattr(req, "full_url", str(req))
            if "api.openalex.org" in u:
                return io.BytesIO(json.dumps(oa).encode())
            if "esearch" in u:
                return io.BytesIO(json.dumps(pm).encode())
            raise AssertionError("意外外呼 " + u)
        with unittest.mock.patch.object(vr, "_urlopen_retry", side_effect=fake), \
             unittest.mock.patch.object(vr, "_cb_open", return_value=False), \
             unittest.mock.patch.object(vr, "_ncbi_rate_wait"), \
             unittest.mock.patch.object(vr, "_cb_record"):
            refs, notes = vr.discover_refs("some topic", 5, 5.0,
                                           policy=vr._parse_source_policy("journal_only"))
        self.assertEqual([r["doi"] for r in refs], ["10.5555/j1"])
        self.assertTrue(any("journal_only" in n for n in notes))
        # 无政策：两条都保留
        with unittest.mock.patch.object(vr, "_urlopen_retry", side_effect=fake), \
             unittest.mock.patch.object(vr, "_cb_open", return_value=False), \
             unittest.mock.patch.object(vr, "_ncbi_rate_wait"), \
             unittest.mock.patch.object(vr, "_cb_record"):
            refs2, _ = vr.discover_refs("some topic", 5, 5.0, policy=None)
        self.assertEqual(len(refs2), 2)

    def test_cli_invalid_policy_exit2(self):
        self.assertEqual(vr.main_with_args(
            ["--source-policy", "nonsense", "--demo", "--offline",
             "--out", "/tmp/x.md"]), 2)


class F31_Trace(unittest.TestCase):
    def test_append_only_two_rounds(self):
        with tempfile.TemporaryDirectory() as td:
            t = os.path.join(td, "trace.md")
            vr._trace_append(t, "discover", {"topic": "x", "命中": "5 条"})
            vr._trace_append(t, "verify", {"条数": 5, "CiteScore": "80/100 B"})
            s = open(t, encoding="utf-8").read()
            self.assertEqual(s.count("## "), 2)
            self.assertIn("· discover", s)
            self.assertIn("· verify", s)
            self.assertIn("topic: x", s)

    def test_write_failure_silent(self):
        vr._trace_append("/nonexistent-dir-xyz/trace.md", "x", {})  # 不抛即过

    def test_cli_trace_writes_verify_round(self):
        with tempfile.TemporaryDirectory() as td:
            t = os.path.join(td, "t.md")
            rc = vr.main_with_args(["--demo", "--offline", "--trace", t,
                                    "--out", os.path.join(td, "r.md")])
            self.assertEqual(rc, 0)
            self.assertIn("· verify", open(t, encoding="utf-8").read())


class Docs(unittest.TestCase):
    def test_skill_rows_and_budget(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("Deep-research controls", en)
        self.assertIn("深度研究控制", zh)
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)
        vd = open(os.path.join(SK, "references", "verification-details.md"),
                  encoding="utf-8").read()
        self.assertIn("--source-policy", vd)
        self.assertIn("append-only", vd)
        faq = open(os.path.join(SK, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("研究计划/信源政策/研究底稿", faq)


if __name__ == "__main__":
    unittest.main()
