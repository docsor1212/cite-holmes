#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.11.0 测试:清单级伪造画像(F1)/预印本→正式版提示(F2)/逐条完整度评分(F3)。
全部离线(F2 的 S2 调用以 mock 覆盖)。"""
import datetime
import importlib.util
import io
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def _mk(i, title, doi="", year=None, source="", verdict="verified"):
    return {"index": i, "title": title, "doi": doi, "year": year, "source": source,
            "verdict": verdict, "note": "", "checks": {}, "tier": "official",
            "http_status": 200, "needs_human_check": False}


class TestProfileBibliography(unittest.TestCase):
    """F1:清单级伪造画像（纯本地,只建议不判定）。"""

    def test_serial_cluster_detected(self):
        rs = [_mk(1, "Paper A", "10.9999/batch2024001"),
              _mk(2, "Paper B", "10.9999/batch2024002"),
              _mk(3, "Paper C", "10.9999/batch2024004"),
              _mk(4, "Real paper", "10.1111/j.1234-5678.2010.01234.x")]
        prof = vr.profile_bibliography(rs)
        kinds = [f["kind"] for f in prof["flags"]]
        self.assertIn("serial_cluster", kinds)
        det = next(f["detail"] for f in prof["flags"] if f["kind"] == "serial_cluster")
        self.assertIn("batch", det)
        self.assertIn("2024001", det)

    def test_future_year_and_year_concentration(self):
        rs = [_mk(i, f"P{i}", f"10.2/x{i}", year=2031 if i == 1 else 2024)
              for i in range(1, 10)]
        kinds = [f["kind"] for f in vr.profile_bibliography(rs)["flags"]]
        self.assertIn("future_year", kinds)
        self.assertIn("year_concentration", kinds)

    def test_source_concentration_and_bare_refs(self):
        rs = [_mk(i, f"P{i}", "", source="Journal X" if i <= 6 else f"J{i}")
              for i in range(1, 11)]
        kinds = [f["kind"] for f in vr.profile_bibliography(rs)["flags"]]
        self.assertIn("source_concentration", kinds)
        self.assertIn("bare_refs", kinds)

    def test_clean_bibliography_no_flags(self):
        y = datetime.date.today().year
        rs = [_mk(i, f"Real Study {i} on Diverse Topics", f"10.4{i % 9}/d{i:04d}7",
                  year=y - i % 7, source=f"Journal {i % 5}") for i in range(1, 10)]
        self.assertEqual(vr.profile_bibliography(rs)["flags"], [])

    def test_too_few_refs_skipped(self):
        self.assertEqual(vr.profile_bibliography([_mk(1, "A", "10.1/x")])["flags"], [])

    def test_verdicts_untouched(self):
        rs = [_mk(i, f"P{i}", f"10.2/x{i}", year=2031 if i == 1 else 2024)
              for i in range(1, 10)]
        vr.profile_bibliography(rs)
        for r in rs:
            self.assertEqual(r["verdict"], "verified")
            self.assertEqual(r["note"], "")

    def test_render_md_profile_section(self):
        rs = [_mk(i, f"P{i}", f"10.1234/batch202400{i}", year=2031 if i <= 3 else 2020)
              for i in range(1, 6)]
        md = vr.render_md(rs, offline=True)
        self.assertIn("## 清单画像", md)
        self.assertIn("serial_cluster", md)

    def test_render_md_no_profile_section_when_clean(self):
        y = datetime.date.today().year
        rs = [_mk(i, f"Real Study {i} on Diverse Topics", f"10.4{i % 9}/d{i:04d}7",
                  year=y - i % 7, source=f"Journal {i % 5}") for i in range(1, 10)]
        self.assertNotIn("## 清单画像", vr.render_md(rs, offline=True))

    def test_json_doc_carries_profile(self):
        rs = [_mk(i, f"P{i}", f"10.2/x{i}", year=2031 if i <= 3 else 2020)
              for i in range(1, 6)]
        self.assertTrue(vr.profile_bibliography(rs)["flags"])


class TestCompleteness(unittest.TestCase):
    """F3:逐条完整度评分（纯本地,只读）。"""

    def test_full_csl_scores_100(self):
        r = _mk(1, "T", "10.1/x")
        r["checks"] = {"doi_metadata": {"csl": {
            "authors": ["A B"], "container": "Nature", "year": 2020,
            "volume": "500", "issue": "1", "page": "54-58"}}}
        c = vr.completeness_for_ref(r)
        self.assertEqual(c["score"], 100)
        self.assertEqual(c["missing"], [])

    def test_partial_csl(self):
        r = _mk(2, "T", "10.1/y")
        r["checks"] = {"doi_metadata": {"csl": {"authors": ["X Y"], "container": "",
                                                "year": None}}}
        c = vr.completeness_for_ref(r)
        self.assertEqual(c["score"], 30)
        self.assertIn("刊名", c["suggestion"])
        self.assertIn("页码", c["suggestion"])

    def test_no_csl_unknown(self):
        self.assertIsNone(vr.completeness_for_ref(_mk(3, "T"))["score"])

    def test_annotate_writes_verified_only(self):
        r1 = _mk(1, "T", "10.1/x")
        r1["checks"] = {"doi_metadata": {"csl": {"authors": ["A"], "container": "C",
                                                 "year": 2020, "volume": "1",
                                                 "issue": "1", "page": "1"}}}
        r2 = _mk(2, "T", "10.1/y", verdict="partial")
        r2["checks"] = r1["checks"]
        n = vr.annotate_completeness([r1, r2])
        self.assertEqual(n, 1)
        self.assertEqual(r1["completeness"]["score"], 100)
        self.assertNotIn("completeness", r2)


class TestPreprintUpgrades(unittest.TestCase):
    """F2:预印本→正式版提示（注记级,失败静默）。"""

    def test_annotates_journal_version(self):
        r = _mk(1, "Preprint Paper", "")
        r["arxiv"] = "2401.00001"
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps({
                "externalIds": {"DOI": "10.5555/journal-ver", "ArXiv": "2401.00001"},
                "venue": "Nature", "year": 2025}).encode())
            mu.return_value.code = 200
            n = vr.annotate_preprint_upgrades([r], 3.0)
        self.assertEqual(n, 1)
        self.assertIn("正式发表", r["note"])
        self.assertIn("10.5555/journal-ver", r["note"])
        self.assertIn("建议引用正式版", r["note"])
        self.assertEqual(r["verdict"], "verified")  # 判定不变

    def test_skips_when_doi_present_or_not_verified(self):
        r1 = _mk(2, "X", "10.1/has")
        r1["arxiv"] = "2401.00002"
        r2 = _mk(3, "Y", "")
        r2["arxiv"] = "2401.00003"
        r2["verdict"] = "partial"
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            n = vr.annotate_preprint_upgrades([r1, r2], 3.0)
            mu.assert_not_called()
        self.assertEqual(n, 0)

    def test_silent_on_transport_failure(self):
        r = _mk(4, "Z", "")
        r["arxiv"] = "2401.00004"
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=OSError("offline")):
            n = vr.annotate_preprint_upgrades([r], 0.2)
        self.assertEqual(n, 0)
        self.assertEqual(r["note"], "")

    def test_silent_on_429(self):
        r = _mk(5, "W", "")
        r["arxiv"] = "2401.00005"
        import urllib.error
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=urllib.error.HTTPError(
                                     "u", 429, "rate", {}, io.BytesIO(b""))):
            n = vr.annotate_preprint_upgrades([r], 3.0)
        self.assertEqual(n, 0)
        self.assertEqual(r["note"], "")

    def test_http_errors_never_trip_circuit_breaker(self):
        # 审计修复回归:HTTP 层失败（404 未收录/429 限流）不触发熔断——
        # 连续多次也不断（api.semanticscholar.org 须保持对 s2_doi_confirm 可用）
        rs = []
        for i in range(5):
            r = _mk(10 + i, f"P{i}", "")
            r["arxiv"] = f"2401.0001{i}"
            rs.append(r)
        import urllib.error
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=urllib.error.HTTPError(
                                     "u", 404, "not found", {}, io.BytesIO(b""))):
            n = vr.annotate_preprint_upgrades(rs, 3.0)
        self.assertEqual(n, 0)
        cb = vr._CB.get("https://api.semanticscholar.org")
        self.assertTrue(cb is None or not cb.get("open"),
                        f"断路器被误开: {cb}")

    def test_venue_truncated(self):
        # 审计观察修复:外部 venue 截断,注记长度有界
        r = _mk(6, "V", "")
        r["arxiv"] = "2401.00006"
        huge_venue = "超" * 200
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps({
                "externalIds": {"DOI": "10.7/jv"}, "venue": huge_venue,
                "year": 2025}).encode())
            mu.return_value.code = 200
            vr.annotate_preprint_upgrades([r], 3.0)
        self.assertIn("正式发表", r["note"])
        self.assertLess(len(r["note"]), 400)

    def test_offline_guard_in_main(self):
        # offline 显式守卫:main 批处理对 preprint 提示有 offline 短路
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn("0 if args.offline else annotate_preprint_upgrades", src)


class TestVersionAndDocs(unittest.TestCase):
    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "3.11.0")

    def test_capability_matrix_lists_new(self):
        cap = vr.capability_matrix()
        self.assertTrue(any("清单画像" in x for x in cap["caught"]))
        self.assertTrue(any("预印本" in x for x in cap["caught"]))

    def test_skill_md_updated(self):
        t = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("version: 3.11.0", t)
        self.assertIn("bibliography profiling", t.lower())
        self.assertIn("preprint", t.lower())

    def test_skill_zh_updated(self):
        t = open(os.path.join(HERE, "..", "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("清单画像", t)
        self.assertIn("预印本", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
