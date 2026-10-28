#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.0.0 测试：学界用法（S2 引文语境呈现）+ doctor 国内直连建议 + reference 导航。

学界用法=增强信号（ADR-0005 同款纪律）：usage_line/报告区/工作台书目行三处
共用一个构造器；无数据整段不渲染（老输出逐字节不变，金标 0 drift）。
全部 sealed（doctor 探针 patch urllib.request.urlopen，零真网）。"""
import io
import json
import os
import sys
import unittest
import unittest.mock
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402

CC = {"cited_by": 12, "coverage": 1.0,
      "samples": [
          {"context": "This landmark study established the method we use",
           "intents": ["methodology", "methodology"], "influential": True,
           "citing_title": "A follow up review"},
          {"context": "Prior work showed the opposite trend",
           "intents": ["background"], "influential": False,
           "citing_title": "Another paper"}]}


def _row(idx, cc=None, verdict="verified"):
    return {"index": idx, "title": f"paper {idx} title here", "url": "", "doi": "",
            "pmid": "", "arxiv": "", "source": "J", "year": 2024, "tier": "official",
            "semantic": "", "verdict": verdict, "http_status": 200,
            "note": "ok", "needs_human_check": False, "checks": {},
            "citation_contexts": cc}


class F26_UsageLine(unittest.TestCase):
    def test_distribution_influential_quote(self):
        ul = vr.usage_line(CC)
        self.assertIn("方法学×2", ul)
        self.assertIn("背景×1", ul)
        self.assertIn("高影响引用 1", ul)
        self.assertIn("例引「This landmark study", ul)
        self.assertIn("——A follow up review", ul)

    def test_unknown_intent_passthrough(self):
        cc = {"samples": [{"context": "x", "intents": ["dataset"],
                           "influential": False, "citing_title": "y"}]}
        self.assertIn("dataset×1", vr.usage_line(cc))

    def test_empty_shapes_silent(self):
        for bad in (None, {}, [], {"samples": []}, {"cited_by": 3}):
            self.assertEqual(vr.usage_line(bad), "")

    def test_long_quote_clipped(self):
        cc = {"samples": [{"context": "x" * 400, "intents": ["result"],
                           "influential": False, "citing_title": "t" * 80}]}
        ul = vr.usage_line(cc)
        self.assertLessEqual(len(ul), 220)


class F26_RenderAndKit(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_md_section_renders_with_data(self):
        md = vr.render_md([_row(1, CC)], False)
        self.assertIn("## 学界用法（引文语境）", md)
        self.assertIn("| 1 | 12 |", md)
        self.assertIn("绝不改变判定", md)

    def test_md_section_absent_without_data(self):
        md = vr.render_md([_row(1), _row(2, {"cited_by": 5})], False)
        self.assertNotIn("学界用法", md)  # 无 samples 整段不渲染

    def test_kit_bibliography_line(self):
        rows = [_row(1, CC)]
        kit = vr.build_review_kit(rows, [], topic="t")
        self.assertIn("- 学界用法（≤3 条抽样）：用法分布 方法学×2", kit)
        kit2 = vr.build_review_kit([_row(1)], [], topic="t")
        self.assertNotIn("学界用法", kit2)


class _Resp:
    """探针以 with urlopen(...) as resp 使用——桩需上下文管理器。"""
    def __init__(self, code=200):
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class F26_DoctorDomesticAdvisory(unittest.TestCase):
    def _run(self, urlopen_mock):
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
             unittest.mock.patch("urllib.request.urlopen", urlopen_mock):
            rc = vr.run_doctor(net=True, timeout=5.0)
        return rc, buf.getvalue()

    def test_all_pass_advisory(self):
        rc, out = self._run(unittest.mock.MagicMock(return_value=_Resp(200)))
        self.assertIn("── 国内直连建议 ──", out)
        self.assertIn("全部注册库直连可达", out)
        self.assertEqual(rc, 0)

    def test_partial_pass_advisory(self):
        calls = {"n": 0}

        def some_fail(req, timeout=None, **kw):
            calls["n"] += 1
            if calls["n"] > 2:  # 后 5 个探针全挂
                raise Exception("timeout")
            return _Resp(200)
        rc, out = self._run(some_fail)
        self.assertIn("源直连可用", out)
        self.assertIn("--proxy", out)

    def test_all_fail_advisory(self):
        rc, out = self._run(unittest.mock.MagicMock(
            side_effect=Exception("unreachable")))
        self.assertIn("直连可用源不足", out)

    def test_rate_limited_counts_as_warn_not_pass(self):
        def limited(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden",
                                         None, io.BytesIO(b""))
        _, out = self._run(limited)
        self.assertIn("直连可用源不足", out)  # 403≠直连可用（需 key/限流）


class F26_Docs(unittest.TestCase):
    def test_reference_nav_headers(self):
        for f, kw in (("faq.md", "30 秒导航"),
                      ("verification-details.md", "30 秒导航"),
                      ("anti-patterns.md", "30 秒导航"),
                      ("medical-mode.md", "30 秒导航"),
                      ("out-of-scope.md", "30 秒导航")):
            head = open(os.path.join(SK, "references", f),
                        encoding="utf-8").read()[:800]
            self.assertIn(kw, head, f)
        # 关键词锁不受头部插入影响
        oos = open(os.path.join(SK, "references", "out-of-scope.md"),
                   encoding="utf-8").read()
        self.assertIn("诚实边界", oos)

    def test_skill_capability_row_and_budget(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("Scholarly usage & open access", en)  # v5.6 行题扩展
        self.assertIn("学界用法与开放获取", zh)  # v5.6 行题扩展
        self.assertLessEqual(len(en.splitlines()), 222, "EN 行预算")
        self.assertLessEqual(len(zh.splitlines()), 202, "ZH 行预算")

    def test_faq_doctor_entry(self):
        faq = open(os.path.join(SK, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("国内直连建议", faq)


if __name__ == "__main__":
    unittest.main()
