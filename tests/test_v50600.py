#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.6.0 测试：开放获取（Unpaywall 数据富集）+ MCP 工具面扩展 + HTML 学界用法。

F42=unpaywall_lookup 解析/静默/三门 helper；F43=MCP 新工具（源码锚点+引擎层）；
F44=render_html 学界用法节对齐 md 层。全部 sealed（urlopen 桩/tmpdir，零真网）。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402

OA_JSON = json.dumps({"is_oa": True,
                      "best_oa_location": {"license": "cc-by",
                                           "url": "https://oa.example/x"}}).encode()
NO_OA = b'{"is_oa": false}'


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


class F42_UnpaywallLookup(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_parse_oa_and_no_oa(self):
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        lambda req, timeout=None: _Resp(OA_JSON)):
            o = vr.unpaywall_lookup("10.1234/x", "a@b.c", 5.0)
        self.assertEqual(o, {"is_oa": True, "license": "cc-by",
                             "oa_url": "https://oa.example/x"})
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        lambda req, timeout=None: _Resp(NO_OA)):
            self.assertEqual(vr.unpaywall_lookup("10.1234/y", "a@b.c", 5.0),
                             {"is_oa": False})

    def test_silent_failures(self):
        import urllib.error
        with unittest.mock.patch.object(
                vr.urllib.request, "urlopen",
                lambda req, timeout=None: (_ for _ in ()).throw(
                    urllib.error.HTTPError(req.full_url, 404, "NA", None, None))):
            self.assertEqual(vr.unpaywall_lookup("10.1234/n", "a@b.c", 5.0), {})
        with unittest.mock.patch.object(
                vr.urllib.request, "urlopen",
                lambda req, timeout=None: (_ for _ in ()).throw(IOError("reset"))):
            self.assertEqual(vr.unpaywall_lookup("10.1234/n", "a@b.c", 5.0), {})


class F42_EnrichWiring(unittest.TestCase):
    """_open_access_enrich 三门：verified+DOI+mailto；纯数据富集。"""

    def setUp(self):
        fresh_engine_state(vr)

    def _out(self, verdict="verified", doi="10.1234/x"):
        return {"verdict": verdict, "doi": doi, "checks": {}}

    def test_populates_when_gates_pass(self):
        vr._OPTS["mailto"] = "a@b.c"
        out = self._out()
        with unittest.mock.patch.object(vr, "unpaywall_lookup",
                                        return_value={"is_oa": True,
                                                      "license": "cc-by",
                                                      "oa_url": "https://o/x"}):
            vr._open_access_enrich(out, 5.0)
        self.assertEqual(out["checks"]["open_access"]["license"], "cc-by")
        self.assertTrue(out["checks"]["open_access"]["ran"])
        self.assertEqual(out["verdict"], "verified")   # 判定不变

    def test_gates_block(self):
        vr._OPTS["mailto"] = "a@b.c"
        for out in (self._out("partial"), self._out("invalid"),
                    self._out("verified", doi="not-a-doi")):
            with unittest.mock.patch.object(
                    vr, "unpaywall_lookup",
                    side_effect=AssertionError("门未拦住")):
                vr._open_access_enrich(out, 5.0)
            self.assertNotIn("open_access", out["checks"])
        vr._OPTS["mailto"] = ""
        out = self._out()
        with unittest.mock.patch.object(
                vr, "unpaywall_lookup",
                side_effect=AssertionError("无 mailto 不应调用")):
            vr._open_access_enrich(out, 5.0)
        self.assertNotIn("open_access", out["checks"])

    def test_behavioral_wiring_doi_main_path(self):
        # 审计 P0-1 行为级锁：OA 富集在终局判定落定后接线（wrapper 统一后处理
        # 覆盖四条提前 return 的 verified 路径+主路径）——真实 verify_one 流转
        vr._OPTS["mailto"] = "a@b.c"   # setUp 重置 _OPTS，逐测补回
        ref = {"title": "Some comprehensive verified doi entry",
               "doi": "10.1234/abc", "year": 2020, "source": "J"}
        calls = {"up": 0}

        def fake_up(doi, mailto, timeout):
            calls["up"] += 1
            return {"is_oa": True, "license": "cc-by", "oa_url": "https://oa/x"}
        with unittest.mock.patch.object(
                vr, "doi_metadata_match",
                return_value=("", "DOI 元数据核验一致（相似度 0.95）", True,
                              {"title": ref["title"], "container-title": ["J"],
                               "issued": {"date-parts": [[2020]]}})), \
             unittest.mock.patch.object(vr, "s2_citation_contexts",
                                        return_value={}), \
             unittest.mock.patch.object(vr, "s2_doi_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch.object(vr, "openalex_title_check",
                                        return_value=""), \
             unittest.mock.patch.object(vr, "unpaywall_lookup",
                                        side_effect=fake_up), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")):
            out = vr.verify_one(ref, 1, False, 5.0, False)
        self.assertEqual(out["verdict"], "verified")
        self.assertEqual(calls["up"], 1)
        self.assertTrue(out["checks"]["open_access"]["is_oa"])


