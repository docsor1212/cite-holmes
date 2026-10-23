#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.9.0 测试：F25 综述工作台（--review-kit）+ F26 SKILL 分层 + F27 文档扩容。

F25=核验结果的另一种交付物形态（ADR-0008）：零新增外呼（被引数复用 S2
citation contexts 与 discover 期 OpenAlex cited_by_count）、GB/T 内联与
--export gbt7714 同一构造器、判定语义原样透出（partial 绝不冒充 verified）。
全部 sealed（patch 高层函数/零真网；示例文件为真实公开数据运行产物）。"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


def _sample_rows():
    return [
        {"index": 1, "title": "KUCSKO G, test paper", "verdict": "verified",
         "note": "ok", "needs_human_check": False, "doi": "10.1234/abc",
         "pmid": "", "source": "Nature", "year": 2013,
         "checks": {"doi_metadata": {"adjust": "", "matched": True,
                                     "csl": {"title": "Test paper",
                                             "year": "2013",
                                             "authors": ["KUCSKO G", "MAURER P C",
                                                         "YAO N Y"],
                                             "container": "Nature",
                                             "volume": "500", "issue": "7460",
                                             "page": "54-58"}},
                    "citation_contexts": {"ran": True, "cited_by": 42}}},
        {"index": 2, "title": "A partial entry needing human eyes",
         "verdict": "partial", "note": "缺可选字段", "needs_human_check": True,
         "doi": "", "pmid": "", "source": "", "year": 2020, "checks": {}},
        {"index": 3, "title": "A fabricated looking entry", "verdict": "invalid",
         "note": "编造 DOI", "needs_human_check": False,
         "doi": "", "pmid": "", "source": "", "year": None, "checks": {}},
    ]


class F25_ReviewKit(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_three_sections_and_order(self):
        kit = vr.build_review_kit(_sample_rows(),
                                  [{}, {"title": "y", "_cited_by": 17}, {}],
                                  topic="ion traps")
        assert "综述表格" in kit and "标注书目" in kit and "即贴参考文献表" in kit
        self.assertLess(kit.index("KUCSKO"), kit.index("A partial entry"))
        self.assertLess(kit.index("A partial entry"), kit.index("A fabricated"))

    def test_cited_by_dual_source_and_honest_dash(self):
        kit = vr.build_review_kit(_sample_rows(),
                                  [{}, {"title": "y", "_cited_by": 17}, {}],
                                  topic="t")
        self.assertIn("42（Semantic Scholar）", kit)   # 核验期 S2 优先
        self.assertIn("17（OpenAlex）", kit)           # discover 期回退
        self.assertIn("| 3 | A fabricated looking entry | — | — | — |", kit)

    def test_gbt_inline_matches_export_constructor(self):
        rows = _sample_rows()
        kit = vr.build_review_kit(rows, [], topic="t", cite_date="2026-10-24")
        # 与 _gbt7714_entry 同一构造器：内联行必须逐字等于构造器输出
        self.assertIn(
            "[1] KUCSKO G, MAURER P C, YAO N Y. Test paper[J]. Nature, 2013, "
            "500(7460): 54-58. DOI: 10.1234/abc.", kit)
        # 收录策略=宁缺毋错：partial 无 CSL 不收、invalid 不收
        self.assertEqual(
            sum(1 for ln in kit.splitlines()
                if __import__("re").match(r"\[\d+\] ", ln)), 1)
        self.assertNotIn("A fabricated looking entry[J]", kit)

    def test_verdict_semantics_never_upgraded(self):
        kit = vr.build_review_kit(_sample_rows(), [], topic="t")
        self.assertIn("⚠需人工", kit)
        self.assertIn("查无永不判死", kit)
        self.assertIn("「核验一致」≠「支撑你的论点」", kit)

    def test_zero_cited_is_measured_zero_not_unknown(self):
        # 审计 P2-2 回归锁：被引=0 是测得的零，绝不与未知「—」混写
        rows = [{"index": 1, "title": "A zero cited paper entry", "verdict": "verified",
                 "note": "", "needs_human_check": False, "doi": "10.1/z", "pmid": "",
                 "source": "J", "year": 2024,
                 "checks": {"citation_contexts": {"ran": True, "cited_by": 0}}}]
        refs = [{"title": "z", "_cited_by": 0}]
        kit = vr.build_review_kit(rows, refs, topic="t")
        self.assertIn("0（Semantic Scholar）", kit)
        rows2 = [{"index": 1, "title": "B fallback zero", "verdict": "partial",
                  "note": "", "needs_human_check": False, "doi": "", "pmid": "",
                  "source": "", "year": None, "checks": {}}]
        kit2 = vr.build_review_kit(rows2, refs, topic="t")
        self.assertIn("0（OpenAlex）", kit2)

    def test_empty_batch_no_crash(self):
        kit = vr.build_review_kit([], [], topic="x")
        self.assertIn("共 0 条", kit)
        self.assertIn("本批无满足收录判定的条目", kit)


class F25_ExportRefactor(unittest.TestCase):
    """export_gbt7714 行构造抽为 _gbt7714_entry——导出行为必须逐字节不变。"""

    def setUp(self):
        fresh_engine_state(vr)

    def test_entry_builder_equals_export_output(self):
        import tempfile
        rows = _sample_rows()
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "g.txt")
            vr.export_gbt7714(rows, p)
            exported = open(p, encoding="utf-8").read().strip()
        inline = vr._gbt7714_entry(rows[0], "2026-10-24")
        self.assertEqual(exported, inline)


