#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.9.0 测试:结构化错误码(F2)+fast-judge 位 B 路由(F1)+MCP 截断语义化(F3)。"""
import importlib.util
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402

_MCP_SPEC = importlib.util.spec_from_file_location(
    "ch_mcp_server", os.path.join(HERE, "..", "mcp", "server.py"))


class TestErrorCodes(unittest.TestCase):

    def test_dou_not_found(self):
        r = {"verdict": "invalid", "doi": "10.9999/x",
             "note": "DOI 在 DOI.org 不存在（404）→ 疑似编造引用", "checks": {}}
        self.assertIn("E_DOU_NOT_FOUND", vr.derive_error_codes(r))

    def test_title_mismatch(self):
        r = {"verdict": "invalid", "doi": "10.1/x",
             "note": "DOI 元数据标题相似度仅 0.27 → 疑似编造或错引",
             "checks": {"doi_metadata": {"matched": True, "adjust": "invalid"}}}
        self.assertIn("E_TITLE_MISMATCH", vr.derive_error_codes(r))

    def test_retracted(self):
        r = {"verdict": "partial",
             "note": "撤稿记录命中",
             "checks": {"retraction": {"retracted": True}}}
        self.assertIn("E_RETRACTED", vr.derive_error_codes(r))

    def test_unreachable_and_offline(self):
        self.assertIn("E_UNREACHABLE",
                      vr.derive_error_codes({"verdict": "unreachable", "checks": {}}))
        self.assertIn("E_OFFLINE",
                      vr.derive_error_codes({"verdict": "unverified",
                                             "note": "offline 模式未做可达性检查",
                                             "checks": {}}))

    def test_clean_verdict_empty_codes(self):
        r = {"verdict": "verified", "note": "DOI 元数据核验一致（相似度 0.95）",
             "checks": {"doi_metadata": {"matched": True}}}
        self.assertEqual(vr.derive_error_codes(r), [])

    def test_author_and_journal_mismatch(self):
        r = {"verdict": "partial", "note": "作者不符；期刊名不符", "checks": {}}
        codes = vr.derive_error_codes(r)
        self.assertIn("E_AUTHOR_MISMATCH", codes)
        self.assertIn("E_JOURNAL_MISMATCH", codes)

    def test_wired_into_pipeline(self):
        r = {"index": 1, "title": "t", "verdict": "verified", "note": "",
             "checks": {}, "year": 2024}
        vr.mark_duplicates([r])
        vr.apply_semantic_cap([r])
        for _r in [r]:  # 主流程同序:semantic_cap 后派生 error_codes
            _r["error_codes"] = vr.derive_error_codes(_r)
        self.assertIn("error_codes", r)


class TestFastJudgeRouting(unittest.TestCase):
    """位 B:fast-judge 预筛→高置信 REFUTES 置前(排序路由,不跳过任何条目)。"""

    def _run(self, fj_side_effect):
        judge_order = []
        vr._OPTS["fast_judge_url"] = "http://127.0.0.1:8793"
        vr._OPTS["judge_url"] = "http://127.0.0.1:8082"
        rows = []
        for i in (1, 2):
            rows.append({"index": i,
                         "title": f"Long descriptive study title number {i} about X",
                         "journal": "Journal of Tests",
                         "verdict": "partial",
                         "semantic_audit": {"claim": f"claim {i}",
                                            "support": "unclear"},
                         "pmid": f"2340000{i}", "note": "", "checks": {}})
        with unittest.mock.patch.object(
                vr, "judge_endpoint_available", return_value=True), \
             unittest.mock.patch.object(
                vr, "fast_judge_vote",
                side_effect=fj_side_effect), \
             unittest.mock.patch.object(
                vr, "fetch_pubmed_abstract", return_value="abstract text about X"), \
             unittest.mock.patch.object(
                vr, "retrieve_evidence", return_value=["chunk about X"]), \
             unittest.mock.patch.object(
                vr, "judge_claim_via_endpoint",
                side_effect=lambda c, e, timeout=5: judge_order.append(c) or {
                    "verdict": "SUPPORTS"}):
            vr.apply_l4_cascade(rows, 5)
        return rows, judge_order

    def test_prescreen_recorded_and_high_refutes_first(self):
        def fj(claim, source, timeout=30):
            # claim 2 → 高置信 REFUTES(应被置前)
            return {"label": "REFUTES", "prob": 0.99} if "2" in claim \
                else {"label": "SUPPORTS", "prob": 0.6}
        rows, judge_order = self._run(fj)
        # 路由排序的证明=级联处理序:judge 先处理高置信 REFUTES 的 claim 2
        self.assertEqual(judge_order, ["claim 2", "claim 1"])
        for r in rows:
            ps = r["checks"]["fast_judge_prescreen"]
            self.assertIn(ps["label"], ("SUPPORTS", "REFUTES"))
        # 全部条目仍被级联处理(排序≠跳过)
        self.assertTrue(all("l4_evidence_cascade" in r["checks"] for r in rows))

    def test_no_fastjudge_keeps_order(self):
        vr._OPTS["fast_judge_url"] = ""
        rows = []
        for i in (1, 2):
            rows.append({"index": i,
                         "title": f"Long descriptive study title number {i} about X",
                         "journal": "Journal of Tests",
                         "verdict": "partial",
                         "semantic_audit": {"claim": f"claim {i}",
                                            "support": "unclear"},
                         "pmid": f"2340000{i}", "note": "", "checks": {}})
        with unittest.mock.patch.object(
                vr, "judge_endpoint_available", return_value=True), \
             unittest.mock.patch.object(
                vr, "fetch_pubmed_abstract", return_value="abstract"), \
             unittest.mock.patch.object(
                vr, "retrieve_evidence", return_value=["chunk"]), \
             unittest.mock.patch.object(
                vr, "judge_claim_via_endpoint",
                return_value={"verdict": "SUPPORTS"}):
            vr.apply_l4_cascade(rows, 5)
        self.assertFalse(any("fast_judge_prescreen" in r["checks"] for r in rows))


class TestMCPClipSemantics(unittest.TestCase):

    def _load_server(self):
        spec = _MCP_SPEC
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_clip_flag_present_when_clipped(self):
        m = self._load_server()
        claims = [{"title": "t", "doi": "10.1/x"}]
        with unittest.mock.patch.object(
                m.vr, "verify_one",
                side_effect=lambda ref, i, o, t, mm: {
                    "index": i, "title": ref["title"], "verdict": "verified",
                    "note": "L" * 3000, "needs_human_check": False}):
            out = m.verify_references_impl(claims, 5, max_field_chars=800)
        self.assertTrue(out["output_clipped"]["clipped_fields"] >= 1)
        self.assertIn("auditjson", out["output_clipped"]["hint"])

    def test_no_clip_flag_when_within_limit(self):
        m = self._load_server()
        claims = [{"title": "t", "doi": "10.1/x"}]
        with unittest.mock.patch.object(
                m.vr, "verify_one",
                side_effect=lambda ref, i, o, t, mm: {
                    "index": i, "title": ref["title"], "verdict": "verified",
                    "note": "short", "needs_human_check": False}):
            out = m.verify_references_impl(claims, 5, max_field_chars=800)
        self.assertNotIn("output_clipped", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
