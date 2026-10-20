#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.6.0 测试：EB/OL URL 提取 + 缩写句点/批准文号年份修正 + discover 增强。

背景（2026-10-21 dogfood 第五轮实锤，西替利嗪报告 17/20 verified 82/B）：
- 'U.S. Food and Drug Administration' 的缩写句点被切分器劈开→机构名当题名；
- 批准文号 H20093320 里的 2009 被当出版年；
- [1][2] EB/OL 类引用（说明书/指南，中文医学文档高频形态）URL 在著录里却
  不提取，裸 unverified。全部 sealed。"""
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


class F19_ParseFixes(unittest.TestCase):
    def test_us_abbreviation_not_split(self):
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[2] U.S. Food and Drug Administration. Cetirizine "
            "hydrochloride oral solution, USP prescribing information[EB/OL]. "
            "[2026-09-28]. https://dailymed.nlm.nih.gov/x.\n")
        self.assertTrue(refs[0]["title"].startswith("Cetirizine hydrochloride"),
                        f"题名误提: {refs[0]['title'][:50]}")

    def test_normal_initial_boundary_still_splits(self):
        # 首字母缩略后的题名界（N H. Title）必须照常切分
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[5] HANSEN J J, FEILBERG JORGENSEN N H. Accidental "
            "cetirizine poisoning in a four-year-old boy[J]. Ugeskr Laeger, "
            "1998, 160(41): 5946-5947.\n")
        self.assertTrue(refs[0]["title"].startswith("Accidental cetirizine"),
                        refs[0]["title"][:50])

    def test_approval_number_not_year(self):
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[1] 北京韩美药品有限公司. 仙达安盐酸西替利嗪口服溶液说明书"
            "（国药准字H20093320）[EB/OL]. (2014-01-13)[2026-09-28]. https://x.\n")
        self.assertEqual(refs[0]["year"], 2014, "批准文号里的 2009 不是年份")

    def test_legacy_year_unchanged(self):
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[1] A. A long enough title about physiology here now[J]. "
            "Pediatrics, 2014, 134(5): e1474.\n")
        self.assertEqual(refs[0]["year"], 2014)


class F18_EBOLUrl(unittest.TestCase):
    def test_url_extracted_when_no_strong_anchor(self):
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[2] U.S. Food and Drug Administration. Cetirizine "
            "hydrochloride oral solution, USP prescribing information[EB/OL]. "
            "[2026-09-28]. https://dailymed.nlm.nih.gov/dailymed/services/v2/x.xml.\n")
        self.assertTrue(refs[0]["url"].startswith("https://dailymed.nlm.nih.gov"))

    def test_strong_anchor_wins_no_url_shadow(self):
        # 带 DOI 的条目不提 URL（强锚优先，url 字段不遮蔽 doi 通路）
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[3] 胡利华, 等. 儿科常用H1抗组胺药处方审核专家共识[J]. "
            "中华实用儿科临床杂志, 2023, 38(10): 733-739. "
            "DOI: 10.3760/cma.j.cn101070-20230802-00060. https://example.com/x.\n")
        self.assertNotIn("url", refs[0])
        self.assertEqual(refs[0]["doi"], "10.3760/cma.j.cn101070-20230802-00060")

    def test_url_ref_flows_to_url_pipeline(self):
        fresh_engine_state(vr)
        ref = {"title": "Cetirizine hydrochloride oral solution prescribing info",
               "url": "https://dailymed.nlm.nih.gov/dailymed/services/v2/x.xml",
               "year": 2026}
        with unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=AssertionError("seal: no net")):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertIn(out["verdict"], ("verified", "partial", "unverified", "unreachable"))
        self.assertNotEqual(out["verdict"], "invalid")
        # 审计 P2-G：真锁 URL 进了 URL 管道（路由回归可假绿——旧断言只锁「不炸」）
        self.assertTrue((out["checks"].get("url") or {}).get("reachable"),
                        "url 字段应驱动可达性检查")


class F20_DiscoverEnhanced(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _dispatch(self, openalex_results):
        def disp(req, timeout=None):
            u = req.full_url
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": "0", "idlist": []}}).encode())
            if "api.openalex.org" in u:
                return _resp(json.dumps({"results": openalex_results}).encode())
            raise AssertionError(f"[seal] 未预期调用: {u[:80]}")
        return disp

    def test_cross_source_title_merge(self):
        # 同题不同键（一条带 DOI 一条仅题名无 DOI）→ 合并非重复
        results = [
            {"display_name": "Wheezing disorders in preschool children updated",
             "publication_year": 2024, "doi": "https://doi.org/10.1000/a",
             "primary_location": {"source": {"display_name": "Pediatr Pulmonol"}}},
            {"display_name": "Wheezing disorders in preschool children updated",
             "publication_year": 2024, "doi": None,
             "primary_location": {"source": {"display_name": "Other J"}}},
        ]
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(results)):
            refs, notes = vr.discover_refs("wheezing", 5, 10.0)
        self.assertEqual(len(refs), 1, f"同题应合并: {len(refs)}")
        self.assertEqual(refs[0]["doi"], "10.1000/a")
        self.assertEqual(refs[0]["source"], "Pediatr Pulmonol",
                         "字段互补应取到非空来源")

    def test_since_filter(self):
        results = [
            {"display_name": "An old enough study about wheezing here one",
             "publication_year": 2015, "doi": None},
            {"display_name": "A recent enough study about wheezing here two",
             "publication_year": 2024, "doi": None},
        ]
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(results)):
            refs, _ = vr.discover_refs("wheezing", 5, 10.0, since=2020)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["year"], 2024)

    def test_no_year_kept_when_since(self):
        # 无年份条目保留（宁多勿错杀）
        results = [{"display_name": "An undated study about wheezing here three",
                    "publication_year": None, "doi": None}]
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._dispatch(results)):
            refs, _ = vr.discover_refs("wheezing", 5, 10.0, since=2020)
        self.assertEqual(len(refs), 1)


if __name__ == "__main__":
    unittest.main()
