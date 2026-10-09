#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.1.0：L4 证据升级级联主流程接入 + 裁判双端点加固（思考模型三连坑反哺）。"""
import io
import json
import os
import urllib.error
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def R(i, v, **kw):
    d = {"index": i, "title": f"Ref {i}", "verdict": v, "tier": "journal",
         "note": "", "needs_human_check": v == "invalid", "http_status": 200}
    d.update(kw)
    return d


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def sa(claim="Aspirin lowers cardiovascular risk.", support="not_in_source"):
    return {"claim": claim, "support": support, "quote": "", "note": ""}


class TestJudgeHardened(unittest.TestCase):
    def setUp(self):
        self._old = dict(vr._OPTS)
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434/v1"

    def tearDown(self):
        vr._OPTS.clear()
        vr._OPTS.update(self._old)

    def test_t1_reasoning_fallback(self):
        """思考模型 content 空、结论在 reasoning → 兜底解析并注记 degraded。"""
        resp = FakeResp({"choices": [{"message": {"content": "",
                         "reasoning": "Let me think... the evidence contradicts the claim. CONTRADICTS"}}]})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp):
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out["verdict"], "CONTRADICTS")
        self.assertEqual(out.get("degraded"), "parsed-from-reasoning")

    def test_t2_plain_content(self):
        resp = FakeResp({"choices": [{"message": {"content": "NEI\n"}}]})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp):
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out, {"verdict": "NEI"})

    def test_t3_last_occurrence_wins(self):
        """思维链里先顺嘴 SUPPORTS、结论 CONTRADICTS → 取末位。"""
        resp = FakeResp({"choices": [{"message": {
            "content": "First glance suggests SUPPORTS, but the paper reports the opposite. CONTRADICTS"}}]})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp):
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out["verdict"], "CONTRADICTS")

    def test_t4_native_ollama_structured(self):
        """原生端点：JSON content {"label":...} 直取。"""
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        resp = FakeResp({"message": {"content": "{\"label\": \"SUPPORTS\"}"}})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp) as m:
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out["verdict"], "SUPPORTS")
        body = json.loads(m.call_args[0][0].data)
        self.assertFalse(body.get("think", True))
        self.assertEqual(body["format"]["properties"]["label"]["enum"],
                         ["SUPPORTS", "CONTRADICTS", "NEI"])

    def test_t5_native_plain_text_fallback(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        resp = FakeResp({"message": {"content": "CONTRADICTS"}})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp):
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out["verdict"], "CONTRADICTS")

    def test_t6_no_endpoint(self):
        vr._OPTS.pop("judge_url", None)
        out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out, {"verdict": "NEI", "degraded": "no-judge-endpoint"})

    def test_t7_no_think_suffix(self):
        """/v1 分支 prompt 追加 /no_think（qwen3 官方软开关，其它网关无害）。"""
        cap = {}
        def mk(payload, *a, **k):
            cap.update(json.loads(payload.data))
            return FakeResp({"choices": [{"message": {"content": "SUPPORTS"}}]})
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=mk):
            vr.judge_claim_via_endpoint("c", "e")
        self.assertTrue(cap["messages"][0]["content"].rstrip().endswith("/no_think"))

    def test_t8_unparsed_degrades(self):
        resp = FakeResp({"choices": [{"message": {"content": "I cannot decide"}}]})
        with mock.patch.object(vr.urllib.request, "urlopen", return_value=resp):
            out = vr.judge_claim_via_endpoint("c", "e")
        self.assertEqual(out["verdict"], "NEI")
        self.assertTrue(out.get("degraded", "").startswith("unparsed-reply"))


