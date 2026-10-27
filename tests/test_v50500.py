#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.0 测试：判定精度与上手降坡。

F37 arXiv 标题别名守卫（整合并行会话补丁+门审 CJK 扩展：截短/异序→partial，
编造仍 invalid）；F38 占位文件修复（真实公开数据 bib）；F39 5 分钟上手路径；
F40 --refs-dir 文献库批量；F41 --next-round 下一轮种子（invalid 不回收）。
全部 sealed（arXiv 用 Atom XML 桩/文献库用 tmpdir，零真网）。"""
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402

_REG = "A Comprehensive Longitudinal Study Addressing Hallucinated and " \
       "Suspicious Citations in Scientific Literature"


def _atom(reg_title):
    return ("""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>""" + reg_title + """</title>
<published>2026-07-01T00:00:00Z</published>
<summary>abstract</summary></entry></feed>""").encode()


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


class F37_AliasGuard(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)
        vr._ARXIV_LAST[0] = 0.0
        self._sleep = unittest.mock.patch.object(vr.time, "sleep", lambda s: None)
        self._sleep.start()
        self._net = unittest.mock.patch.object(
            vr.urllib.request, "urlopen",
            unittest.mock.MagicMock(return_value=_Resp(_atom(_REG))))
        self._net.start()

    def tearDown(self):
        self._net.stop()
        self._sleep.stop()
        vr._net_reset()

    def _match(self, title):
        return vr.arxiv_metadata_match("2607.22693", title, 2026, 5.0)

    def test_truncated_subset_partial(self):
        adj, note, matched = self._match("suspicious citations literature")
        self.assertEqual(adj, "partial")
        self.assertTrue(matched)
        self.assertIn("截短/异序", note)
        self.assertIn(_REG[:40], note)            # 登记全称建议在

    def test_reordered_subset_partial(self):
        adj, note, _ = self._match(
            "literature scientific in citations suspicious hallucinated study")
        self.assertEqual(adj, "partial")

    def test_disjoint_still_invalid(self):
        # 反伪造锁：ID 指向的论文与声称题名完全无关 → 仍 invalid
        adj, note, matched = self._match("Quantum Baking Recipes Collection")
        self.assertEqual(adj, "invalid")
        self.assertIn("编造或错引", note)

    def test_partial_carries_needs_human_flag(self):
        # 审计 P1-1 回归锁：别名守卫 partial 在 verify_one 消费侧必须真挂
        # needs_human_check（「转人工」旗不得缺席——v4.1.0 P3-1 红线）
        with unittest.mock.patch.object(
                vr, "arxiv_metadata_match",
                return_value=("partial", "arXiv 标题疑似截短/异序（相似度 0.42）"
                              "→ 建议引用登记全称", True)), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")):
            out = vr.verify_one({"title": "suspicious citations literature",
                                 "arxiv": "2607.22693"}, 1, False, 5.0, False)
        self.assertEqual(out["verdict"], "partial")
        self.assertTrue(out["needs_human_check"],
                        "别名 partial 未挂转人工旗（审计 P1-1 复发）")

    def test_single_word_no_guard(self):
        # ≥2 实词门：单词题名不触发守卫（信息量不足照旧判死转人工语义）
        adj, _, _ = self._match("citations")
        self.assertEqual(adj, "invalid")

    def test_cjk_same_script_subset(self):
        # 评审扩展：CJK 同文种守卫（原补丁字符集会剥空中文）
        reg2 = "基于大规模语料库的中文医学文献自动摘要与关键信息抽取系统研究"
        with unittest.mock.patch.object(
                vr.urllib.request, "urlopen",
                unittest.mock.MagicMock(return_value=_Resp(_atom(reg2)))):
            adj, note, _ = vr.arxiv_metadata_match(
                "2607.22693", "文献研究", 2026, 5.0)
        self.assertEqual(adj, "partial")
        self.assertIn("截短/异序", note)


class F38_RealBib(unittest.TestCase):
    def test_placeholder_bib_now_real(self):
        p = os.path.join(SK, "examples", "end-to-end", "exports", "report.bib")
        s = open(p, encoding="utf-8").read()
        self.assertIn("@article{", s)
        self.assertIn("10.1038/nature12373", s)
        refs = vr.parse_bibtex(s)
        self.assertEqual(len(refs), 1)
        self.assertIn("thermometry", refs[0].get("title", "").lower())
        # excerpt 不再是无换行的孤行
        ex = open(os.path.join(SK, "examples", "end-to-end",
                               "paper_excerpt.md"),
                  encoding="utf-8").read()
        self.assertTrue(ex.endswith("\n"))


class F39_Onboarding(unittest.TestCase):
    def test_doc_and_routing(self):
        s = open(os.path.join(SK, "docs", "onboarding.md"),
                 encoding="utf-8").read()
        for kw in ("第 1 级", "--demo", "第 2 级", "--refs", "第 3 级",
                   "--preset submission"):
            self.assertIn(kw, s)
        idx = open(os.path.join(SK, "references", "INDEX.md"),
                   encoding="utf-8").read()
        self.assertIn("docs/onboarding.md", idx)
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("docs/onboarding.md", en)
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("docs/onboarding.md", zh)


class F40_RefsDir(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_batch_load_mixed(self):
        with tempfile.TemporaryDirectory() as td:
            json.dump([{"title": "Ref one from json file here", "url":
                        "https://example.org/1", "year": 2020},
                       {"title": "Ref two from json file here", "url":
                        "https://example.org/2", "year": 2021}],
                      open(os.path.join(td, "a.json"), "w", encoding="utf-8"))
            open(os.path.join(td, "b.bib"), "w", encoding="utf-8").write(
                "@article{k2023,\n  title={A bib entry title about topic},\n"
                "  author={K Author},\n  year={2023},\n  journal={J}\n}\n")
            open(os.path.join(td, "broken.json"), "w").write("{not json")
            open(os.path.join(td, "notes.md"), "w", encoding="utf-8").write(
                "# 笔记（无参考文献节）\n正文而已\n")
            out = os.path.join(td, "r.md")
            rc = vr.main_with_args(["--refs-dir", td, "--offline", "--out", out])
            self.assertEqual(rc, 0)     # 坏文件跳过、零参考文献节 md 跳过，3 条进批
            body = open(out, encoding="utf-8").read()
            self.assertIn("Ref one from json file here", body)
            self.assertIn("A bib entry title about topic", body)

    def test_empty_dir_exit2(self):
        self.assertEqual(vr.main_with_args(
            ["--refs-dir", "/nonexistent-dir-xyz", "--offline",
             "--out", "/tmp/x.md"]), 2)


class F41_NextRound(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_skeleton_semantics(self):
        report = {"results": [
            {"index": 1, "title": "A verified entry", "verdict": "verified",
             "doi": "10.1/v", "note": ""},
            {"index": 2, "title": "A partial entry", "verdict": "partial",
             "doi": "10.1/p", "note": "缺字段；  请复核"},
            {"index": 3, "title": "An unreachable entry",
             "verdict": "unreachable", "url": "https://x.org/a", "note": ""},
            {"index": 4, "title": "An invalid fabrication",
             "verdict": "invalid", "doi": "", "note": "编造"},
            {"index": 5, "title": "An unverified entry",
             "verdict": "unverified", "pmid": "12345678", "note": ""},
        ]}
        with tempfile.TemporaryDirectory() as td:
            rp = os.path.join(td, "report.json")
            json.dump(report, open(rp, "w", encoding="utf-8"))
            out, n = vr.build_next_round(report, os.path.join(td, "nr.json"))
            self.assertEqual(n, 3)                      # partial+unreach+unverified
            sk = json.load(open(out, encoding="utf-8"))
            titles = [r["title"] for r in sk["refs"]]
            self.assertNotIn("A verified entry", titles)   # verified 不回收
            self.assertNotIn("An invalid fabrication", titles)  # invalid 不回收
            p2 = next(r for r in sk["refs"] if "partial" in r["title"])
            self.assertIn("_retry_reason", p2)
            self.assertNotIn("verdict", p2)             # 骨架不带判定

    def test_cli_smoke_from_demo(self):
        with tempfile.TemporaryDirectory() as td:
            rep = os.path.join(td, "rep.json")
            vr.main_with_args(["--demo", "--offline", "--json-out", rep,
                               "--out", os.path.join(td, "r.md")])
            rc = vr.main_with_args(["--next-round", rep])
            self.assertEqual(rc, 0)
            nr = rep.rsplit(".", 1)[0] + "_next_round.json"
            self.assertTrue(os.path.exists(nr))
            sk = json.load(open(nr, encoding="utf-8"))
            # demo invalid #8（Meta-analysis…）是终局判定——绝不回收
            self.assertFalse(any(r.get("title", "").startswith("Meta-analysis")
                                 for r in sk["refs"]))

    def test_bad_report_exit2(self):
        self.assertEqual(vr.main_with_args(
            ["--next-round", "/nonexistent-report.json"]), 2)


class Docs(unittest.TestCase):
    def test_budgets_and_anchors(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)
        self.assertIn("--refs-dir", en)
        self.assertIn("--next-round", en)
        self.assertIn("--refs-dir", zh)
        self.assertIn("--next-round", zh)
        vd = open(os.path.join(SK, "references", "verification-details.md"),
                  encoding="utf-8").read()
        self.assertIn("别名守卫", vd)
        self.assertIn("invalid 不回收", vd)


if __name__ == "__main__":
    unittest.main()
