#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.3.0 测试：OpenAlex 找锚→DOI.org 验锚链 + 判死前桥接拯救 + RWDB 索引构建器。

背景（2026-10-18 TA 表在线甄别实锤）：39 条候选中文医学期刊映射仅 18 条有
PubMed 收录——非 MEDLINE 期刊与万方系期刊的引用此前无任何官方核验通路。
F9 把 OpenAlex 从「只确认」升级为「找锚→验锚」：聚合库只当索引，判定证据
全部来自 DOI.org 权威核验（含撤稿检测，锚定通路不绕开安全检查）。
全部 sealed（零真网依赖）。"""
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


def _dispatch(openalex_results=None, csl=None, retraction_items=None,
              s2_empty=True):
    """URL 特征派发：eutils esearch 空 / openalex works / doi.org CSL /
    crossref updated-by / s2 空。"""
    def disp(req, timeout=None):
        u = req.full_url
        if "esearch" in u:
            return _resp(json.dumps({"esearchresult": {"count": "0",
                                                       "idlist": []}}).encode())
        if "api.openalex.org" in u:
            return _resp(json.dumps({"results": openalex_results or []}).encode())
        if "api.crossref.org" in u:
            # 撤稿 works 记录（注意先于 DOI.org 判定：works/10.x 也含 ".org/works/10."
            # 形态，宽匹配会把撤稿查询喂成 CSL——首跑实证）
            return _resp(json.dumps({"message": {"updated-by":
                                                 retraction_items or []}}).encode())
        if "doi.org" in u:
            if csl is not None:
                return _resp(json.dumps(csl).encode())
            return _resp(b"{}")
        if "api.semanticscholar.org" in u:
            return _resp(b'{"data": []}')
        raise AssertionError(f"[seal] 未预期的网络调用: {u[:100]}")
    return disp


class F9_OpenAlexAnchorChain(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_works_lookup_confirmed_with_doi(self):
        results = [{"display_name": "A study about pediatric wheezing systems",
                    "publication_year": 2024, "doi": "https://doi.org/10.1000/abc"}]
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex_results=results)):
            note, confirmed, doi = vr.openalex_works_lookup(
                "A study about pediatric wheezing systems", 2024, 10.0)
        self.assertTrue(confirmed)
        self.assertEqual(doi, "10.1000/abc")
        self.assertIn("OpenAlex 书目确认存在", note)

    def test_works_lookup_year_mismatch_not_confirmed(self):
        results = [{"display_name": "A study about pediatric wheezing systems",
                    "publication_year": 2010, "doi": "https://doi.org/10.1000/abc"}]
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex_results=results)):
            note, confirmed, doi = vr.openalex_works_lookup(
                "A study about pediatric wheezing systems", 2024, 10.0)
        self.assertFalse(confirmed)
        self.assertEqual(doi, "")

    def test_e2e_anchor_chain_verified(self):
        # 无标识符中文系引用：反查/锚定无通路 → OpenAlex 找锚 → DOI.org 一致 →
        # verified + DOI 锚回填 + 撤稿干净
        ref = {"title": "A study about pediatric wheezing systems and care",
               "source": "J Scleroderma Relat Disord", "year": 2024}
        openalex = [{"display_name": "A study about pediatric wheezing systems and care",
                     "publication_year": 2024,
                     "doi": "https://doi.org/10.1000/anchor"}]
        csl = {"title": ["A study about pediatric wheezing systems and care"],
               "issued": {"date-parts": [[2024]]}}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex, csl)), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch("time.sleep"):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "verified",
                         f"{out['verdict']} / {out['note'][:200]}")
        self.assertEqual(out["doi"], "10.1000/anchor")
        self.assertTrue(out["checks"]["doi_metadata"].get("matched"))
        self.assertEqual(out["checks"]["doi_metadata"].get("via"),
                         "openalex-anchor")
        self.assertFalse(out["checks"]["retraction"].get("retracted"))

    def test_e2e_anchor_chain_retracted_capped_partial(self):
        # 锚定通路的 DOI 命中撤稿记录 → 不得 verified（安全检查不绕开）
        ref = {"title": "A study about pediatric wheezing systems and care",
               "source": "J Scleroderma Relat Disord", "year": 2024}
        openalex = [{"display_name": "A study about pediatric wheezing systems and care",
                     "publication_year": 2024,
                     "doi": "https://doi.org/10.1000/anchor"}]
        csl = {"title": ["A study about pediatric wheezing systems and care"],
               "issued": {"date-parts": [[2024]]}}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(
                                     openalex, csl,
                                     retraction_items=[{"DOI": "10.1/r",
                                                        "type": "retraction"}])), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch("time.sleep"):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "partial")
        self.assertTrue(out["checks"]["retraction"].get("retracted"))

    def test_e2e_anchor_chain_title_mismatch_invalid(self):
        # OpenAlex 找到锚但 DOI.org 登记题名与声称不符（同语言）→ invalid——
        # 「存在相似条目」不放行错引（A2 同族防护在链式通路的延续）
        ref = {"title": "A totally different claimed title about kidney health",
               "source": "Journal X", "year": 2024}
        openalex = [{"display_name": "A totally different claimed title about kidney health",
                     "publication_year": 2024,
                     "doi": "https://doi.org/10.1000/anchor"}]
        csl = {"title": ["Registered paper about something else entirely here"],
               "issued": {"date-parts": [[2024]]}}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex, csl)), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch("time.sleep"):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "invalid")

    def test_confirmed_without_doi_caps_partial(self):
        # 无 DOI 候选 → 维持 v1.8 语义：确认→partial 转人工
        ref = {"title": "A study about pediatric wheezing systems and care",
               "source": "Journal X", "year": 2024}
        openalex = [{"display_name": "A study about pediatric wheezing systems and care",
                     "publication_year": 2024, "doi": None}]
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex)), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "partial")
        self.assertTrue(out["needs_human_check"])

    def test_wrapper_backward_compat(self):
        # openalex_title_check 薄包装：旧调用方面（无 doi 字段的罐体）注记不变
        results = [{"display_name": "A long enough title about testing things here",
                    "publication_year": 2024}]
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex_results=results)):
            note = vr.openalex_title_check(
                "A long enough title about testing things here", 10.0)
        self.assertIn("OpenAlex 书目确认存在", note)


    def test_e2e_anchor_chain_cross_lang_partial(self):
        # 主打场景：中文声称题名 → OpenAlex 确认（库内即中文题名）→ 候选 DOI →
        # DOI.org 登记英文题名 → 跨族守卫/桥接 miss → partial 转人工，绝不 invalid
        ref = {"title": "儿童喘息性疾病的长期管理策略与随访要点",
               "source": "中华儿科杂志", "year": 2024}
        openalex = [{"display_name": "儿童喘息性疾病的长期管理策略与随访要点",
                     "publication_year": 2024,
                     "doi": "https://doi.org/10.1000/cn-anchor"}]
        csl = {"title": ["Long-term management and follow-up of wheezing "
                         "disorders in children"],
               "issued": {"date-parts": [[2024]]}}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=_dispatch(openalex, csl)), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge",
                                        return_value=""), \
             unittest.mock.patch("time.sleep"):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "partial",
                         f"跨语言链应封顶 partial: {out['verdict']} / {out['note'][:160]}")
        self.assertTrue(out["needs_human_check"])
        self.assertNotEqual(out["verdict"], "invalid")


class F11_PreInvalidBridge(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _esummary(self, title, doi="10.3760/cma.j.x"):
        return json.dumps({"result": {"uids": ["39429074"], "39429074": {
            "title": title, "fulljournalname": "X", "pubdate": "2024",
            "articleids": [{"idtype": "doi", "value": doi}]}}})

    def test_same_family_low_sim_bridge_hit_rescues(self):
        # 拼音/译名声称 vs 登记英文题名（同族低 sim）→ 桥接命中 → 一致
        es = self._esummary("Clinical practice guideline for bronchiolitis")
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=_resp(es)), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge",
                                        return_value="Crossref original-title 一致"):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "Er tong mao xi zhi qi yan guan li lin chuang zhi nan",
                "X", 2024, 5)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertIn("跨语言桥接", note)

    def test_same_family_low_sim_bridge_miss_still_invalid(self):
        # 桥接未命中 → 同语言假标题判死不弱化（拼接防护保持）
        es = self._esummary("Clinical practice guideline for bronchiolitis")
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=_resp(es)), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge",
                                        return_value=""):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "Completely unrelated title words about renal diet",
                "X", 2024, 5)
        self.assertEqual(adj, "invalid")

    def test_no_registry_doi_skips_bridge(self):
        es = self._esummary("Clinical practice guideline for bronchiolitis", doi="")
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=_resp(es)), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge",
                                        side_effect=AssertionError("无登记 DOI 不得走桥接")):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "Completely unrelated title words about renal diet",
                "X", 2024, 5)
        self.assertEqual(adj, "invalid")


class RWDBCacheBuilder(unittest.TestCase):
    def test_build_index_priority_and_shape(self):
        sys.path.insert(0, os.path.join(HERE, "..", "tools"))
        import build_retraction_cache as brc
        rows = [
            {"OriginalPaperDOI": "10.1/A", "RetractionNature": "Correction",
             "RetractionDate": "2020-01-01", "RetractionReason": "minor"},
            {"OriginalPaperDOI": "10.1/A", "RetractionNature": "Retraction",
             "RetractionDate": "2021-06-01", "RetractionReason": "data"},
            {"OriginalPaperDOI": "10.1/B", "RetractionNature": "Expression of Concern",
             "RetractionDate": "2022-03-03", "RetractionReason": "concern"},
            {"OriginalPaperDOI": "", "RetractionNature": "Retraction",
             "RetractionDate": "2020", "RetractionReason": "no doi"},
        ]
        idx = brc.build_index(rows)
        self.assertEqual(len(idx), 2)
        # 同 DOI 多通告：撤稿族信息量优先
        self.assertEqual(idx["10.1/a"]["type"], "Retraction")
        self.assertEqual(idx["10.1/a"]["date"], "2021-06-01")
        self.assertEqual(idx["10.1/b"]["type"], "Expression of Concern")
        # 与 v4.1.0 分档分类器互通
        self.assertEqual(vr._retraction_classify(idx["10.1/b"]["type"]),
                         "expression_of_concern")
        self.assertEqual(vr._retraction_classify(idx["10.1/a"]["type"]), "retraction")


if __name__ == "__main__":
    unittest.main()
