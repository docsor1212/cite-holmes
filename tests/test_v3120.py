#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.12.0 测试:投稿工作台版——--preset submission(F1)/--explain 单条解释(F2)
/文档可用性三件(F3)/词根扩容(F4)。全部离线。"""
import importlib.util
import os
import sys
import unittest
from contextlib import redirect_stdout
import io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def _mk(i, title, doi="", verdict="verified", note=""):
    return {"index": i, "title": title, "doi": doi, "verdict": verdict,
            "note": note, "checks": {}, "tier": "official", "http_status": 200,
            "needs_human_check": False}


class TestExplainRef(unittest.TestCase):
    """F2:explain_ref 判定链人话解释(纯静态零网络)。"""

    def test_verified_full_chain(self):
        r = _mk(1, "A Real Paper", "10.1/x")
        r["checks"] = {"doi_metadata": {"matched": True},
                       "url": {"reachable": True, "status": 200}}
        out = vr.explain_ref(r)
        self.assertIn("第 1 条", out)
        self.assertIn("verified", out)
        self.assertIn("DOI.org 注册元数据比对一致", out)
        self.assertIn("来源页可达（HTTP 200）", out)
        self.assertIn("建议", out)

    def test_invalid_with_error_codes(self):
        r = _mk(2, "Fake Paper", "10.9999/fake", verdict="invalid",
                note="DOI 在 DOI.org 不存在（404）→ 疑似编造引用")
        out = vr.explain_ref(r)
        self.assertIn("invalid", out)
        self.assertIn("E_DOU_NOT_FOUND", out)
        self.assertIn("编造引用", out)
        self.assertIn("不得引用", out)

    def test_cross_lang_partial(self):
        r = _mk(3, "中文题名", "10.2/y", verdict="partial",
                note="跨语言标题无法机器比对（相似度 0.00；桥接核验未命中）")
        r["error_codes"] = ["E_CROSS_LANG"]
        out = vr.explain_ref(r)
        self.assertIn("E_CROSS_LANG", out)
        self.assertIn("人工核对", out)

    def test_completeness_shown(self):
        r = _mk(4, "T", "10.3/z")
        r["completeness"] = {"score": 70, "missing": ["volume", "issue"],
                             "suggestion": "注册库未登记：卷、期"}
        out = vr.explain_ref(r)
        self.assertIn("70/100", out)
        self.assertIn("volume", out)

    def test_clone_note_surfaced(self):
        r = _mk(5, "T", "10.4/w",
                note="克隆引用对 #5↔#6：同题不同 DOI（克隆引用：至少一个标识为编造或错引）")
        out = vr.explain_ref(r)
        self.assertIn("克隆引用对", out)

    def test_offline_unverified(self):
        r = _mk(6, "T", verdict="unverified")
        out = vr.explain_ref(r)
        self.assertIn("unverified", out)
        self.assertIn("离线", out)

    def test_zero_network(self):
        # 纯静态承诺:mock urlopen 后调用不得触发网络
        import unittest.mock
        r = _mk(7, "T", "10.5/v")
        r["checks"] = {"doi_metadata": {"matched": True}}
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            vr.explain_ref(r)
            mu.assert_not_called()


class TestPresetAndCli(unittest.TestCase):
    """F1:--preset submission 组合预设 + --explain CLI 接线。"""

    def test_preset_in_argparse(self):
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn('choices=["submission"]', src)
        self.assertIn('args.export = args.export or "gbt7714,bibtex,csv"', src)
        self.assertIn("args.strict = True", src)
        # preset 组合在 doctor 分发之前(parse 后立即)
        self.assertLess(src.index('if getattr(args, "preset", "") == "submission"'),
                        src.index('if getattr(args, "doctor", False)'))

    def test_explain_wiring_after_citescore(self):
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn('if getattr(args, "explain", None) is not None:', src)
        self.assertIn("explain_ref(target) if target else", src)

    def test_explain_missing_index_message(self):
        # 条目不存在时给有效范围提示(边界)
        r = _mk(1, "T", "10.1/x")
        self.assertIn("无法解释", vr.explain_ref({"verdict": "weird"}))
        self.assertIn("verified", vr.explain_ref(r))


class TestDocsUsability(unittest.TestCase):
    """F3:文档可用性三件 + F4 词根扩容。"""

    def test_deep_docs_have_entry(self):
        for f in ("search-strategies.md", "verification-details.md",
                  "medical-mode.md", "report-template.md"):
            t = open(os.path.join(HERE, "..", "references", f), encoding="utf-8").read()
            self.assertIn("30 秒入口", t, f)

    def test_index_routing_table(self):
        t = open(os.path.join(HERE, "..", "references", "INDEX.md"),
                 encoding="utf-8").read()
        self.assertIn("按任务 30 秒路由", t)
        self.assertIn("--preset submission", t)

    def test_anti_patterns_grown_with_alternatives(self):
        t = open(os.path.join(HERE, "..", "references", "anti-patterns.md"),
                 encoding="utf-8").read()
        self.assertGreaterEqual(t.count("✅ 替代"), 10)
        self.assertIn("克隆引用对", t)
        self.assertIn("清单画像", t)
        self.assertIn("预印本", t)

    def test_faq_covers_new_features(self):
        t = open(os.path.join(HERE, "..", "references", "faq.md"),
                 encoding="utf-8").read()
        for kw in ("克隆引用对", "清单画像", "预印本", "桥接", "投稿前终检", "--explain"):
            self.assertIn(kw, t)

    def test_dn_keyword_expansion(self):
        # F4:displayName 词根「文献管理」上车;desc 补 GB-T/参考文献格式/投稿前终检
        t = open(os.path.join(HERE, "..", "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("displayName: 引用核查·参考文献验真｜文献管理×AI幻觉检测", t)
        self.assertIn("GB-T 7714", t)
        self.assertIn("参考文献格式", t)

    def test_skill_md_preset_row(self):
        t = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("--preset submission", t)
        self.assertIn("--explain N", t)

    def test_frontmatter_single_metadata_block(self):
        # 审计 B-3 回归锁:frontmatter 只允许一个 metadata 键,且标准 YAML
        # 解析下 displayName 可读（重复键会静默覆盖 displayName）
        t = open(os.path.join(HERE, "..", "SKILL_ZH.md"), encoding="utf-8").read()
        fm = t.split("---")[1]
        self.assertEqual(fm.count("metadata:"), 1, "frontmatter 出现重复 metadata 键")
        try:
            import yaml
            d = yaml.safe_load(fm)
            self.assertEqual(
                d["metadata"]["displayName"],
                "引用核查·参考文献验真｜文献管理×AI幻觉检测")
        except ImportError:
            pass  # 无 pyyaml 环境退化为上方文本断言

    def test_preset_print_reflects_actual_export(self):
        # 审计 A-1 回归锁:preset 打印回显实际 export 而非无条件宣称三导出
        src = open(os.path.join(HERE, "..", "scripts", "verify_refs.py"),
                   encoding="utf-8").read()
        self.assertIn('f"[preset] submission：--strict + --export {args.export} 已组合"', src)
        self.assertIn("绕过磁盘缓存读", src)  # B-1:副作用提示

    def test_error_code_count_11(self):
        # 审计 B-2 回归锁:文档说 11 类,翻译表恰好 11 码
        t = open(os.path.join(HERE, "..", "SKILL_ZH.md"), encoding="utf-8").read()
        self.assertIn("11 类机器可读错误码", t)
        self.assertEqual(len(vr._ERR_CODE_ZH), 11)

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "3.12.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