class TestL4Cascade(unittest.TestCase):
    def setUp(self):
        self._old = dict(vr._OPTS)

    def tearDown(self):
        vr._OPTS.clear()
        vr._OPTS.update(self._old)

    def test_t9_zero_config_noop(self):
        """未配 --judge-url：零行为变化（连 checks 键都不出现）。"""
        vr._OPTS.pop("judge_url", None)
        rs = [R(1, "partial", semantic_audit=sa(), pmid="12345678")]
        vr.apply_l4_cascade(rs, 5)
        self.assertNotIn("l4_evidence_cascade", rs[0].get("checks") or {})
        self.assertEqual(rs[0]["note"], "")

    def test_t10_supports_note_only_no_flip(self):
        """裁判 SUPPORTS：只加注记，判定与封顶绝不翻案。"""
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", needs_human_check=True,
                semantic_audit=sa(), pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract", return_value="x" * 2000), \
             mock.patch.object(vr, "retrieve_evidence", return_value=["chunk-a", "chunk-b"]), \
             mock.patch.object(vr, "judge_claim_via_endpoint",
                               return_value={"verdict": "SUPPORTS"}):
            vr.apply_l4_cascade(rs, 5)
        chk = rs[0]["checks"]["l4_evidence_cascade"]
        self.assertEqual(chk["judge_verdict"], "SUPPORTS")
        self.assertEqual(chk["evidence_source"], "pubmed-abstract")
        self.assertEqual(rs[0]["verdict"], "partial")          # 封顶维持
        self.assertTrue(rs[0]["needs_human_check"])            # 维持
        self.assertIn("L4 升级", rs[0]["note"])

    def test_t11_contradicts_flags_human(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(), pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract", return_value="text"), \
             mock.patch.object(vr, "retrieve_evidence", return_value=["c1"]), \
             mock.patch.object(vr, "judge_claim_via_endpoint",
                               return_value={"verdict": "CONTRADICTS"}):
            vr.apply_l4_cascade(rs, 5)
        self.assertTrue(rs[0]["needs_human_check"])

    def test_t12_invalid_untouched(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "invalid", semantic_audit=sa(), pmid="12345678")]
        vr.apply_l4_cascade(rs, 5)
        self.assertNotIn("l4_evidence_cascade", rs[0].get("checks") or {})

    def test_t13_contradicted_support_skipped(self):
        """语义层已判 contradicted 的不升级（L4 只处理 NEI 类状态）。"""
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(support="contradicted"), pmid="12345678")]
        vr.apply_l4_cascade(rs, 5)
        self.assertNotIn("l4_evidence_cascade", rs[0].get("checks") or {})

    def test_t14_no_claim_skipped(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(claim=""), pmid="12345678")]
        vr.apply_l4_cascade(rs, 5)
        self.assertNotIn("l4_evidence_cascade", rs[0].get("checks") or {})

    def test_t15_arxiv_source_used(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(), arxiv="2401.12345v2")]
        with mock.patch.object(vr, "fetch_fulltext", return_value="ft") as mf, \
             mock.patch.object(vr, "retrieve_evidence", return_value=["c"]), \
             mock.patch.object(vr, "judge_claim_via_endpoint",
                               return_value={"verdict": "NEI"}):
            vr.apply_l4_cascade(rs, 5)
        mf.assert_called_once_with("2401.12345v2", 5)   # 版本号剥离在 fetch_fulltext 内部
        self.assertEqual(rs[0]["checks"]["l4_evidence_cascade"]["evidence_source"],
                         "arxiv-fulltext")

    def test_t16_no_text_source_recorded(self):
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(), pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract", return_value=""):
            vr.apply_l4_cascade(rs, 5)
        self.assertEqual(rs[0]["checks"]["l4_evidence_cascade"]["degraded"], "no-text")

    def test_t17_exception_isolated(self):
        """单条异常不拖垮整跑，degraded 留痕。"""
        vr._OPTS["judge_url"] = "http://127.0.0.1:11434"
        rs = [R(1, "partial", semantic_audit=sa(), pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract",
                               side_effect=RuntimeError("boom")):
            vr.apply_l4_cascade(rs, 5)
        self.assertTrue(rs[0]["checks"]["l4_evidence_cascade"]["degraded"]
                        .startswith("cascade-error"))


class TestS2TransportRetry(unittest.TestCase):
    def test_t19_transport_error_retried_once(self):
        """SSL EOF 等传输错误也获得单次重试（弱网出口实测），仍败才返回空。"""
        calls = []
        ok = FakeResp({"data": [{"contexts": ["x"], "intents": [], "isInfluential": False,
                                 "citingPaper": {"title": "T"}}]})
        def flaky(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("SSL EOF")
            return ok
        with mock.patch.object(vr, "_s2_rate_wait"), \
             mock.patch.object(vr.urllib.request, "urlopen", side_effect=flaky), \
             mock.patch.object(vr, "_cb_open", return_value=False), \
             mock.patch.object(vr, "_cb_record"):
            out = vr.s2_citation_contexts("10.1000/x", 5)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out.get("cited_by"), 1)

    def test_t20_transport_error_twice_returns_empty(self):
        calls = []
        def always(*a, **k):
            calls.append(1)
            raise OSError("ssl down")
        always.__name__ = "always"
        with mock.patch.object(vr, "_s2_rate_wait"), \
             mock.patch.object(vr.urllib.request, "urlopen", side_effect=always), \
             mock.patch.object(vr, "_cb_open", return_value=False), \
             mock.patch.object(vr, "_cb_record") as rec:
            out = vr.s2_citation_contexts("10.1000/x", 5)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out, {})
        self.assertTrue(rec.called)  # 仍败才记熔断


class TestEmbedNaNFallback(unittest.TestCase):
    def test_t21_nan_doubling_retry(self):
        """首调 HTTPError 500(真实世界 NaN 表现)→按条加倍重试→成功返回嵌入。"""
        calls = []
        ok_single = FakeResp({"embeddings": [[0.1, 0.2]]})
        state = {"n": 0}

        def seq(req, *a, **k):  # 整批 500→条1单查 ok→条2单查 500→条2加倍 ok
            state["n"] += 1
            if state["n"] in (1, 3):
                raise urllib.error.HTTPError(req.full_url, 500,
                                             "unsupported value: NaN",
                                             {}, io.BytesIO(b"{}"))
            calls.append(json.loads(req.data.decode())["input"])
            return ok_single
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=seq):
            out = vr._embed_ollama(["short claim", "another"])
        self.assertEqual(out, [[0.1, 0.2], [0.1, 0.2]])
        # 流:整批 500→条1单查 ok→条2单查 500(不计)→条2加倍 ok
        self.assertEqual(calls, [["short claim"], ["anotheranother"]])

    def test_t22_total_failure_degrades(self):
        def always(payload, *a, **k):
            raise OSError("down")
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=always):
            self.assertEqual(vr._embed_ollama(["x"]), [])


class TestVersion(unittest.TestCase):
    def test_t18_version_and_catalog(self):
        self.assertEqual(vr.VERSION, "3.11.0")
        cat = None
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn("v3.1.0 接入主流程", src)


if __name__ == "__main__":
    unittest.main()
