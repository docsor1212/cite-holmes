#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cite-holmes v1.11.0 回归：arXiv 第二源 fallback 链（判定确定性保卫）
+ 语义层工作底稿结构化（semantic_audit）+ 投稿前结论 2026-05/ICML 话术
+ agentskills_check 分发准备模式。mock 模式沿用 test_v110 的 _seq。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


class _Resp:
    """urlopen 替身的最小响应对象（with 上下文 + read）。"""

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


class TestV111(unittest.TestCase):
    """v1.11.0 新功能测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ch_v111_")
        vr._net_reset()
        vr._ARXIV_LAST[0] = 0.0

    def tearDown(self):
        vr._net_reset()

    # ---------- 版本 ----------

    def test_version_bumped_111(self):
        self.assertEqual(vr.VERSION, "1.13.0")

    # ---------- P0-1: arXiv fallback 链 ----------

    @staticmethod
    def _landing_html(title):
        return f"<html><head><title>[2607.22693] {title}</title></head><body>x</body></html>"

    def _patch_sleep(self):
        # 退避 sleep(5)+rate_wait(3s) 不真睡——测试必须快
        enter = unittest.mock.patch.object(vr.time, "sleep", lambda s: None)
        return enter

    def test_arxiv_api_406_fallback_landing_match(self):
        # API 两次尝试均 406 → 着陆页 200 且标题一致 → 放行 verified 档 + note 注明
        calls = {"urls": []}

        def fake_urlopen(req, timeout=None):
            calls["urls"].append(req.full_url)
            if "export.arxiv.org" in req.full_url:
                raise vr.urllib.error.HTTPError(req.full_url, 406, "NA", None, None)
            return _Resp(self._landing_html(
                "Detecting Hallucinated and Suspicious Citations").encode())

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Detecting Hallucinated and Suspicious Citations",
                2026, 5.0)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertIn("着陆页", note)
        self.assertIn("2607.22693", calls["urls"][-1])  # 确实回退到了着陆页
        self.assertNotIn("跳过内容核验", note)  # 旧静默文案必须消失

    def test_arxiv_fallback_landing_partial_similarity(self):
        # 着陆页标题相似度 0.50-0.82 → partial（人工复核），与 API 路径阈值一致
        def fake_urlopen(req, timeout=None):
            if "export.arxiv.org" in req.full_url:
                raise vr.urllib.error.HTTPError(req.full_url, 406, "NA", None, None)
            return _Resp(self._landing_html(
                "Detecting and Preventing Suspicious Citations in Academic Publishing").encode())

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Detecting Hallucinated and Suspicious Citations",
                2026, 5.0)
        self.assertEqual(adj, "partial")
        self.assertTrue(matched)
        self.assertIn("相似度", note)

    def test_arxiv_fallback_landing_mismatch_invalid(self):
        # 着陆页标题相似度 <0.50 → invalid（错引），防「真 ID 假论文」借 API 故障溜过
        def fake_urlopen(req, timeout=None):
            if "export.arxiv.org" in req.full_url:
                raise vr.urllib.error.HTTPError(req.full_url, 406, "NA", None, None)
            return _Resp(self._landing_html(
                "Completely Unrelated Paper About Quantum Cooking Recipes").encode())

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Detecting Hallucinated and Suspicious Citations",
                2026, 5.0)
        self.assertEqual(adj, "invalid")
        self.assertIn("错引", note)

    def test_arxiv_fallback_landing_404_invalid(self):
        # 着陆页 404 = 官方库查无 → invalid（不回退成 unreachable）
        def fake_urlopen(req, timeout=None):
            if "export.arxiv.org" in req.full_url:
                raise vr.urllib.error.HTTPError(req.full_url, 406, "NA", None, None)
            raise vr.urllib.error.HTTPError(req.full_url, 404, "NF", None, None)

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Any Title", 2026, 5.0)
        self.assertEqual(adj, "invalid")
        self.assertFalse(matched)
        self.assertIn("404", note)

    def test_arxiv_fallback_both_fail_honest_note(self):
        # API 失败 + 着陆页传输失败（断网/降级）→ 维持可达性路径（matched=False），
        # 但 note 必须明示「核验未完成」——不静默
        def fake_urlopen(req, timeout=None):
            if "export.arxiv.org" in req.full_url:
                raise vr.urllib.error.HTTPError(req.full_url, 406, "NA", None, None)
            raise vr.urllib.error.URLError("connection refused")

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Any Title", 2026, 5.0)
        self.assertEqual(adj, "")
        self.assertFalse(matched)
        self.assertIn("未完成", note)

    def test_arxiv_api_success_no_fallback(self):
        # API 正常时不得触发 fallback（note 不含「着陆页」）
        atom = ("""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Some Real Paper Title</title>
