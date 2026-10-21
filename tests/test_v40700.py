#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7.0 测试：点式缩写作者自愈（审计 P2-A 语义级修复）+ 文献发现排序。

背景（v4.6.0 审计 A4 探针）：链式缩写守卫保护 U.S. 型机构名的同时，把欧式
点式作者（HANSEN J.J. Title[J]）并进首段→作者污染题名→假 unverified（保守向）。
F21 语义级自愈；F22 --discover-sort（relevance/cited/newest）。全部 sealed。"""
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


class F21_DottedInitialSelfHeal(unittest.TestCase):
    def test_dotted_author_heals(self):
        # 审计 A4 原案：点式缩写作者 + 题名 + 类型码
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[5] HANSEN J.J. Accidental cetirizine poisoning in a "
            "four-year-old boy here[J]. Ugeskr Laeger, 1998, 160(41): 5946-5947.\n")
        self.assertTrue(refs[0]["title"].startswith("Accidental cetirizine"),
                        f"自愈失效: {refs[0]['title'][:60]}")
        self.assertEqual(refs[0]["source"], "Ugeskr Laeger")

    def test_us_org_regression(self):
        # U.S. 机构名回归（自愈不得误伤既有修复）
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[2] U.S. Food and Drug Administration. Cetirizine "
            "hydrochloride oral solution prescribing information[EB/OL]. "
            "[2026-09-28]. https://x.\n")
        self.assertTrue(refs[0]["title"].startswith("Cetirizine"))

    def test_title_with_version_dots_guard(self):
        # 假阳性守卫（审计 E-P3：真实数字形态探针）——题名含 "Ver 2.0" 且
        # 前段无点式缩写模式时不触发自愈
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[1] Expert consensus on management standards Ver 2.0 "
            "edition management[J]. Chinese Medical Journal, 2020, 100(2): 81-90.\n")
        self.assertTrue(refs[0]["title"].startswith("Expert consensus"),
                        refs[0]["title"][:60])

    def test_title_with_us_inside_author_path(self):
        # 审计 A-P1 封印：题名含 U.K./Q.T. 形态（题名先行 + 作者头形态不符）不拆
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[4] Cost-effectiveness of U.K. pharmacogenomics "
            "testing programmes today[J]. BMJ Open, 2024, 14(2): 1-11.\n")
        self.assertTrue(refs[0]["title"].startswith("Cost-effectiveness of U.K."),
                        refs[0]["title"][:60])

    def test_year_comma_blocks_heal(self):
        # 年份逗号阻断路径（期刊段形态不拆）
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[6] HANSEN J.J. Accidental cetirizine poisoning[J]. "
            "Ugeskr Laeger, 1998, 160(41): 5946-5947.\n")
        # 该条无题名先行标记：走常规路径，题名不混入作者
        self.assertTrue(refs[0]["title"].startswith("Accidental"),
                        refs[0]["title"][:60])

    def test_title_first_without_dots_unchanged(self):
        # 无点式缩写的题名先行著录照旧
        refs = vr.parse_markdown_refs(
            "参考文献\n\n[1] 毛细支气管炎诊断治疗与预防专家共识2014年版[EB/OL]. "
            "中华儿科杂志. [2026-09-28]. https://x.\n")
        self.assertTrue(refs[0]["title"].startswith("毛细支气管炎"))


class F22_DiscoverSort(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _dispatch(self, openalex_results=None):
        def disp(req, timeout=None):
            u = req.full_url
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": "0", "idlist": []}}).encode())
            if "api.openalex.org" in u:
                return _resp(json.dumps({
                    "results": openalex_results if openalex_results is not None
                    else [{"display_name": "A study topic result one here long",
                           "publication_year": 2024, "doi": None}]}).encode())
            raise AssertionError(f"[seal] 未预期调用: {u[:80]}")
        return disp

    def test_cited_sort_openalex_param(self):
        calls = []

        def disp(req, timeout=None):
            calls.append(req.full_url)
            return _dispatch()(req, timeout)
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen", side_effect=disp):
            refs, notes = vr.discover_refs("topic", 5, 10.0, sort="cited")
        oa = [u for u in calls if "api.openalex.org" in u]
        self.assertTrue(any("cited_by_count:desc" in u for u in oa), oa[:1])
        self.assertTrue(any("PubMed 无被引排序" in n for n in notes),
                        f"PubMed 回退声明: {notes}")

    def test_newest_sort_dual_param(self):
        calls = []

        def disp(req, timeout=None):
            calls.append(req.full_url)
            return _dispatch()(req, timeout)
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen", side_effect=disp):
            refs, notes = vr.discover_refs("topic", 5, 10.0, sort="newest")
        es = [u for u in calls if "esearch" in u]
        self.assertTrue(any("sort=pub_date" in u for u in es), es[:1])
        oa = [u for u in calls if "api.openalex.org" in u]
        self.assertTrue(any("publication_date:desc" in u for u in oa))

    def test_invalid_sort_falls_to_relevance(self):
        calls = []

        def disp(req, timeout=None):
            calls.append(req.full_url)
            return _dispatch()(req, timeout)
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen", side_effect=disp):
            refs, _ = vr.discover_refs("topic", 5, 10.0, sort="bogus")
        oa = [u for u in calls if "api.openalex.org" in u]
        self.assertTrue(all("sort=" not in u for u in oa), "非法排序应回退默认")


if __name__ == "__main__":
    unittest.main()
