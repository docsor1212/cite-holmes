#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.5.0 fast-judge 预筛测试(--fast-judge-url;laya_service.py 形态)
核心纪律:默认关=零行为变化;开=note-only 永不判定/永不设 needs_human_check;
服务失败/无元数据/L4 已判定/invalid 全部弃权。"""
import importlib.util, os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "verify_refs", os.path.join(HERE, "..", "scripts", "verify_refs.py"))
vr = importlib.util.module_from_spec(spec)
sys.modules["verify_refs"] = vr
spec.loader.exec_module(vr)

TITLE = "Lethal autoimmune myocarditis in interferon-gamma receptor-deficient mice"


def _ref(**kw):
    r = {"title": TITLE, "journal": "J Clin Invest",
         "semantic": {"claim": "IFN-gamma receptor deficient mice develop lethal myocarditis",
                      "support": "unclear"}}
    r.update(kw)
    r["semantic_audit"] = vr.build_semantic_audit(r)
    return r


class TestFastJudgeOff(unittest.TestCase):
    def test_default_off_zero_change(self):
        vr._OPTS.update({"fast_judge_url": "", "fast_judge_threshold": 0.95})
        rs = [_ref(verdict="partial")]
        with mock.patch.object(vr, "fast_judge_vote") as mj:
            vr.apply_fast_judge(rs, 5)
        mj.assert_not_called()
        self.assertNotIn("fast_judge", rs[0].get("checks", {}))
        self.assertNotIn("note", rs[0])


class TestFastJudgeOn(unittest.TestCase):
    def setUp(self):
        vr._OPTS.update({"fast_judge_url": "http://127.0.0.1:8793",
                         "fast_judge_threshold": 0.95})

    def test_high_conf_supports_note_only(self):
        rs = [_ref(verdict="partial")]
        with mock.patch.object(vr, "fast_judge_vote",
                               return_value={"label": "SUPPORTS", "prob": 0.98}):
            vr.apply_fast_judge(rs, 5)
        self.assertIn("fast-judge 预筛倾向支持", rs[0].get("note", ""))
        self.assertEqual(rs[0]["verdict"], "partial")          # 永不改判定
        self.assertFalse(rs[0].get("needs_human_check"))        # 永不标人工复核
        self.assertEqual(rs[0]["checks"]["fast_judge"]["action"], "note-only")

    def test_below_threshold_record_no_note(self):
        rs = [_ref(verdict="partial")]
        with mock.patch.object(vr, "fast_judge_vote",
                               return_value={"label": "SUPPORTS", "prob": 0.80}):
            vr.apply_fast_judge(rs, 5)
        self.assertNotIn("fast-judge", rs[0].get("note", ""))
        self.assertEqual(rs[0]["checks"]["fast_judge"]["label"], "SUPPORTS")
        self.assertNotIn("action", rs[0]["checks"]["fast_judge"])

    def test_refutes_no_note_no_flag(self):
        rs = [_ref(verdict="partial")]
        with mock.patch.object(vr, "fast_judge_vote",
                               return_value={"label": "REFUTES", "prob": 0.99}):
            vr.apply_fast_judge(rs, 5)
        self.assertNotIn("note", rs[0])
        self.assertFalse(rs[0].get("needs_human_check"))

    def test_service_down_abstain_silent(self):
        rs = [_ref(verdict="partial")]
        with mock.patch.object(vr, "fast_judge_vote", return_value={"label": None}):
            vr.apply_fast_judge(rs, 5)
        self.assertNotIn("note", rs[0])

    def test_l4_judged_gives_way(self):
        rs = [_ref(verdict="partial")]
        rs[0]["checks"] = {"l4_evidence_cascade": {"judge_verdict": "SUPPORTS"}}
        with mock.patch.object(vr, "fast_judge_vote") as mj:
            vr.apply_fast_judge(rs, 5)
        mj.assert_not_called()

    def test_invalid_skipped(self):
        rs = [_ref(verdict="invalid")]
        with mock.patch.object(vr, "fast_judge_vote") as mj:
            vr.apply_fast_judge(rs, 5)
        mj.assert_not_called()

    def test_no_metadata_abstain(self):
        rs = [_ref(verdict="partial", title="", journal="")]
        with mock.patch.object(vr, "fast_judge_vote") as mj:
            vr.apply_fast_judge(rs, 5)
        mj.assert_not_called()

    def test_supported_semantic_not_targeted(self):
        rs = [_ref(verdict="partial",
                   semantic={"claim": "x supports y", "support": "supported"})]
        rs[0]["semantic_audit"] = vr.build_semantic_audit(rs[0])
        with mock.patch.object(vr, "fast_judge_vote") as mj:
            vr.apply_fast_judge(rs, 5)
        mj.assert_not_called()


class TestFastJudgeVoteInput(unittest.TestCase):
    def test_input_format_matches_training(self):
        vr._OPTS.update({"fast_judge_url": "http://127.0.0.1:8793"})
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = req.data.decode()

            class R:
                def read(self):
                    return b'{"label": "SUPPORTS", "prob": 0.99}'

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            return R()

        with mock.patch.object(vr.urllib.request, "urlopen", fake_urlopen):
            out = vr.fast_judge_vote("claim text", "title\nabstract")
        wire = captured["body"].replace(chr(92) + "n", " ")  # JSON 转义换行还原后断言
        self.assertIn('"SENTENCE: claim text', wire)
        self.assertEqual(out["label"], "SUPPORTS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
