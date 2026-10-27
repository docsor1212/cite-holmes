#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.4.0 测试：审查与审计强化（F34 --reviewer / F35 --audit-mode / F36 MCP 后端）。

F34=审稿人预演就地嵌入（--grill 同款生成器，判定不变）；
F35=稿件审计报告（P0/P1/P2 分级+行动清单，机械层重组绝不新造判定）；
F36=MCP README「核验后端」接线示例。全部 sealed（--demo --offline，零真网）。"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


def _demo_rows():
    """离线跑 demo 集（8 条 3 预埋伪造）拿真实形态 results。"""
    fresh_engine_state(vr)
    refs = __import__("json").load(open(
        os.path.join(SK, "examples", "demo_refs.json"), encoding="utf-8"))
    return [vr.verify_one(r, i, True, 5.0, False)
            for i, r in enumerate(refs, 1)]


class F34_ReviewerEmbed(unittest.TestCase):
    def test_embedded_into_report(self):
        fresh_engine_state(vr)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "r.md")
            rc = vr.main_with_args(["--demo", "--offline", "--reviewer",
                                    "--out", out])
            self.assertEqual(rc, 0)
            body = open(out, encoding="utf-8").read()
            self.assertIn("对抗审查问题单", body)      # grill 区嵌入
            self.assertIn("引用机械验证报告", body)    # 原报告主体仍在
            self.assertLess(body.index("引用机械验证报告"),
                            body.index("对抗审查问题单"))  # 嵌在尾部


class F35_AuditMode(unittest.TestCase):
    def test_audit_report_structure(self):
        fresh_engine_state(vr)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "r.md")
            rc = vr.main_with_args(["--demo", "--offline", "--audit-mode",
                                    "--out", out])
            self.assertEqual(rc, 0)
            ap = out.rsplit(".", 1)[0] + ".audit.md"
            body = open(ap, encoding="utf-8").read()
            self.assertIn("引用审计报告", body)
            self.assertIn("P0 编造嫌疑", body)          # demo #8 假 DOI → invalid
            self.assertIn("P2 复核项", body)            # partial+needs_human
            self.assertIn("行动清单", body)
            self.assertIn("机械层口径", body)           # 免责在档

    def test_audit_reorg_only_no_new_verdicts(self):
        rows = _demo_rows()
        sc = vr.compute_scorecard(rows)
        before = {r["index"]: r["verdict"] for r in rows}
        vr.render_audit_report(rows, None, sc)
        after = {r["index"]: r["verdict"] for r in rows}
        self.assertEqual(before, after)                 # 重组绝不改判定
        # P0 只含 invalid
        p0_titles = [r["index"] for r in rows if r["verdict"] == "invalid"]
        body = vr.render_audit_report(rows, None, sc)
        seg = body.split("P0 编造嫌疑")[1].split("###")[0] if "P0" in body else ""
        for i in p0_titles:
            self.assertIn(f"#{i} ", seg)

    def test_audit_retraction_layer(self):
        # 审计 P1-1/P1-2 回归锁：撤稿信号在嵌套 checks.retraction.retracted——
        # ①真实撤稿必须进 P1（带撤稿⚠）而非 P2；②撤稿+invalid 只进 P0；
        # ③撤稿+unreachable 在 P1 恰一次（去重互斥）
        def _row(idx, verdict, retr=False, unreach=False):
            checks = {}
            if retr:
                checks["retraction"] = {"retracted": True}
            return {"index": idx, "title": f"paper {idx}", "url": "", "doi": "",
                    "pmid": "", "arxiv": "", "source": "", "year": 2024,
                    "tier": "journal", "semantic": "", "verdict": verdict,
                    "http_status": None, "note": "撤稿库命中" if retr else "",
                    "needs_human_check": retr, "checks": checks}
        rows = [_row(1, "partial", retr=True),          # 纯撤稿 → P1
                _row(2, "invalid", retr=True),           # 撤稿+invalid → P0 only
                _row(3, "unreachable", retr=True),       # 撤稿+不可达 → P1 一次
                _row(4, "unreachable")]                  # 纯不可达 → P1
        sc = vr.compute_scorecard(rows)
        body = vr.render_audit_report(rows, None, sc)
        p1_seg = body.split("P1 高风险线索")[1].split("###")[0]
        self.assertIn("#1 [撤稿⚠]", p1_seg)             # 纯撤稿进 P1（修复主断言）
        self.assertIn("#3 [撤稿⚠]", p1_seg)
        self.assertEqual(p1_seg.count("#3 "), 1)        # 去重（恰一次）
        self.assertNotIn("#2 ", p1_seg)                 # invalid 不重复进 P1
        self.assertIn("#4 [不可达]", p1_seg)
        if "P2 复核项" in body:                          # 本夹具无 P2 残留条目
            self.assertNotIn("#1 ", body.split("P2 复核项")[1].split("##")[0])


class F36_McpBackend(unittest.TestCase):
    def test_readme_backend_section(self):
        s = open(os.path.join(SK, "mcp", "README.md"), encoding="utf-8").read()
        self.assertIn("核验后端", s)
        self.assertIn("verify_references", s)
        self.assertIn("50", s)                          # 批量上限声明

    def test_docs_budget_unchanged(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)
        self.assertIn("--audit-mode", en)
        self.assertIn("--audit-mode", zh)
        self.assertIn("--reviewer", en)
        self.assertIn("--reviewer", zh)


if __name__ == "__main__":
    unittest.main()
