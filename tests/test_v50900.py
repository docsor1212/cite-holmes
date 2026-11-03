#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.9.0 测试：引文语境分歧信号（F48）+ 基准与 ADR 文档真相化（F49）。

F48=context_signal 启发式（S2 intents 不标注争议性，本地对比/质疑句式扫描，
命中 ≥50% 抽样才提示；纯呈现层——绝不改判定、不挂复核旗，宪法同 v5.0
usage_line）+md/kit/HTML 三处渲染接线；F49=金标集 #7 夹具描述纠偏（编造
URL 非假 arXiv——与 demo_refs.json 实际形态逐字对齐）+ADR tests/ 位置
澄清+发布链 sha 门禁披露。全部 sealed（纯函数/桩，零网络）。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


def _ctx(*contexts):
    return {"cited_by": len(contexts), "coverage": 1.0,
            "samples": [{"context": c, "intents": [], "influential": False,
                         "citing_title": f"T{i}"} for i, c in
                        enumerate(contexts)]}


class F48_ContextSignal(unittest.TestCase):
    def test_empty_and_malformed_return_blank(self):
        self.assertEqual(vr.context_signal({}), "")
        self.assertEqual(vr.context_signal(None), "")
        self.assertEqual(vr.context_signal("x"), "")
        self.assertEqual(vr.context_signal({"samples": []}), "")
        self.assertEqual(vr.context_signal({"samples": "no"}), "")

    def test_below_threshold_blank(self):
        # 0/3 与 1/3（学术写作转折常态）不报——避免把常规转折渲染成争议
        self.assertEqual(vr.context_signal(
            _ctx("we adopt their protocol",
                 "solid baseline for our study",
                 "extends the framework")), "")
        self.assertEqual(vr.context_signal(
            _ctx("However, results vary.",
                 "we adopt it",
                 "a useful reference")), "")

    def test_at_threshold_hits(self):
        out = vr.context_signal(_ctx("However, the method fails to generalize.",
                                     "In contrast, their estimates are inconsistent.",
                                     "we adopt their protocol"))
        self.assertIn("分歧信号 2/3", out)
        self.assertIn("人工复核", out)  # advisory 指引字样在场

    def test_unanimous_single_and_full(self):
        self.assertIn("分歧信号 1/1", vr.context_signal(
            _ctx("然而该结论与观察并不一致。")))
        self.assertIn("分歧信号 3/3", vr.context_signal(
            _ctx("contradicts prior estimates", "refutes the claim",
                 "与此相反")))

    def test_zh_patterns_covered(self):
        for kw in ("然而", "质疑", "反驳", "并未", "不一致"):
            self.assertTrue(vr._CONTRAST_RE.search(kw), kw)

    def test_audit_false_positive_words_rejected(self):
        # 对抗审计 P3 实测误报词：赞同/常态用法不得触发
        for w in ("not unlike previous work", "unlikely to generalize",
                  "indisputable evidence", "irrefutable proof",
                  "a questionnaire was sent", "不但高效而且稳定",
                  "极具挑战性"):
            # 「相反数」类数学词审计判定为可接受误报（引用语境近乎不出现），不设窄补丁
            self.assertIsNone(vr._CONTRAST_RE.search(w), w)

    def test_audit_missed_pattern_covered(self):
        # 对抗审计 P3 漏报词：failed to <verb> 类须覆盖
        self.assertIsNotNone(vr._CONTRAST_RE.search(
            "their model failed to generalize beyond the benchmark"))

    def test_signal_never_touches_verdict_fields(self):
        # 纯呈现层宪法：context_signal 只读 samples，不改判定/旗标
        cc = _ctx("However, x.", "In contrast, y.")
        before = dict(cc)
        vr.context_signal(cc)
        self.assertEqual(cc, before)


def _row(cc, idx=1):
    """render_md 最小契约条目（tier/http_status/note/needs_human 等表格键全带）。"""
    return {"index": idx, "verdict": "verified", "title": f"T{idx}",
            "note": "", "tier": "", "http_status": 200,
            "needs_human_check": False,
            "citation_contexts": cc}


class F48_Rendering(unittest.TestCase):
    R = [_row(_ctx("However, the estimates are inconsistent.",
                   "In contrast, we find the opposite."))]

    def test_md_renders_signal_section(self):
        out = vr.render_md(self.R, offline=True)
        self.assertIn("分歧信号", out)
        self.assertIn("advisory", out)
        self.assertIn("#1", out)

    def test_md_no_signal_omits_section(self):
        r = [_row(_ctx("builds on prior work", "extends the framework"))]
        self.assertNotIn("分歧信号", vr.render_md(r, offline=True))

    def test_kit_bibliography_signal_line(self):
        kit = vr.build_review_kit([dict(self.R[0])], topic="t")
        self.assertIn("语境信号（advisory）", kit)

    def test_html_signal_in_cell(self):
        r = dict(self.R[0])
        html = vr.render_html([r], offline=True)
        self.assertIn("分歧信号", html)

    def test_signal_without_usage_line_still_renders(self):
        # 审计 P2 回归锁：usage_line 空（首样本 context 为空串）而信号非空，
        # md/html 不得静默丢失（kit 本就无此门）
        cc = {"cited_by": 2, "coverage": 1.0, "samples": [
            {"context": "", "intents": [], "influential": False,
             "citing_title": "T0"},
            {"context": "However, the estimates are inconsistent.",
             "intents": [], "influential": False, "citing_title": "T1"}]}
        self.assertEqual(vr.usage_line(cc), "")
        self.assertTrue(vr.context_signal(cc))
        r = _row(cc)
        self.assertIn("分歧信号", vr.render_md([r], offline=True))
        self.assertIn("分歧信号", vr.render_html([r], offline=True))
    def test_signal_needs_no_network(self):
        # 密封：context_signal 是纯函数——构造即算，无任何 urlopen 依赖
        self.assertIsInstance(vr.context_signal(_ctx("However.")), str)


class F49_DocTruth(unittest.TestCase):
    def _read(self, *parts):
        with open(os.path.join(SK, *parts), encoding="utf-8") as f:
            return f.read()

    def test_benchmark_fixture7_describes_fabricated_url(self):
        bm = self._read("docs", "benchmark.md")
        self.assertIn("编造 URL", bm)
        self.assertNotIn("#7=假 arXiv", bm)

    def test_run_eval_fixture_comment_aligned(self):
        src = self._read("tools", "run_eval.py")
        self.assertIn("编造 URL", src)
        self.assertNotIn("#7=假 arXiv", src)

    def test_capability_rows_keep_fake_arxiv_ability(self):
        # 能力描述（真抓假 arXiv ID）与夹具描述（#7）必须区分——能力行保留
        from _mocks import engine_full_text
        eng = engine_full_text()
        self.assertIn("假 arXiv ID（官方 API 查无）", eng)

    def test_adr_clarify_tests_location(self):
        adr1 = self._read("docs", "adr", "0001-verdict-contract.md")
        adr9 = self._read("docs", "adr", "0009-dual-engine-copy-with-sha-gate.md")
        for doc in (adr1, adr9):
            self.assertIn("GitHub 仓库", doc)
            self.assertIn("不随 skill 包分发", doc)

    def test_adr9_publish_chain_sha_gates_disclosed(self):
        adr9 = self._read("docs", "adr", "0009-dual-engine-copy-with-sha-gate.md")
        self.assertIn("MCP sha 只读门", adr9)
        self.assertIn("打包后洁净复验", adr9)


if __name__ == "__main__":
    unittest.main()
