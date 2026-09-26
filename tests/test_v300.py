#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.0.0：L3 引文语境 + L4 证据级联 + BLUF 双读者报告 + 跨语言标题守卫。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "mcp"))
import verify_refs as vr  # noqa: E402


def R(i, v, **kw):
    d = {"index": i, "title": f"Ref {i}", "verdict": v, "tier": "journal",
         "note": "", "needs_human_check": v == "invalid", "http_status": 200}
    d.update(kw)
    return d


class TestV300(unittest.TestCase):
    def setUp(self):
        vr._net_reset()
        vr._OPTS.update({"openalex_key": "", "s2_key": "", "mailto": "",
                         "ncbi_key": "", "contexts": True,
                         "judge_url": "", "judge_model": "m"})

    def test_version_is_300(self):
        self.assertEqual(vr.VERSION, "3.0.0")

    # ---- BLUF 双读者前置块 ----

    def test_bluf_md_head_and_yaml_keys(self):
        rs = [R(1, "verified"), R(2, "invalid")]
        md = vr.render_md(rs, False)
        self.assertTrue(md.startswith("---\nverdict:"), "md 必须以 BLUF YAML 开头")
        for k in ("verdict:", "key_numbers:", "blocker:", "next_action:",
                  "cite_holmes_version: 3.0.0"):
            self.assertIn(k, md.split("---")[1])

    def test_bluf_html_machine_readable(self):
        rs = [R(1, "verified")]
        html = vr.render_html(rs, False)
        self.assertIn("cite-holmes BLUF machine-readable", html)
        self.assertTrue('class="bluf"' in html or "class='bluf'" in html, "html 应含 bluf 前置块")

    def test_bluf_json_field(self):
        rs = [R(1, "verified")]
        sc = vr.compute_scorecard(rs)
        b = vr.render_bluf(rs, sc)
        self.assertIn("全部 verified", b)

    def test_bluf_all_invalid_wording(self):
        rs = [R(1, "invalid"), R(2, "invalid")]
        b = vr.render_bluf(rs, vr.compute_scorecard(rs))
        self.assertIn("不建议直接使用", b)
        self.assertIn("2 条编造/无效", b)

    # ---- L3 引文语境 ----

    def test_s2_citation_contexts_parses(self):
        body = json.dumps({"data": [
            {"contexts": ["AlphaFold predicts structure with high accuracy."],
             "intents": ["methodology"], "isInfluential": True,
             "citingPaper": {"title": "A Review of Protein Folding"}},
            {"contexts": [], "intents": [], "isInfluential": False,
             "citingPaper": {"title": "Unrelated"}}]})

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return body.encode()
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=Resp()):
            ctx = vr.s2_citation_contexts("10.1/x", 5)
        self.assertEqual(ctx["cited_by"], 2)
        self.assertEqual(ctx["coverage"], 0.5)
        self.assertEqual(ctx["samples"][0]["influential"], True)
        self.assertIn("AlphaFold", ctx["samples"][0]["context"])

    def test_s2_contexts_failure_silent(self):
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=RuntimeError("net")):
            ctx = vr.s2_citation_contexts("10.1/x", 5)
        self.assertEqual(ctx, {})

    def test_l3_wired_into_verified_doi(self):
        csl = json.dumps({"title": ["A Verified Paper About Topic X"],
                          "issued": {"date-parts": [[2026]]}}).encode()
        cr = json.dumps({"message": {}}).encode()
        ctx_body = json.dumps({"data": [{"contexts": ["cited as breakthrough"],
                                         "intents": ["background"],
                                         "isInfluential": True,
                                         "citingPaper": {"title": "Later Work"}}]}).encode()

        class Resp:
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return self.body
        calls = {"n": 0}

        def dispatch(req, timeout=None):
            calls["n"] += 1
            u = req.full_url
            if "crossref" in u:
                return Resp(cr)
            if "/citations" in u:
                return Resp(ctx_body)
            return Resp(csl)
        ref = {"title": "A Verified Paper About Topic X", "doi": "10.1000/good",
               "source": "Journal of Good Things", "year": 2026}
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=dispatch), \
                unittest.mock.patch.object(vr, "check_url",
                                           return_value=(True, 200, "GET 200")):
            r = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(r["verdict"], "verified")
        self.assertIn("citation_contexts", r["checks"])
        self.assertEqual(r["citation_contexts"]["cited_by"], 1)
        self.assertIn("学界评价", r["note"])

    # ---- L4 证据级联 ----

    def test_chunk_overlap(self):
        ch = vr.chunk_text("x" * 2000, size=900, overlap=120)
        self.assertEqual(len(ch), 3)
        self.assertEqual(len(ch[0]), 900)

    def test_retrieve_tfidf_fallback(self):
        with unittest.mock.patch.object(vr, "_embed_ollama", return_value=[]):
            ev = vr.retrieve_evidence(
                "tocilizumab sJIA",
                "weather text. " * 20 + "tocilizumab treats sJIA patients. " * 5, k=1)
        self.assertEqual(len(ev), 1)
        self.assertIn("tocilizumab", ev[0].lower())

    def test_judge_no_endpoint_degrades(self):
        j = vr.judge_claim_via_endpoint("claim", "evidence")
        self.assertEqual(j["verdict"], "NEI")
        self.assertEqual(j["degraded"], "no-judge-endpoint")

    def test_judge_parses_labels(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:19999/v1"

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return json.dumps({"choices": [{"message": {
                    "content": "SUPPORTS"}}]}).encode()
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=Resp()):
            j = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(j["verdict"], "SUPPORTS")
        vr._OPTS["judge_url"] = ""

    def test_pubmed_abstract_fetch(self):
        abstract = b"Abstract: Tocilizumab works."

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return abstract
        captured = {}

        def cap(req, timeout=None):
            captured["url"] = req.full_url
            return Resp()
        with unittest.mock.patch.object(vr.urllib.request, "urlopen", cap):
            t = vr.fetch_pubmed_abstract("12345678", 5)
        self.assertIn("Tocilizumab", t)
        self.assertIn("efetch.fcgi", captured["url"])

    # ---- 跨语言标题守卫 ----

    def test_crosslang_doi_title_partial_not_invalid(self):
        # 中文声称 vs 英文登记 → partial(不再 invalid)
        csl = json.dumps({"title": ["Tocilizumab for sJIA treatment"],
                          "issued": {"date-parts": [[2021]]}}).encode()

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return csl
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=Resp()):
            adj, note, matched = vr.doi_metadata_match(
                "10.1/x", "托珠单抗治疗幼年特发性关节炎", 2021, 5, "", "")
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言", note)

    def test_same_lang_wrong_paper_still_invalid(self):
        csl = json.dumps({"title": ["Totally Different Paper About Weather"],
                          "issued": {"date-parts": [[2021]]}}).encode()

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return csl
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=Resp()):
            adj, note, matched = vr.doi_metadata_match(
                "10.1/x", "Tocilizumab for sJIA", 2021, 5, "", "")
        self.assertEqual(adj, "invalid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