class F25_DiscoverCitedByPlumbing(unittest.TestCase):
    """discover OpenAlex select 带 cited_by_count → ref._cited_by（密封 mock）。"""

    def setUp(self):
        fresh_engine_state(vr)

    def test_openalex_cited_by_count_stashed(self):
        import io
        oa = {"results": [
            {"display_name": "A very long openalex discovered paper title here",
             "publication_year": 2023, "doi": "10.5555/oa1",
             "primary_location": {"source": {"display_name": "J OA"}},
             "cited_by_count": 321}]}
        pm_ids = {"esearchresult": {"idlist": []}}

        def fake_urlopen(req, timeout):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "api.openalex.org" in url:
                return io.BytesIO(json.dumps(oa).encode())
            if "esearch" in url:
                return io.BytesIO(json.dumps(pm_ids).encode())
            raise AssertionError("意外外呼: " + url)

        with unittest.mock.patch.object(vr, "_urlopen_retry",
                                        side_effect=fake_urlopen), \
             unittest.mock.patch.object(vr, "_cb_open", return_value=False), \
             unittest.mock.patch.object(vr, "_ncbi_rate_wait"), \
             unittest.mock.patch.object(vr, "_cb_record"):
            refs, notes = vr.discover_refs("discovery topic here", 5, 5.0)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].get("_cited_by"), 321)
        self.assertTrue(any("429" not in n for n in notes))


class F25_CLI_Wiring(unittest.TestCase):
    def test_demo_offline_review_kit_file(self):
        import tempfile
        fresh_engine_state(vr)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "rep.md")
            rc = vr.main_with_args(["--demo", "--offline", "--review-kit",
                                    "--out", out])
            self.assertEqual(rc, 0)
            kit_p = out.rsplit(".", 1)[0] + ".review_kit.md"
            self.assertTrue(os.path.exists(kit_p), kit_p)
            kit = open(kit_p, encoding="utf-8").read()
            self.assertIn("文献综述工作台", kit)
            # --review-kit 未显式给 --export 时默认齐活
            self.assertTrue(os.path.exists(out.rsplit(".", 1)[0] + "_GB-T7714.txt"))
            self.assertTrue(os.path.exists(out.rsplit(".", 1)[0] + ".bib"))


class F26_F27_Docs(unittest.TestCase):
    def test_skill_hierarchy_dividers(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertGreaterEqual(en.count("\n---\n"), 4, "四部分隔线缺失")
        self.assertGreaterEqual(zh.count("\n---\n"), 4, "四部分隔线缺失")
        self.assertLess(en.index("30-second quickstart"),
                        en.index("Step 0"), "快速上手未前移")
        self.assertLess(zh.index("30 秒上手"), zh.index("Step 0"))
        for t in (en, zh):
            self.assertIn("review-kit", t)

    def test_sample_real_data_provenance(self):
        p = os.path.join(SK, "examples", "review-kit-sample.md")
        s = open(p, encoding="utf-8").read()
        self.assertIn("真实公开数据", s)
        self.assertIn("--discover", s)
        self.assertIn("文献综述工作台", s)
        self.assertIn("doi.org", s)

    def test_docs_trio(self):
        faq = open(os.path.join(SK, "references", "faq.md"),
                   encoding="utf-8").read()
        self.assertIn("全局网络降级", faq)
        self.assertIn("OPENALEX_API_KEY", faq)
        ap = open(os.path.join(SK, "references", "anti-patterns.md"),
                  encoding="utf-8").read()
        self.assertIn("16. **不要把 partial 条目当\"已核实\"直接搬进综述",
                      ap)
        idx = open(os.path.join(SK, "references", "INDEX.md"),
                   encoding="utf-8").read()
        self.assertIn("--discover \"主题\" --review-kit", idx)
        vd = open(os.path.join(SK, "references", "verification-details.md"),
                  encoding="utf-8").read()
        self.assertIn("--review-kit", vd)
        self.assertTrue(os.path.exists(
            os.path.join(SK, "docs", "adr",
                         "0008-review-kit-reuses-verification-data.md")))
        # 反模式计数更正（文档从 14 条陈旧值同步到 16）
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("16 entries", en)
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("16 条", zh)


if __name__ == "__main__":
    unittest.main()
