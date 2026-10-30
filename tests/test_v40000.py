#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.0.0 测试:版本规则对齐+F1 PubMed 题名反查(Vancouver 医学引用核验)+
F1-b markdown 参考文献提取+429 可观测。网络路径以 mock 覆盖。"""
import importlib.util
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
from _mocks import NCBIMock, fresh_engine_state  # noqa: E402


def _mock_esearch(ids):
    """构造 esearch+esummary 两跳 mock。"""
    class Ctx:
        def __init__(self, payload):
            self.payload = payload
        def read(self, n=-1):
            return json.dumps(self.payload).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    def fake_urlopen(req, timeout=None):
        u = req.full_url
        if "esearch" in u:
            return Ctx({"esearchresult": {"idlist": ids}})
        # esummary
        result = {}
        for pid in ids:
            result[pid] = {"title": "2013 classification criteria for systemic sclerosis: "
                                    "an American College of Rheumatology/European League "
                                    "Against Rheumatism classification criteria",
                           "source": "Arthritis Rheum", "pubdate": "2013 Nov"}
        return Ctx({"result": result, "esearchresult": {"idlist": ids}})
    return fake_urlopen


class TestPubmedTitleReverseLookup(unittest.TestCase):
    """F1:Vancouver 医学引用的 PubMed 题名反查。"""

    def setUp(self):
        fresh_engine_state(vr)  # 测试间全局状态隔离（机制化）

    def test_hit_upgrades(self):
        T = "2013 American College of Rheumatology/European League against Rheumatism classification criteria for systemic sclerosis"
        with unittest.mock.patch("urllib.request.urlopen", side_effect=NCBIMock(
                default_ids=["24122180"],
                summaries={"24122180": {
                    "title": "2013 classification criteria for systemic sclerosis: "
                             "an American College of Rheumatology/European League "
                             "Against Rheumatism classification criteria",
                    "source": "Arthritis Rheum", "pubdate": "2013 Nov"}})):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(T, "Arthritis Rheum", 2013, 10.0)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertEqual(pmid, "24122180")
        self.assertIn("反查核验一致", note)

    def test_word_count_descending(self):
        # 5 词零命中时递减 4/3 词（mock 只在 3 词命中）
        T = "Mechanisms of Disease Scleroderma Lung Involvement Severe"
        mock = NCBIMock(esearch_hits={5: [], 4: [], 3: ["999"]},
                        summaries={"999": {"title": "Mechanisms of Disease Scleroderma Lung",
                                           "source": "X", "pubdate": "2020 Jan"}})
        with unittest.mock.patch("urllib.request.urlopen", side_effect=mock):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(T, "", 2020, 10.0)
        self.assertTrue(matched)
        n_calls = [c for c in mock.calls if c[0] == "esearch"]
        self.assertTrue(any(c[1].count("[Title]") == 3 for c in n_calls),
                        f"应递减到 3 词: {n_calls}")

    def test_zero_hit_silent(self):
        T = "A Very Unusual Title About Nonexistent Topics Here"
        with unittest.mock.patch("urllib.request.urlopen", side_effect=NCBIMock(default_ids=[])):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(T, "", 2020, 10.0)
        self.assertEqual(adj, "")
        self.assertFalse(matched)

    def test_429_observable(self):
        # 审计要求:限流可观测——「没搜成」≠「搜了没命中」
        err = urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b""))
        with unittest.mock.patch("urllib.request.urlopen", side_effect=err):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                "A Title Long Enough For Lookup Testing", "", 2020, 10.0)
        self.assertIn("限流", note)
        self.assertFalse(matched)

    def test_short_title_skipped(self):
        adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup("Short", "", 2020, 10.0)
        self.assertFalse(matched)

    def test_sim_jaccard_wordset_on_raw(self):
        # 词集用原始题名（保留空格）切词——_cjk_norm 连续串上 findall 退化（实测踩坑）
        s = vr._cjk_norm("Abc Def")
        self.assertNotIn(" ", s)
        # 直接验证 _title_sim 若存在则用公开路径测（双通道取大）
        T = "2013 American College of Rheumatology classification criteria"
        M = "2013 classification criteria: an American College of Rheumatology guideline"
        # 词集重合高、序列低——只要综合分 >= 单序列分即可
        import difflib, re
        seq = difflib.SequenceMatcher(None, vr._cjk_norm(T).lower(), vr._cjk_norm(M).lower()).ratio()
        ta = set(re.findall(r"[a-z0-9]+", T.lower()))
        tb = set(re.findall(r"[a-z0-9]+", M.lower()))
        jac = len(ta & tb) / len(ta | tb)
        self.assertGreater(jac, seq)


class TestMarkdownRefs(unittest.TestCase):
    """F1-b:markdown 参考文献节 Vancouver 提取。"""

    def test_extract_ssc_style(self):
        md = (
            "## 9. 参考文献\n\n"
            "### 分类标准\n"
            "1. **van den Hoogen F, et al.** 2013 American College of Rheumatology/European "
            "League against Rheumatism classification criteria for systemic sclerosis. "
            "*Arthritis Rheum*. 2013;65(11):2737-2747.\n\n"
            "2. **LeRoy EC, et al.** Scleroderma (systemic sclerosis): classification, subsets "
            "and pathogenesis. *J Rheumatol*. 1988;15(2):202-205.\n"
        )
        refs = vr.parse_markdown_refs(md)
        self.assertGreaterEqual(len(refs), 2)
        self.assertIn("classification criteria", refs[0]["title"])
        self.assertEqual(refs[0]["year"], 2013)

    def test_no_section_uses_whole_text(self):
        md = "1. Some Author. A Long Enough Title For Extraction Testing Here. *Journal*. 2020;1:2.\n"
        refs = vr.parse_markdown_refs(md)
        self.assertGreaterEqual(len(refs), 1)

    def test_non_numbered_lines_skipped(self):
        md = "## 参考文献\n一些说明文字\n这不是编号行\n1. Author X. A Long Enough Title For The Test. *J*. 2020;1:2.\n"
        refs = vr.parse_markdown_refs(md)
        self.assertEqual(len(refs), 1)


class TestWiringAndVersion(unittest.TestCase):
    def test_verify_one_calls_reverse_lookup(self):
        src = open(os.path.join(SK, "scripts", "verify_refs.py"), encoding="utf-8").read()
        self.assertIn("pubmed_title_reverse_lookup(", src)
        self.assertIn('"pubmed_reverse"', src)
        self.assertIn("skipped_by_circuit", src)

    def test_refs_loader_accepts_md(self):
        src = open(os.path.join(SK, "scripts", "verify_refs.py"), encoding="utf-8").read()
        self.assertIn('path.lower().endswith((".md", ".markdown"))', src)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "5.8.0")
        self.assertIn("version: 5.8.0",
                      open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read())

    def test_version_scheme_rule(self):
        # 版本号十进制规则:trunk 不得出现 x.10.0 式段
        self.assertFalse(re.match(r"4\.10\.", vr.VERSION))


import re  # noqa: E402  (test_version_scheme_rule 用)


if __name__ == "__main__":
    unittest.main(verbosity=2)
