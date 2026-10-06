#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.3.0：L2 NLI 第三票（nli_vote/aggregate_l2/L4 接线/contested 不翻案）。"""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def R(i, v, **kw):
    d = {"index": i, "title": f"Ref {i}", "verdict": v, "tier": "journal",
         "note": "", "needs_human_check": False, "http_status": 200}
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


class TestNliClient(unittest.TestCase):
    def setUp(self):
        self._old = dict(vr._OPTS)
    def tearDown(self):
        vr._OPTS.clear(); vr._OPTS.update(self._old)

    def test_t1_unconfigured_none(self):
        vr._OPTS.pop("nli_url", None)
        self.assertEqual(vr.nli_vote("p", "h"), {"label": None})

    def test_t2_service_ok(self):
        vr._OPTS["nli_url"] = "http://127.0.0.1:8792"
        with mock.patch.object(vr.urllib.request, "urlopen",
                               return_value=FakeResp({"label": "contradiction",
                                                      "margin": 0.6})):
            out = vr.nli_vote("premise", "hypothesis")
        self.assertEqual(out["label"], "contradiction")

    def test_t3_service_down_degrades(self):
        vr._OPTS["nli_url"] = "http://127.0.0.1:9"
        def boom(req, timeout=None):
            raise OSError("down")
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=boom):
            self.assertEqual(vr.nli_vote("p", "h"), {"label": None})


class TestAggregateL2(unittest.TestCase):
    def test_t4_agree_high(self):
        self.assertEqual(vr.aggregate_l2("SUPPORTS", {"label": "entailment"}),
                         {"confidence": "high", "nli": "SUPPORTS"})

    def test_t5_conflict_contested(self):
        out = vr.aggregate_l2("SUPPORTS", {"label": "contradiction"})
        self.assertEqual(out["confidence"], "contested")
        self.assertEqual(out["nli"], "CONTRADICTS")

    def test_t6_abstain_single(self):
        self.assertEqual(vr.aggregate_l2("SUPPORTS", {"label": "entailment",
                                                      "abstain": True})["confidence"], "single")
        self.assertEqual(vr.aggregate_l2("NEI", {})["confidence"], "single")

    def test_t7_unknown_label(self):
        self.assertEqual(vr.aggregate_l2("NEI", {"label": "weird"})["confidence"], "single")


class TestL4NliWiring(unittest.TestCase):
    def setUp(self):
        self._old = dict(vr._OPTS)
        vr._OPTS.update({"judge_url": "http://127.0.0.1:11434",
                         "nli_url": "http://127.0.0.1:8792"})
    def tearDown(self):
        vr._OPTS.clear(); vr._OPTS.update(self._old)

    def _run(self, nli_label, judge_verdict):
        rs = [R(1, "partial", semantic_audit={"claim": "c", "support": "not_in_source",
                                              "quote": "", "note": ""},
                pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract", return_value="x" * 2000), \
             mock.patch.object(vr, "retrieve_evidence", return_value=["c1"]), \
             mock.patch.object(vr, "judge_claim_via_endpoint",
                               return_value={"verdict": judge_verdict}), \
             mock.patch.object(vr, "nli_vote",
                               return_value={"label": nli_label, "margin": 0.5}):
            vr.apply_l4_cascade(rs, 5)
        return rs[0]

    def test_t8_contested_flags_human_not_flip(self):
        r = self._run("contradiction", "SUPPORTS")
        self.assertTrue(r["needs_human_check"])
        self.assertIn("L2 分歧", r["note"])
        self.assertEqual(r["verdict"], "partial")  # 判定不翻案

    def test_t9_agree_no_contest(self):
        r = self._run("entailment", "SUPPORTS")
        self.assertFalse(r["needs_human_check"])
        rec = r["checks"]["l4_evidence_cascade"]
        self.assertEqual(rec["l2_confidence"], "high")
        self.assertEqual(rec["nli"], "SUPPORTS")

    def test_t10_no_nli_no_keys(self):
        vr._OPTS.pop("nli_url", None)
        rs = [R(1, "partial", semantic_audit={"claim": "c", "support": "not_in_source",
                                              "quote": "", "note": ""},
                pmid="12345678")]
        with mock.patch.object(vr, "fetch_pubmed_abstract", return_value="t"), \
             mock.patch.object(vr, "retrieve_evidence", return_value=["c"]), \
             mock.patch.object(vr, "judge_claim_via_endpoint",
                               return_value={"verdict": "SUPPORTS"}):
            vr.apply_l4_cascade(rs, 5)
        rec = rs[0]["checks"]["l4_evidence_cascade"]
        self.assertNotIn("nli", rec)
        self.assertNotIn("l2_confidence", rec)

    def test_t11_version(self):
        self.assertEqual(vr.VERSION, "3.7.0")


if __name__ == "__main__":
    unittest.main()
