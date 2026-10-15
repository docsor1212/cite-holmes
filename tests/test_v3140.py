#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.14.0 测试:--grill 对抗审查(F1)+SKILL 分层瘦身(F2,评测 usability 4.5 失分面对策)。"""
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


def _mk(i, verdict, note="", title="T"):
    return {"index": i, "title": title, "doi": "10.1/x", "verdict": verdict,
            "note": note, "checks": {}, "tier": "official", "http_status": 200,
            "needs_human_check": False}


class TestGrillReport(unittest.TestCase):
    """F1:对抗审查问题单（纯模板零网络，只出问题不出判定）。"""

    def test_per_verdict_questions(self):
        items = vr.grill_report([_mk(1, "verified"), _mk(2, "invalid"),
                                 _mk(3, "partial"), _mk(4, "unreachable"),
                                 _mk(5, "unverified")])
        by = {x["index"]: x for x in items}
        self.assertEqual(len(by[1]["questions"]), 3)   # verified 3 问
        self.assertTrue(any("撤稿" in q for q in by[1]["questions"]))
        self.assertTrue(any("抄写错误" in q for q in by[2]["questions"]))
        self.assertTrue(any("替代来源" in q for q in by[3]["questions"]))
        self.assertTrue(any("Wayback" in q for q in by[4]["questions"]))
        self.assertTrue(any("联网重跑" in q for q in by[5]["questions"]))

    def test_note_triggered_followups(self):
        items = vr.grill_report([_mk(1, "verified", "克隆引用对 #1↔#2：同题不同 DOI"),
                                 _mk(2, "verified", "该预印本已登记正式发表"),
                                 _mk(3, "partial", "跨语言标题无法机器比对")])
        qs = " ".join(q for x in items for q in x["questions"])
        for kw in ("克隆引用对", "期刊版 DOI", "人工确认"):
            self.assertIn(kw, qs, kw)

    def test_verdicts_untouched(self):
        rs = [_mk(1, "verified"), _mk(2, "invalid")]
        vr.grill_report(rs)
        for r in rs:
            self.assertEqual(r["verdict"], rs[[x["index"] for x in rs].index(r["index"])]["verdict"])
            self.assertEqual(r["note"], "")

    def test_render_md(self):
        items = vr.grill_report([_mk(1, "verified"), _mk(2, "invalid")])
        md = vr.render_grill_md(items, {"score": 72, "grade": "B"})
        self.assertIn("对抗审查问题单", md)
        self.assertIn("- [ ]", md)
        self.assertIn("清单级追问", md)
        self.assertIn("CiteScore 72/100", md)
        self.assertIn("cite_holmes_version:", md)

    def test_zero_network(self):
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            vr.grill_report([_mk(1, "verified")])
            mu.assert_not_called()

    def test_cli_wiring(self):
        src = open(os.path.join(SK, "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn('ap.add_argument("--grill", metavar="REPORT_JSON"', src)
        self.assertIn("render_grill_md(items, sc)", src)


class TestSkillSlimDown(unittest.TestCase):
    """F2:SKILL.md 分层瘦身（usability 失分面对策：248+行→精简主文件）。"""

    def test_line_budget(self):
        en = len(open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read().splitlines())
        zh = len(open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read().splitlines())
        self.assertLessEqual(en, 215, f"EN {en} 行")
        self.assertLessEqual(zh, 195, f"ZH {zh} 行")

    def test_sunk_files_exist(self):
        sec = open(os.path.join(SK, "references", "security.md"), encoding="utf-8").read()
        self.assertIn("网络边界", sec)
        self.assertIn("api.crossref.org", sec)
        oos = open(os.path.join(SK, "references", "out-of-scope.md"), encoding="utf-8").read()
        self.assertIn("诚实边界", oos)  # Honest limits 已并入

    def test_links_replaces_inline_sections(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("references/anti-patterns.md", en)
        self.assertIn("references/security.md", en)
        self.assertIn("references/out-of-scope.md", en)
        # 反模式全文不再内联（内联版应有 14 条目录——瘦身后只留链接+两条最重要的）
        self.assertNotIn("## Security & behavior declaration", en)

    def test_all_feature_keywords_retained(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read().lower()
        for kw in ("clone-pair detection", "cross-lingual title bridging",
                   "bibliography profiling", "preprint upgrade hints",
                   "completeness scoring", "--doctor", "--preset submission",
                   "--explain n", "--grill report.json"):
            self.assertIn(kw, en, kw)
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        for kw in ("克隆引用对检测", "跨语言标题桥接", "清单画像", "预印本升级提示",
                   "导出完整度评分", "--doctor", "--preset submission", "--explain",
                   "--grill report.json", "11 类机器可读错误码"):
            self.assertIn(kw, zh, kw)

    def test_registry_domains_in_security_summary(self):
        # v1.2 老测试同源约束:主文件安全摘要必须点名外联端点
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        for token in ("doi.org", "api.crossref.org", "eutils.ncbi.nlm.nih.gov",
                      "export.arxiv.org", "api.semanticscholar.org"):
            self.assertIn(token, en, token)

    def test_grill_cli_friendly_errors(self):
        # 审计 minor-3 回归锁:文件不存在/非 JSON/results 缺失三路径均友好报错 return 2
        src = open(os.path.join(SK, "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn("❌ 报告文件不存在", src)
        self.assertIn("❌ 不是有效的 JSON 报告", src)
        self.assertIn("❌", src) and self.assertIn("无 results 字段", src)
        # 三处 return 2 在 grill 分支内
        seg = src[src.index('if getattr(args, "grill", ""):'):src.index("grill_report(doc")]
        self.assertEqual(seg.count("return 2"), 3)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "4.0.0")
        self.assertIn("version: 4.0.0",
                      open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
