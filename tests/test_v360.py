#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.6.0 测试:GB/T 7714-2025 导出(F1)+ --cn Crossref 回源(F2)。
判据与红线:导出仅 verified;注册库 CSL 优先于声称字段;--cn 只加回源不加行为。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def _result(idx, verdict="verified", csl=None, **kw):
    r = {"index": idx, "title": kw.get("title", "A Great Paper About X"),
         "verdict": verdict, "note": "", "needs_human_check": False,
         "year": kw.get("year", 2024), "source": kw.get("source", "J of Tests"),
         "url": kw.get("url", ""), "doi": kw.get("doi", "10.1000/x"),
         "pmid": kw.get("pmid", ""), "arxiv": kw.get("arxiv", ""),
         "checks": {}}
    if csl:
        r["checks"]["doi_metadata"] = {"matched": True, "adjust": "", "csl": csl}
    return r


CSL_J = {"title": "A Great Paper About X", "authors": ["ZHANG S", "LI Q", "WANG F",
          "BROWN A"], "container": "Journal of Tests", "year": 2024,
         "volume": "12", "issue": "3", "page": "100-110"}


class TestGBT7714Export(unittest.TestCase):

    def _export(self, results):
        p = "/tmp/_gbt_test.txt"
        n = vr.export_gbt7714(results, p)
        return n, open(p, encoding="utf-8").read()

    def test_journal_full_fields(self):
        n, txt = self._export([_result(1, csl=CSL_J)])
        self.assertEqual(n, 1)
        self.assertIn("[J].", txt)
        self.assertIn("Journal of Tests, 2024, 12(3): 100-110.", txt)
        self.assertIn("DOI: 10.1000/x.", txt)

    def test_more_than_three_authors_et_al(self):
        n, txt = self._export([_result(1, csl=CSL_J)])
        # 4 位作者 → 前 3 + et al(拉丁题名)
        self.assertIn("ZHANG S, LI Q, WANG F, et al.", txt)
        self.assertNotIn("BROWN", txt)

    def test_cjk_entry_uses_deng(self):
        csl = dict(CSL_J, authors=["张三", "李四", "王五", "赵六"],
                   title="关于某重要机制的研究", container="测试学报")
        n, txt = self._export([_result(1, csl=csl, title="关于某重要机制的研究")])
        self.assertIn("张三, 李四, 王五, 等.", txt)
        self.assertIn("测试学报, 2024, 12(3): 100-110.", txt)

    def test_arxiv_is_ebol_with_cite_date(self):
        r = _result(1, arxiv="2601.01234", doi="", url="", csl=None,
                    title="An arXiv preprint")
        r["checks"] = {}
        n, txt = self._export([r])
        self.assertIn("[EB/OL].", txt)
        self.assertIn("[EB/OL]. (2024).", txt)  # 引用日期行含发布年

    def test_non_verified_excluded(self):
        rows = [_result(1, csl=CSL_J), _result(2, verdict="invalid", csl=CSL_J)]
        n, txt = self._export(rows)
        self.assertEqual(n, 1)
        self.assertNotIn("Unico", txt)

    def test_metadata_consistent_partial_included(self):
        r = _result(1, csl=CSL_J)
        r["verdict"] = "partial"  # 仅缺可选字段(adjust=="")
        r["checks"]["doi_metadata"]["adjust"] = ""
        n, txt = self._export([r])
        self.assertEqual(n, 1)
        self.assertIn("[J].", txt)

    def test_title_disputed_partial_excluded(self):
        r = _result(1, csl=CSL_J)
        r["verdict"] = "partial"
        r["checks"]["doi_metadata"]["adjust"] = "partial"  # 标题相似度存疑
        n, txt = self._export([r])
        self.assertEqual(n, 0)

    def test_fallback_to_claimed_fields_when_no_csl(self):
        r = _result(1, csl=None, title="Claimed Title", source="Claimed J",
                    year=2023)
        r["checks"] = {"doi_metadata": {"matched": True}}
        n, txt = self._export([r])
        self.assertIn("Claimed Title[EB/OL].", txt)  # 无注册 container → 电子资源


class TestCNFallback(unittest.TestCase):

    def setUp(self):
        vr._net_reset()

    def tearDown(self):
        vr._net_reset()
        try:
            vr._OPTS.pop("cn_mode", None)
        except Exception:
            pass

    def _run(self, cn_mode, side_effects):
        vr._OPTS["cn_mode"] = cn_mode
        calls = []

        def fake_urlopen(req, timeout=5):
            calls.append(req.full_url)
            return side_effects(req.full_url)

        with unittest.mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            out = vr.doi_metadata_match("10.1000/real", "a landmark study about x",
                                        2023, 5)
        return out, calls

    @staticmethod
    def _resp(body, code=200):
        import io
        if code != 200:
            raise unittest.mock.Mock(side_effect=Exception("use side_effect"))
        return io.BytesIO(body.encode())

    def test_crossref_fallback_on_cn_mode(self):
        def eff(url):
            if url.startswith("https://doi.org/"):
                raise TimeoutError("CN 出口抖动")
            if url.startswith("https://api.crossref.org/"):
                return self._resp(json.dumps({"message": {
                    "title": ["A landmark study about X"],
                    "issued": {"date-parts": [[2023]]}}}))
            raise AssertionError("unexpected host " + url)
        (adj, note, matched, csl), calls = self._run(True, eff)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertIn("经 Crossref 回源（CN 模式）", note)
        self.assertEqual(csl["title"], "A landmark study about X")
        self.assertTrue(any(u.startswith("https://api.crossref.org/") for u in calls))

    def test_no_fallback_without_cn_mode(self):
        def eff(url):
            if url.startswith("https://doi.org/"):
                raise TimeoutError("抖动")
            raise AssertionError("非 --cn 模式不得回源 Crossref")
        # doi.org 三试×3 次重试 → 全走 fake(会 raise) → 静默失败,无 Crossref 调用
        (adj, note, matched, csl), calls = self._run(False, eff)
        self.assertFalse(matched)
        self.assertIsNone(csl)
        self.assertFalse(any("crossref" in u for u in calls))

    def test_404_still_invalid_in_cn_mode(self):
        import urllib.error
        def eff(url):
            if url.startswith("https://doi.org/"):
                raise urllib.error.HTTPError(url, 404, "not found", {}, io.BytesIO(b""))
            if url.startswith("https://api.crossref.org/"):
                return self._resp(json.dumps({"message": {
                    "title": ["A landmark study about X"],
                    "issued": {"date-parts": [[2023]]}}}))
            raise AssertionError(url)
        # 404=编造证据:CN 模式回源也不得把 DOI.org 404 救回(404 是判定不是传输失败)
        vr._OPTS["cn_mode"] = True
        adj, note, matched, csl = vr.doi_metadata_match(
            "10.9999/bogus", "anything", 2026, 5)
        self.assertEqual(adj, "invalid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
