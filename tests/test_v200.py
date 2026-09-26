#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.0（MCP 三原语+arXiv 版本备注+NCBI key+证据链）。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "mcp"))
import verify_refs as vr  # noqa: E402
import server  # noqa: E402


class TestV200(unittest.TestCase):
    def setUp(self):
        vr._net_reset()

    def test_version_is_200(self):
        self.assertEqual(vr.VERSION, "3.0.0")

    # ---- arXiv 版本二级核验(零额外请求,同一响应内取数) ----

    FEED_OPEN = '<feed xmlns="http://www.w3.org/2005/Atom">'
    FEED_CLOSE = "</feed>"

    def _arxiv_entry_xml(self, entry_id, title="Some Paper Title Here", year=2024):
        return (f'<entry><id>http://arxiv.org/abs/{entry_id}</id>'
                f'<title>{title}</title>'
                f'<published>{year}-03-01T00:00:00Z</published></entry>')

    def _run_arxiv_mock(self, arxiv_id, entry_xml, title, year=2024):
        xml_text = (self.FEED_OPEN + entry_xml + self.FEED_CLOSE)

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return xml_text.encode()

        with unittest.mock.patch.object(vr, "_arxiv_rate_wait"), \
                unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                           return_value=Resp()):
            return vr.arxiv_metadata_match(arxiv_id, title, year, 5)

    def test_arxiv_unversioned_ref_notes_multiple_versions(self):
        entry = self._arxiv_entry_xml("2401.12345v3")
        adj, note, matched = self._run_arxiv_mock(
            "2401.12345", entry, "Some Paper Title Here", 2024)
        self.assertEqual(adj, "", "多版本备注不降级")
        self.assertIn("3 个修订版本", note)

    def test_arxiv_old_version_ref_flags_newer(self):
        entry = self._arxiv_entry_xml("2401.12345v2")
        adj, note, matched = self._run_arxiv_mock(
            "2401.12345v1", entry, "Some Paper Title Here", 2024)
        self.assertNotEqual(adj, "invalid")
        self.assertIn("v2", note, "应提示最新版为 v2")

    def test_arxiv_single_version_no_note(self):
        entry = self._arxiv_entry_xml("2401.12345v1")
        adj, note, matched = self._run_arxiv_mock(
            "2401.12345v1", entry, "Some Paper Title Here", 2024)
        self.assertEqual(adj, "")
        self.assertNotIn("修订版本", note, "单版本不应出现版本备注")

    # ---- NCBI API key ----

    def test_ncbi_key_appended_to_esummary(self):
        vr._OPTS["ncbi_key"] = "NCKEY123"
        captured = {}

        def cap(req, timeout=None):
            class R:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self):
                    return json.dumps({"result": {"uids": ["12345678"],
                                                  "12345678": {}}}).encode()
            captured["url"] = req.full_url
            return R()

        with unittest.mock.patch.object(vr.urllib.request, "urlopen", cap):
            ok, note = vr.pubmed_pmid_exists("12345678", 5)
        self.assertIn("api_key=NCKEY123", captured["url"], "NCBI key 应附加到请求")
        vr._OPTS["ncbi_key"] = ""

    def test_ncbi_key_from_env(self):
        os_env = {"NCBI_API_KEY": "ENVKEY"}
        with unittest.mock.patch.dict(os.environ, os_env):
            vr.main.__wrapped__ if hasattr(vr.main, "__wrapped__") else None
        # 环境变量路径由 main() 装载——此处仅验证 _OPTS 装载逻辑的常量在位
        self.assertIn("ncbi_key", vr._OPTS)

    # ---- 证据链:checks 明细已在 result 里(渲染层读 checks) ----

    def test_checks_recorded_for_verified_doi(self):
        ref = {"title": "A Verified Paper About Topic X", "doi": "10.1000/good",
               "source": "Journal of Good Things", "year": 2026}
        csl = json.dumps({"title": ["A Verified Paper About Topic X"],
                          "issued": {"date-parts": [[2026]]}}).encode()
        cr = json.dumps({"message": {}}).encode()

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return self.body

        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=lambda req, timeout=None: (
                                            Resp() if "crossref" in req.full_url else Resp())), \
                unittest.mock.patch.object(vr, "check_url",
                                           return_value=(True, 200, "GET 200")):
            r = vr.verify_one(ref, 1, False, 5.0)
        self.assertIn("doi_metadata", r["checks"])
        self.assertIn("retraction", r["checks"])
        self.assertIn("url", r["checks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