class F43_McpSurface(unittest.TestCase):
    def test_server_source_anchors(self):
        src = open(os.path.join(SK, "mcp", "server.py"), encoding="utf-8").read()
        self.assertIn("def discover_references(", src)
        self.assertIn("def build_review_kit(", src)
        self.assertIn("verify_references_impl(refs, timeout, 800)", src)  # 出生即核验
        self.assertIn('vr.build_review_kit(safe, [], topic=str(topic or "")[:200])', src)
        self.assertIn("_clip(kit, _CLIP_STR)", src)  # 审计 P2-1：输出截断契约

    def test_readme_tools_listed(self):
        s = open(os.path.join(SK, "mcp", "README.md"), encoding="utf-8").read()
        self.assertIn("discover_references", s)
        self.assertIn("build_review_kit", s)

    def test_engine_layer_kit(self):
        kit = vr.build_review_kit(
            [{"index": 1, "title": "T", "verdict": "verified", "doi": "10.1/x",
              "source": "J", "year": 2024, "note": "", "needs_human_check": False,
              "checks": {}}], [], topic="t")
        self.assertIn("综述表格", kit)


class F44_HtmlUsage(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _row(self, cc=None):
        r = {"index": 1, "title": "T", "url": "", "doi": "", "pmid": "",
             "arxiv": "", "source": "J", "year": 2024, "tier": "official",
             "semantic": "", "verdict": "partial", "http_status": 200,
             "note": "", "needs_human_check": False, "checks": {}}
        if cc:
            r["citation_contexts"] = cc
        return r

    def test_html_usage_section(self):
        cc = {"cited_by": 9, "samples": [
            {"context": "cited for its method", "intents": ["methodology"],
             "influential": True, "citing_title": "Z"}]}
        html = vr.render_html([self._row(cc)], False)
        self.assertIn("学界用法（引文语境）", html)
        self.assertIn("方法学×1", html)
        html2 = vr.render_html([self._row()], False)
        self.assertNotIn("学界用法", html2)

    def test_md_oa_summary_line(self):
        r = self._row()
        r["checks"]["open_access"] = {"ran": True, "is_oa": True,
                                      "license": "cc-by", "oa_url": "https://o/x"}
        md = vr.render_md([r], False)
        self.assertIn("开放获取：1/1 条可免费读取", md)
        md2 = vr.render_md([self._row()], False)
        self.assertNotIn("开放获取", md2)

    def test_kit_oa_lines(self):
        r = self._row()
        r["verdict"] = "verified"
        r["checks"]["open_access"] = {"ran": True, "is_oa": True,
                                      "license": "cc-by", "oa_url": "https://o/x"}
        kit = vr.build_review_kit([r], [], topic="t")
        self.assertIn("开放获取：cc-by", kit)
        r2 = self._row(2)
        r2["verdict"] = "verified"
        r2["checks"]["open_access"] = {"ran": True, "is_oa": False}
        kit2 = vr.build_review_kit([r2], [], topic="t")
        self.assertIn("无免费全文", kit2)


class Docs(unittest.TestCase):
    def test_budgets_and_anchors(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)
        for t in (en, zh):
            self.assertIn("discover_references", t)
            self.assertIn("build_review_kit", t)
            self.assertIn("Unpaywall", t)
        vd = open(os.path.join(SK, "references", "verification-details.md"),
                  encoding="utf-8").read()
        self.assertIn("Unpaywall", vd)
        self.assertIn("discover_references", vd)
        faq = open(os.path.join(SK, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("Unpaywall", faq)




class F45_PubmedLanding404(unittest.TestCase):
    """v5.6.0 审计修复（T2 实战回归）：PubMed 落地页对不存在 PMID 返回真 404 后，
    unreachable 提前 return 不得屏蔽 E-utilities 权威存在性判定。"""

    def _stub(self, esum_body):
        def stub(req, timeout=None):
            u = req.full_url
            if "pubmed.ncbi.nlm.nih.gov" in u:
                import urllib.error
                raise urllib.error.HTTPError(u, 404, "NF", None, None)
            if "esummary" in u:
                return type("R", (), {"__enter__": lambda s: s,
                                      "__exit__": lambda s, *a: False,
                                      "read": lambda s: esum_body})()
            raise AssertionError("意外外呼 " + u)
        return stub

    def test_fake_pmid_landing404_still_invalid(self):
        err = json.dumps({"result": {"uids": ["99999999"], "99999999": {
            "uid": "99999999", "error": "cannot get document summary"}}}).encode()
        ref = {"title": "Tocilizumab efficacy in sJIA landmark trial",
               "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/",
               "pmid": "99999999", "source": "Journal of X", "year": 2025}
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        self._stub(err)), \
             unittest.mock.patch.object(vr.time, "sleep", lambda s: None):
            out = vr.verify_one(ref, 5, False, 10.0, False)
        self.assertEqual(out["verdict"], "invalid")
        self.assertIn("不存在", out["note"])

    def test_real_pmid_landing404_never_invalid(self):
        ok = json.dumps({"result": {"uids": ["39429074"], "39429074": {
            "title": "[Clinical practice guidelines]",
            "fulljournalname": "J", "pubdate": "2024 Nov",
            "articleids": []}}}).encode()
        ref = {"title": "[Clinical practice guidelines]",
               "url": "https://pubmed.ncbi.nlm.nih.gov/39429074/",
               "pmid": "39429074", "source": "J", "year": 2024}
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        self._stub(ok)), \
             unittest.mock.patch.object(vr.time, "sleep", lambda s: None):
            out = vr.verify_one(ref, 6, False, 10.0, False)
        self.assertNotEqual(out["verdict"], "invalid")  # 查无永不判死

    def test_transport_failure_stays_unreachable(self):
        # fail-safe：E-utilities 传输失败按可达处理 → unreachable（不误判 invalid）
        ref = {"title": "Tocilizumab efficacy in sJIA landmark trial",
               "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/",
               "pmid": "99999999", "source": "J", "year": 2025}

        def stub(req, timeout=None):
            if "pubmed.ncbi.nlm.nih.gov" in req.full_url:
                import urllib.error
                raise urllib.error.HTTPError(req.full_url, 404, "NF", None, None)
            raise IOError("reset")   # E-utilities 传输失败
        with unittest.mock.patch.object(vr.urllib.request, "urlopen", stub), \
             unittest.mock.patch.object(vr.time, "sleep", lambda s: None):
            out = vr.verify_one(ref, 5, False, 10.0, False)
        self.assertEqual(out["verdict"], "unreachable")


if __name__ == "__main__":
    unittest.main()