<published>2026-07-01T00:00:00Z</published>
<summary>abstract</summary></entry></feed>""").encode()

        def fake_urlopen(req, timeout=None):
            return _Resp(atom)

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Some Real Paper Title", 2026, 5.0)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertNotIn("着陆页", note)

    def test_arxiv_api_parse_error_fallback(self):
        # API 返回非 XML（反爬 HTML 典型形态）→ 触发 fallback 而非静默跳过
        def fake_urlopen(req, timeout=None):
            if "export.arxiv.org" in req.full_url:
                return _Resp(b"<html><body>captcha wall</body></html>")
            return _Resp(self._landing_html("Some Real Paper Title").encode())

        with self._patch_sleep(), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            adj, note, matched = vr.arxiv_metadata_match(
                "2607.22693", "Some Real Paper Title", 2026, 5.0)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertIn("着陆页", note)

    # ---------- P0-2: semantic_audit ----------

    def test_semantic_structured_accepted(self):
        sa = vr.build_semantic_audit({"semantic": {
            "claim": "该药降低死亡率", "support": "SUPPORTED",
            "quote": "mortality was lower", "note": "表2"}})
        self.assertEqual(sa["support"], "supported")  # 大写归一
        self.assertEqual(sa["claim"], "该药降低死亡率")
        self.assertEqual(sa["quote"], "mortality was lower")
        self.assertEqual(sa["note"], "表2")

    def test_semantic_legacy_string_compat(self):
        # 旧字符串形式 → None（不建底稿、不影响判定）——向后兼容铁律
        self.assertIsNone(vr.build_semantic_audit({"semantic": "模型已判定支撑"}))
        self.assertIsNone(vr.build_semantic_audit({}))

    def test_semantic_invalid_support_becomes_unclear(self):
        sa = vr.build_semantic_audit({"semantic": {"claim": "x", "support": "yes!"}})
        self.assertEqual(sa["support"], "unclear")
        self.assertIn("非法值", sa["note"])

    def test_semantic_cap_not_in_source_demotes_verified(self):
        r = {"index": 1, "title": "t", "verdict": "verified", "note": "",
             "needs_human_check": False,
             "semantic_audit": {"claim": "c", "support": "not_in_source",
                                "quote": "", "note": ""}}
        vr.apply_semantic_cap([r])
        self.assertEqual(r["verdict"], "partial")
        self.assertTrue(r["needs_human_check"])
        self.assertIn("语义层判定", r["note"])
        self.assertIn("未包含", r["note"])

    def test_semantic_cap_contradicted(self):
        r = {"index": 1, "title": "t", "verdict": "verified", "note": "",
             "needs_human_check": False,
             "semantic_audit": {"claim": "c", "support": "contradicted",
                                "quote": "", "note": ""}}
        vr.apply_semantic_cap([r])
        self.assertEqual(r["verdict"], "partial")
        self.assertTrue(r["needs_human_check"])
        self.assertIn("相矛盾", r["note"])

    def test_semantic_supported_no_cap(self):
        r = {"index": 1, "title": "t", "verdict": "verified", "note": "",
             "needs_human_check": False,
             "semantic_audit": {"claim": "c", "support": "supported",
                                "quote": "", "note": ""}}
        vr.apply_semantic_cap([r])
        self.assertEqual(r["verdict"], "verified")
        self.assertFalse(r["needs_human_check"])

    def test_semantic_cap_invalid_not_promoted(self):
        # invalid 不得被语义封顶反向"提升"为 partial
        r = {"index": 1, "title": "t", "verdict": "invalid", "note": "x",
             "needs_human_check": True,
             "semantic_audit": {"claim": "c", "support": "not_in_source",
                                "quote": "", "note": ""}}
        vr.apply_semantic_cap([r])
        self.assertEqual(r["verdict"], "invalid")

    def test_semantic_md_section_conditional(self):
        base = {"index": 1, "title": "T", "tier": "journal", "http_status": 200,
                "verdict": "verified", "note": "", "needs_human_check": False,
                "url": "", "doi": "", "pmid": "", "arxiv": ""}
        with_sem = [dict(base, semantic_audit={
            "claim": "药 A 优于安慰剂", "support": "supported",
            "quote": "p<0.05", "note": ""})]
        md = vr.render_md(with_sem, False)
        self.assertIn("语义层判定", md)
        self.assertIn("药 A 优于安慰剂", md)
        md_plain = vr.render_md([dict(base)], False)
        self.assertNotIn("语义层判定", md_plain)  # 无语义字段 → 输出与 v1.10 一致

    def test_semantic_in_auditjson(self):
        results = [{"index": 1, "title": "T", "verdict": "verified", "tier": "journal",
                    "http_status": 200, "needs_human_check": False,
                    "checks": {}, "note": "",
                    "semantic_audit": {"claim": "c", "support": "supported",
                                       "quote": "q", "note": ""}}]
        p = os.path.join(self.tmp, "a.audit.json")
        vr.export_audit(results, p, False, "general")
        doc = json.load(open(p, encoding="utf-8"))
        self.assertIn("semantic_audit", doc["checks_catalog"])
        self.assertEqual(doc["results"][0]["semantic_audit"]["claim"], "c")

    # ---------- P1: 话术与工具 ----------

    def test_precheck_arxiv_2026_05_and_icml(self):
        sc = vr.compute_scorecard([{"verdict": "invalid"}, {"verdict": "verified"}])
        text = vr.precheck_conclusion(sc)
        self.assertIn("2026-05", text)
        self.assertNotIn("2026-06", text)
        self.assertIn("ICML", text)

    def test_agentskills_check_distro_mode(self):
        tool = os.path.join(HERE, "..", "tools", "agentskills_check.py")
        skill_md = os.path.join(HERE, "..", "SKILL.md")
        out = subprocess.run([sys.executable, tool, skill_md, "--distro"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("AGENTSPEAK_CHECK: PASS", out.stdout)
        self.assertIn("skills.sh", out.stdout)
        self.assertIn("when_to_use", out.stdout)


if __name__ == "__main__":
    unittest.main()
