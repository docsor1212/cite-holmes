#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.5.0 测试：文献发现（--discover 双源+出生即核验）+ --demo 零门槛体验。

背景（2026-10-19 调研）：「查文献/综述」邻域已有大体量检索类 skill；本版差异化
=文献发现与核验一体（每条出生即核验）。全部 sealed（零真网依赖）。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


def _resp(body):
    if isinstance(body, str):
        body = body.encode()

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body
    return R()


class F15_DiscoverRefs(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _dispatch(self, pmid_ids=("39429074",), summaries=None,
                  openalex_results=None):
        summaries = summaries or {
            "39429074": {"title": "Clinical practice guideline for bronchiolitis "
                                  "in children (2024 edition)",
                         "source": "Zhonghua Er Ke Za Zhi", "pubdate": "2024 Nov",
                         "articleids": [{"idtype": "doi",
                                         "value": "10.3760/cma.j.x"}]}}
        openalex_results = openalex_results if openalex_results is not None else [
            {"display_name": "Wheezing disorders in preschool children: an update",
             "publication_year": 2024, "doi": "https://doi.org/10.1000/disc1",
             "primary_location": {"source": {"display_name": "Pediatr Pulmonol"}}}]

        def disp(req, timeout=None):
            u = req.full_url
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": str(len(pmid_ids)), "idlist": list(pmid_ids)}}).encode())
            if "esummary" in u:
                return _resp(json.dumps({"result": dict(
                    {"uids": list(pmid_ids)},
                    **{k: v for k, v in summaries.items()})}).encode())
            if "api.openalex.org" in u:
                return _resp(json.dumps({"results": openalex_results}).encode())
            raise AssertionError(f"[seal] 未预期调用: {u[:80]}")
        return disp

    def test_dual_source_merge_and_shape(self):
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch()):
            refs, notes = vr.discover_refs("bronchiolitis", 5, 10.0)
        self.assertEqual(len(refs), 2, f"双源各一: {refs}")
        pm = [r for r in refs if r.get("pmid")]
        self.assertEqual(len(pm), 1, "PubMed 源带 PMID（OpenAlex 源无）")
        self.assertTrue(all(r.get("doi") for r in refs),
                        "双源条目都应尽量带 DOI 锚")
        self.assertTrue(all(r.get("title") and r.get("year") for r in refs))
        self.assertEqual(notes, [])

    def test_dedupe_by_doi(self):
        # 同一论文双源命中（同 DOI）→ 去重为一条
        results = [{"display_name": "Clinical practice guideline for bronchiolitis "
                                    "in children (2024 edition)",
                    "publication_year": 2024,
                    "doi": "https://doi.org/10.3760/cma.j.x"}]
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(openalex_results=results)):
            refs, notes = vr.discover_refs("bronchiolitis", 5, 10.0)
        self.assertEqual(len(refs), 1, f"同 DOI 应去重: {len(refs)}")

    def test_pubmed_zero_hit_openalex_still_delivers(self):
        # 单源零命中不崩批（家族纪律：单源失败静默跳过）
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(pmid_ids=())):
            refs, notes = vr.discover_refs("topic", 5, 10.0)
        self.assertEqual(len(refs), 1)
        self.assertTrue(any("零命中" in n for n in notes))

    def test_short_titles_filtered(self):
        results = [{"display_name": "Short", "publication_year": 2024,
                    "doi": "https://doi.org/10.1/x"}]
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(
                                     pmid_ids=(), openalex_results=results)):
            refs, notes = vr.discover_refs("topic", 5, 10.0)
        self.assertEqual(refs, [], "过短题名过滤")


class F16_Demo(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_demo_loads_bundled_refs(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "r.md")
        rc = vr.main_with_args(["--demo", "--out", out, "--offline"])
        self.assertEqual(rc, 0)
        j = json.load(open(out[:-3] + ".json", encoding="utf-8"))
        self.assertEqual(len(j["results"]), 8, "内置样例 8 条")
        # 金标契约：预埋伪造必须 non-verified（offline 语义下封顶态可能不同，
        # 但绝不允许伪造条目混进 verified）
        fakes = [r for r in j["results"] if r.get("verdict") != "verified"]
        self.assertGreaterEqual(len(fakes), 3,
                                f"三处伪造应 non-verified: {[r['verdict'] for r in j['results']]}")

    def test_demo_yields_to_explicit_refs(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        refs_file = os.path.join(tmp, "refs.json")
        with open(refs_file, "w", encoding="utf-8") as f:
            json.dump([{"title": "显式清单优先于内置样例的条目测试", "source": "X",
                        "year": 2024}], f)
        out = os.path.join(tmp, "r2.md")
        rc = vr.main_with_args(["--demo", "--refs", refs_file, "--out", out,
                                "--offline"])
        self.assertEqual(rc, 0)
        j = json.load(open(out[:-3] + ".json", encoding="utf-8"))
        self.assertEqual(len(j["results"]), 1, "显式 --refs 优先")


class F17_DescReach(unittest.TestCase):
    def test_zh_desc_volume_terms(self):
        t = open(os.path.join(HERE, "..", "SKILL_ZH.md"),
                 encoding="utf-8").read()
        for kw in ("综述", "文献检索", "文献发现", "找文献"):
            self.assertIn(kw, t, kw)

    def test_discover_in_help(self):
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        assert '"--discover"' in src and '"--demo"' in src


if __name__ == "__main__":
    unittest.main()
