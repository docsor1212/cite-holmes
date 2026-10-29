#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.7.0 测试：口径一致性收紧（10-29 评测点名四类不一致的逐项锁）。

评测点名：INDEX 版本标注过期 / 错误码数量 11 与 12 并存 / 安全声明漏报
用户 URL 检查 / 示例产物版本陈旧 / 触发词缺成组请求示例 / 双副本缺设计记录。
全部文件读断言，零网络。"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SK, "scripts"))
import verify_refs as vr  # noqa: E402


class Consistency_ErrorCodes(unittest.TestCase):
    def test_unified_twelve(self):
        # 审计点名：错误码数量 11/12 两种表述并存——统一为真值 12
        self.assertEqual(len(vr._ERR_CODE_ZH), 12)
        gl = open(os.path.join(SK, "references", "GLOSSARY.md"),
                  encoding="utf-8").read()
        self.assertIn("12 类，机器可读", gl)
        self.assertNotIn("11 类，机器可读", gl)
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("12 machine-readable error codes", en)
        self.assertIn("12 类机器可读错误码", zh)
        self.assertNotIn("11 类机器可读错误码", zh)


class Consistency_IndexVersionAgnostic(unittest.TestCase):
    def test_no_stale_stamps(self):
        idx = open(os.path.join(SK, "references", "INDEX.md"),
                   encoding="utf-8").read()
        self.assertNotIn("（v3.8.0 新增）", idx)
        self.assertNotIn("（v3.12）", idx)
        self.assertNotIn("v3.8.0 从 README/SKILL 收拢", idx)
        # 路由表与主索引功能行不受损
        self.assertIn("按任务 30 秒路由", idx)
        self.assertIn("medical-mode.md", idx)


class Consistency_SecurityDeclaration(unittest.TestCase):
    def test_user_url_disclosed(self):
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        sec = open(os.path.join(SK, "references", "security.md"),
                   encoding="utf-8").read()
        self.assertIn("the source URLs you submit", en)
        self.assertIn("来源 URL", zh)
        self.assertIn("你提交的来源 URL", sec)
        # 引擎确实会访问用户 URL——声明必须覆盖该行为
        self.assertIn("check_url(url", open(
            os.path.join(SK, "scripts", "verify_refs.py"),
            encoding="utf-8").read())

    def test_security_md_registries_intact(self):
        sec = open(os.path.join(SK, "references", "security.md"),
                   encoding="utf-8").read()
        for host in ("doi.org", "eutils.ncbi.nlm.nih.gov", "api.openalex.org"):
            self.assertIn(host, sec)


class Consistency_ExampleFreshness(unittest.TestCase):
    def test_no_stale_versions_in_examples(self):
        stale = re.compile(r"[34]\.\d+\.\d+")      # 3.x/4.x 版本串=陈旧迹象
        bad = []
        for root, _dirs, files in os.walk(os.path.join(SK, "examples")):
            for fn in files:
                if not fn.endswith((".json", ".md", ".txt", ".bib")):
                    continue
                p = os.path.join(root, fn)
                for m in stale.finditer(open(p, encoding="utf-8",
                                             errors="replace").read()):
                    bad.append(f"{fn}: {m.group(0)}")
        self.assertEqual(bad, [], f"示例产物含陈旧版本串: {bad}")

    def test_endtoend_report_current_major(self):
        d = json.load(open(os.path.join(SK, "examples", "end-to-end",
                                        "report.json"), encoding="utf-8"))
        self.assertTrue(str(d["version"]).startswith("5."),
                        f"end-to-end 版本陈旧: {d['version']}")


class Consistency_TriggerExamples(unittest.TestCase):
    def test_grouped_request_examples(self):
        readme = open(os.path.join(SK, "README.md"), encoding="utf-8").read()
        self.assertIn("示例请求", readme)
        for g in ("核验引用", "查文献", "深度研究", "投稿前"):
            self.assertIn(g, readme)
        ob = open(os.path.join(SK, "docs", "onboarding.md"),
                  encoding="utf-8").read()
        self.assertIn("示例请求", ob)


class Consistency_DualCopyADR(unittest.TestCase):
    def test_adr_exists_and_budgets(self):
        p = os.path.join(SK, "docs", "adr",
                         "0009-dual-engine-copy-with-sha-gate.md")
        s = open(p, encoding="utf-8").read()
        self.assertIn("sha 门禁", s)
        self.assertIn("Accepted", s)
        en = open(os.path.join(SK, "SKILL.md"), encoding="utf-8").read()
        zh = open(os.path.join(SK, "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertLessEqual(len(en.splitlines()), 222)
        self.assertLessEqual(len(zh.splitlines()), 202)




class Consistency_DualCopyByteEqual(unittest.TestCase):
    """审计 P1-1：ADR-0009 承诺的「测试双闸」做实——引擎双副本逐字节一致。"""

    def test_engine_copies_byte_identical(self):
        import filecmp
        a = os.path.join(SK, "scripts", "verify_refs.py")
        b = os.path.join(SK, "mcp", "verify_refs.py")
        self.assertTrue(os.path.exists(a) and os.path.exists(b))
        self.assertTrue(filecmp.cmp(a, b, shallow=False),
                        "scripts/ 与 mcp/ 引擎副本漂移——跑 bash mcp/sync_engine.sh")


if __name__ == "__main__":
    unittest.main()
