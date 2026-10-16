#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.1.0 测试：传输失败可观测+短题名反查+撤稿通告分档。

背景（2026-10-16 实测）：
- 代理抖动下 esearch/esummary 传输失败被裸 except 吞成「查无」→ 12+ 条真文献
  被报 unverified 且无任何痕迹）——F1 要求失败可区分、可观测。
- "Scleroderma in children" 类 2 实词规范短题名被 <3 词守卫静默跳过——F2 放行。
- Crossref updated-by 二元判定对 EoC/部分撤稿/撤回完全漏抓——F3 六类分档。
"""
import io
import json
import os
import sys
import unittest
import unittest.mock
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import NCBIMock, fresh_engine_state  # noqa: E402


def _resp(body):
    """带上下文管理器的假响应（crossref works JSON）。"""
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body
    return R()


def _crossref_updated_by(items):
    return json.dumps({"message": {"updated-by": items}}).encode()


class F1_TransportObservable(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_transport_error_observable(self):
        # 传输异常重试耗尽 → net_err=True +「未完成」注记——绝不伪装成查无
        T = "A Title Long Enough For Reverse Lookup Testing"
        calls = {"n": 0}

        def always_fail(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.URLError("tls handshake timeout")
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen", side_effect=always_fail):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                T, "", 2020, 5.0)
        self.assertFalse(matched)
        self.assertTrue(net_err)
        self.assertIn("未完成", note)
        self.assertIn("非查无", note)
        self.assertGreaterEqual(calls["n"], 3, "应有重试（≥3 次尝试）")

    def test_transport_retry_recovers(self):
        # 前两次传输失败第三次成功 → 正常命中（抖动自愈，零可观测负担）
        T = "Mechanisms of Disease Scleroderma Lung Involvement Severe"
        inner = NCBIMock(esearch_hits={5: ["777"]},
                         summaries={"777": {"title": T, "source": "X",
                                            "pubdate": "2020 Jan"}})
        state = {"n": 0}

        def flaky(req, timeout=None):
            state["n"] += 1
            if state["n"] <= 2:
                raise urllib.error.URLError("reset by peer")
            return inner(req, timeout=timeout)
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen", side_effect=flaky):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                T, "", 2020, 5.0)
        self.assertTrue(matched)
        self.assertFalse(net_err)
        self.assertEqual(pmid, "777")

    def test_wiring_records_network_error(self):
        # verify_one 接线：checks.pubmed_reverse.network_error 落盘
        ref = {"title": "Some Identifier Free Medical Reference Title Here",
               "source": "Journal", "year": 2021}
        with unittest.mock.patch.object(
                vr, "pubmed_title_reverse_lookup",
                return_value=("", "PubMed 反查未完成（网络传输失败，已重试）——非查无",
                              False, "", True)), \
             unittest.mock.patch.object(vr, "openalex_title_check",
                                        return_value=""), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertTrue(out["checks"]["pubmed_reverse"]["network_error"])
        self.assertNotEqual(out["verdict"], "verified")

    def test_httperror_no_retry(self):
        # 429 是服务器应答：不进重试，直接走限流可观测注记
        T = "A Title Long Enough For Reverse Lookup Testing"
        err = urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b""))
        calls = {"n": 0}

        def once(req, timeout=None):
            calls["n"] += 1
            raise err
        with unittest.mock.patch("urllib.request.urlopen", side_effect=once):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                T, "", 2020, 5.0)
        self.assertEqual(calls["n"], 1, "HTTPError 绝不重试")
        self.assertIn("限流", note)
        self.assertFalse(net_err)


class F2_ShortTitle(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_two_word_title_hits(self):
        # dogfood 实锤案例：Zulian 2017 "Scleroderma in children"（2 实词）
        T = "Scleroderma in children"
        mock = NCBIMock(esearch_hits={2: ["21694444"]},
                        summaries={"21694444": {
                            "title": "Scleroderma in children",
                            "source": "Best Pract Res Clin Rheumatol",
                            "pubdate": "2017 Oct"}})
        with unittest.mock.patch("urllib.request.urlopen", side_effect=mock):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                T, "Best Pract Res Clin Rheumatol", 2017, 10.0)
        self.assertTrue(matched)
        self.assertEqual(pmid, "21694444")
        self.assertIn("反查核验一致", note)
        self.assertTrue(any(c[0] == "esearch" and c[1].count("[Title]") == 2
                            for c in mock.calls), f"应发 2 词查询: {mock.calls}")

    def test_single_word_still_skipped(self):
        # 单实词噪声过大：维持跳过（[Title] 单词检索会命中数千条）
        mock = NCBIMock(default_ids=["1"])  # 若守卫失效则 mock 返回命中→测试必炸
        with unittest.mock.patch("urllib.request.urlopen", side_effect=mock):
            adj, note, matched, pmid, net_err = vr.pubmed_title_reverse_lookup(
                "On the scleroderma of the", "", 2020, 5.0)
        # "of/on/the" 全停用词 → 实词仅 scleroderma（1 个）→ 守卫跳过
        self.assertFalse(matched)
        self.assertFalse(net_err)
        self.assertEqual(mock.calls, [], "守卫路径必须零外呼")


class F3_RetractionNuance(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_eoc_classified_not_retracted(self):
        body = _crossref_updated_by([
            {"DOI": "10.1111/eoc", "type": "expression-of-concern",
             "updated": {"date-time": "2024-03-01T00:00:00Z"}}])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=_resp(body)):
            ret = vr.crossref_retraction_check("10.1000/eoc", 5)
        self.assertFalse(ret["retracted"])
        self.assertEqual(ret["nature"], "expression_of_concern")
        self.assertEqual(ret["source"], "crossref")
        note = vr._retraction_nature_note(ret["nature"], ret["when"],
                                          ret["notice_doi"], "Crossref/Retraction Watch")
        self.assertIn("Expression of Concern", note)
        self.assertIn("人工复核", note)

    def test_partial_retraction_is_retracted_family(self):
        body = _crossref_updated_by([
            {"DOI": "10.1111/pr", "type": "partial-retraction"}])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=_resp(body)):
            ret = vr.crossref_retraction_check("10.1000/pr", 5)
        self.assertTrue(ret["retracted"])
        self.assertEqual(ret["nature"], "partial_retraction")

    def test_withdrawal_is_retracted_family(self):
        body = _crossref_updated_by([{"DOI": "10.1111/wd", "type": "withdraw"}])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        return_value=_resp(body)):
            ret = vr.crossref_retraction_check("10.1000/wd", 5)
        self.assertTrue(ret["retracted"])
        self.assertEqual(ret["nature"], "withdrawal")

    def test_local_cache_rwdb_strings(self):
        # RWDB dump 的空格式 type 字符串走同一分类器
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump({"10.1000/leoc": {"date": "2024-05-01",
                                        "type": "Expression of Concern",
                                        "reason": "r"}}, f)
            path = f.name
        vr._OPTS["retraction_cache"] = path
        self.addCleanup(vr._OPTS.__setitem__, "retraction_cache", "")
        vr._RETRACTION_CACHE[0] = None  # 强制重载
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=AssertionError("本地命中不走网络")):
            ret = vr.crossref_retraction_check("10.1000/leoc", 5)
        self.assertFalse(ret["retracted"])
        self.assertEqual(ret["nature"], "expression_of_concern")
        self.assertEqual(ret["source"], "local")

    def test_transport_failure_check_failed(self):
        # 传输失败（重试耗尽）→ check_failed=True——「没查成」≠「未撤稿」
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=urllib.error.URLError("timeout")), \
             unittest.mock.patch.object(vr, "_cb_open", return_value=False), \
             unittest.mock.patch.object(vr, "_cb_record"):
            ret = vr.crossref_retraction_check("10.1000/netfail", 5)
        self.assertFalse(ret["retracted"], "绝不因检查失败惩罚引用（家族铁律）")
        self.assertTrue(ret["check_failed"])

    def _verify_with_updated_by(self, items):
        """E2E：DOI 引用 + Crossref updated-by → verify_one 全链。"""
        csl = json.dumps({"title": ["A Flagged Paper About X"],
                          "issued": {"date-parts": [[2020]]}}).encode()
        cr = _crossref_updated_by(items)
        bodies = [csl, cr]

        class Dispatch:
            def __init__(self, bodies):
                self.i = 0
                self.bodies = bodies

            def __call__(self, req, timeout=None):
                b = self.bodies[min(self.i, len(self.bodies) - 1)]
                self.i += 1
                return _resp(b)
        ref = {"title": "A Flagged Paper About X", "doi": "10.1000/flag",
               "source": "journal", "year": 2020}
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=Dispatch(bodies)), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")):
            out = vr.verify_one(ref, 1, False, 5.0)
        return out

    def test_e2e_eoc_downgrades_verified_to_partial(self):
        # 全链达标本可 verified 的引用，EoC 通告必须压回 partial 转人工
        out = self._verify_with_updated_by([
            {"DOI": "10.1111/eoc", "type": "expression-of-concern"}])
        self.assertEqual(out["verdict"], "partial")
        self.assertTrue(out["needs_human_check"])
        self.assertIn("Expression of Concern", out["note"])
        self.assertIn("E_EXPRESSION_OF_CONCERN",
                      vr.derive_error_codes(out))

    def test_e2e_correction_keeps_verified(self):
        # 更正/勘误不降级——仅提示注记（大量论文带勘误，不应制造转人工洪水）
        out = self._verify_with_updated_by([
            {"DOI": "10.1111/corr", "type": "correction"}])
        self.assertEqual(out["verdict"], "verified")
        self.assertFalse(out["needs_human_check"])
        self.assertIn("勘误", out["note"])
        self.assertNotIn("E_EXPRESSION_OF_CONCERN",
                         vr.derive_error_codes(out))

    def test_e2e_check_failed_stays_verified(self):
        # 传输失败绝不惩罚引用（铁律）：可达+元数据一致的引用维持 verified
        csl = json.dumps({"title": ["A Clean Paper About Y"],
                          "issued": {"date-parts": [[2020]]}}).encode()

        class CslThenFail:
            def __init__(self):
                self.i = 0

            def __call__(self, req, timeout=None):
                self.i += 1
                if self.i == 1:
                    return _resp(csl)
                raise urllib.error.URLError("reset")
        ref = {"title": "A Clean Paper About Y", "doi": "10.1000/clean",
               "source": "journal", "year": 2020}
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=CslThenFail()), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")), \
             unittest.mock.patch.object(vr, "_cb_open", return_value=False), \
             unittest.mock.patch.object(vr, "_cb_record"):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "verified")
        self.assertTrue(out["checks"]["retraction"]["check_failed"])
        self.assertIn("撤稿检查未完成", out["note"])


if __name__ == "__main__":
    unittest.main()
