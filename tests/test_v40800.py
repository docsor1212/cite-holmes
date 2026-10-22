#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.8.0 测试：EB/OL 落地页题名对照（F23）。

背景（v4.6.0 dogfood 残留 + v4.7.0 发车实录）：说明书/FDA 标签/共识类 EB/OL
引用 v4.6.0 起有了 URL 可达判据，但「这条 URL 讲的就是这篇」仍无证据——
F23 落地页题名对照补上（确认→partial 转人工，存在性证据不升 verified）。
F24 轮询窗口加长（3×180→4×240）落在发布工具 release.py 的链模板里——本包
之外，包内不可断言（不在本文件做覆盖声明）。
全部 sealed（_fetch_landing_html 直接 patch，opener 不触网）。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


class F23_LandingTitleCheck(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_title_match_confirmed(self):
        html = "<html><head><title>Cetirizine Hydrochloride Oral Solution - DailyMed</title></head></html>"
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html):
            note, confirmed = vr.landing_title_check(
                "https://dailymed.nlm.nih.gov/x",
                "Cetirizine hydrochloride oral solution, USP prescribing information",
                10.0)
        self.assertTrue(confirmed)
        self.assertIn("落地页题名对照一致", note)

    def test_approx_not_confirmed(self):
        html = "<html><title>Completely different page about pharmacy rules</title></html>"
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html):
            note, confirmed = vr.landing_title_check(
                "https://x.example.com", "A very different claimed title text", 10.0)
        self.assertFalse(confirmed)
        self.assertEqual(note, "")

    def test_fetch_failure_silent(self):
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=None):
            note, confirmed = vr.landing_title_check("https://x.example.com",
                                                     "Some claimed title here", 10.0)
        self.assertEqual((note, confirmed), ("", False))

    def test_og_title_candidate(self):
        html = ('<html><head><meta property="og:title" '
                'content="儿科常用H1抗组胺药处方审核专家共识"/></head></html>')
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html):
            note, confirmed = vr.landing_title_check(
                "https://x.example.com", "儿科常用H1抗组胺药处方审核专家共识", 10.0)
        self.assertTrue(confirmed)

    def test_intra_word_hyphen_never_cut(self):
        # 审计 P1 回归锁：词内连字符（COVID-19/anti-TNF/State-of-the-Art
        # 生物医学高频形态）绝不开削——页面题名与声称题名逐字相同必须 confirmed
        for page_title in ("COVID-19 vaccines: WHO guideline",
                           "Anti-TNF agents in rheumatoid arthritis",
                           "State-of-the-Art Review: psoriasis therapy"):
            html = f"<html><title>{page_title}</title></html>"
            with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                            return_value=html):
                note, confirmed = vr.landing_title_check(
                    "https://x.example.com", page_title, 10.0)
            self.assertTrue(confirmed, f"连字符题名被误削: {page_title}")

    def test_spaced_brand_suffix_still_stripped(self):
        # 带空白的品牌后缀照常剥离——词内连字符与后缀分隔互不干扰
        html = ("<html><title>Anti-TNF agents in rheumatoid arthritis "
                "- DailyMed</title></html>")
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html):
            note, confirmed = vr.landing_title_check(
                "https://dailymed.nlm.nih.gov/y",
                "Anti-TNF agents in rheumatoid arthritis", 10.0)
        self.assertTrue(confirmed)


class F23_Wiring(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_partial_evidence_annotation(self):
        # EB/OL 靶型：官方层可达但缺字段 → partial；落地页对照一致补强证据注记
        # （不改判定——partial 仍转人工）
        ref = {"title": "Cetirizine hydrochloride oral solution, USP label",
               "url": "https://dailymed.nlm.nih.gov/dailymed/x", "year": 2026}
        html = ("<html><head><title>Cetirizine Hydrochloride Oral Solution, "
                "USP Label - DailyMed</title></head></html>")
        with unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")), \
             unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html), \
             unittest.mock.patch.object(vr, "openalex_title_check",
                                        return_value=""), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertEqual(out["verdict"], "partial",
                         f"{out['verdict']} / {out['note'][:160]}")
        self.assertTrue(out["checks"]["landing"]["confirmed"])
        self.assertIn("落地页题名对照一致", out["note"])

    def test_unconfirmed_annotation_only(self):
        ref = {"title": "A claimed title entirely unlike the page below",
               "url": "https://dailymed.nlm.nih.gov/page", "year": 2026}
        html = "<html><title>Something totally unrelated lives here</title></html>"
        with unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")), \
             unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        return_value=html), \
             unittest.mock.patch.object(vr, "openalex_title_check",
                                        return_value=""), \
             unittest.mock.patch.object(vr, "s2_title_confirm",
                                        return_value=(False, "")):
            out = vr.verify_one(ref, 1, False, 5.0)
        self.assertFalse((out["checks"].get("landing") or {}).get("confirmed"))
        self.assertNotIn("落地页题名对照一致", out["note"])

    def test_offline_never_lands(self):
        ref = {"title": "Cetirizine hydrochloride oral solution, USP label",
               "url": "https://dailymed.nlm.nih.gov/x", "year": 2026}
        with unittest.mock.patch.object(vr, "_fetch_landing_html",
                                        side_effect=AssertionError("seal")):
            out = vr.verify_one(ref, 1, True, 5.0)  # offline
        self.assertNotIn("landing", out["checks"])


if __name__ == "__main__":
    unittest.main()
