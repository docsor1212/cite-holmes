#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.4.0 测试：文档级引用完整性审计（孤儿/覆盖率）+ 单文件一体化。

背景（2026-10-19 dogfood 第四轮实锤）：
- 毛细支气管炎报告 16 条清单中 14/15 两条从未被正文引用（13%）——现行报告不提示；
- 首跑实锤：参考文献节自身的 [N] 清单编号被当引用标记（69 处"引用"含 16 个假
  标记、覆盖度假 100%）——正文提取必须截断到节前；
- --check-document 此前必须与 --refs 同用，同一文件传两遍是最大使用摩擦。
全部 sealed（零真网依赖）。"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import fresh_engine_state  # noqa: E402


DOC = """# 报告样例

## 正文

喘息性疾病的管理需要遵循指南[1]。糖皮质激素的使用存在争议[2]。
长期随访数据显示预后良好[1]。

## 参考文献

[1] 中华医学会儿科学分会,等. 儿童喘息性疾病管理临床实践指南(2024版)[J]. 中华儿科杂志, 2024, 62(11): 1030-1042. PMID: 39429074.
[2] Ralston SL，Lieberthal AS，Meissner HC, et al. Clinical practice guideline: the diagnosis, management, and prevention of bronchiolitis[J]. Pediatrics, 2014, 134(5): e1474-502. PMID: 25349312.
[3] Douros K，Everard ML. Time to Say Goodbye to Bronchiolitis and All That[J]. Front Pediatr, 2020, 8: 218. PMID: 32432064.
"""


class F13_CompletenessAudit(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def _results(self):
        def _r(i, t, v):
            return {"index": i, "title": t, "verdict": v, "note": "",
                    "checks": {}, "needs_human_check": False, "tier": "-",
                    "http_status": None}
        return [_r(1, "儿童喘息性疾病管理临床实践指南(2024版)", "verified"),
                _r(2, "Clinical practice guideline: bronchiolitis", "verified"),
                _r(3, "Time to Say Goodbye to Bronchiolitis", "unverified")]

    def test_orphans_and_coverage(self):
        cd = vr.check_document(DOC, self._results())
        self.assertEqual(cd["n_citations"], 3, f"正文标记 3 处: {cd['n_citations']}")
        self.assertEqual(cd["uncited_refs"], [3], "条目 3 从未被正文引用")
        self.assertEqual(cd["n_uncited"], 1)
        self.assertEqual(cd["coverage"], round(2 / 3, 2))
        self.assertEqual(cd["n_listed"], 3)

    def test_ref_list_markers_not_citations(self):
        # 截断守卫：清单节内的 [1][2][3] 编号不算引用（首跑实锤 69 处假标记）
        cd = vr.check_document(DOC, self._results())
        self.assertEqual(cd["n_citations"], 3,
                         "清单编号被当引用=截断失效")
        # 且锚词率低不应由清单行贡献
        self.assertTrue(all(c["sentence"] for c in cd["citations"]))

    def test_ghost_still_counted(self):
        # 幽灵引用必须写在正文区（参考文献节后会被节截断正确忽略）
        doc2 = DOC.replace("长期随访数据显示预后良好[1]。",
                           "长期随访数据显示预后良好[1]，清单外条目亦有引用[9]。")
        cd = vr.check_document(doc2, self._results())
        self.assertEqual(cd["n_unbound"], 1, "幽灵引用（引了没列）仍要报")

    def test_all_cited_full_coverage(self):
        doc3 = DOC.replace("长期随访数据显示预后良好[1]。",
                           "长期随访数据显示预后良好[3]。")
        cd = vr.check_document(doc3, self._results())
        self.assertEqual(cd["uncited_refs"], [])
        self.assertEqual(cd["coverage"], 1.0)

    def test_composite_markers_count_all_bound(self):
        # 审计 P1 回归锁：[1-3]/[2-5] 复合标记的全部条目计入已引——
        # 原实现只记首绑，医学高频的 [2-5] 会把条目 2-4 误报孤儿
        doc2 = DOC.replace("长期随访数据显示预后良好[1]。",
                           "随访与预后研究见系列文献[1-3]。")
        cd = vr.check_document(doc2, self._results())
        self.assertEqual(cd["uncited_refs"], [],
                         f"复合标记应全部计入: {cd['uncited_refs']}")
        self.assertEqual(cd["coverage"], 1.0)

    def test_h4_heading_variant_truncation(self):
        # 审计 P3 修复锁：#### 四级标题变体同样截断（#{0,6}）
        doc2 = DOC.replace("## 参考文献", "#### 参考文献")
        cd = vr.check_document(doc2, self._results())
        self.assertEqual(cd["n_citations"], 3,
                         f"四级标题清单编号不得当引用: {cd['n_citations']}")

    def test_mojibake_doc_no_crash(self):
        # 审计 P2 修复锁：坏字节文档 replace 降级，不裸 Traceback
        import tempfile, os
        p = os.path.join(tempfile.mkdtemp(), "bad.md")
        bad = chr(0xFF) + chr(0xFE) + chr(0x80)
        with open(p, "w", encoding="utf-8", errors="replace") as f:
            f.write("# t" + bad + " bad bytes\n\n## 参考文献\n\n"
                    "[1] ok entry title here[J]. X, 2020, 1(1): 1-2.\n")
        rc = vr.main_with_args(["--check-document", p, "--out",
                                os.path.join(tempfile.mkdtemp(), "r.md"),
                                "--offline"])
        self.assertEqual(rc, 0, "坏编码应 replace 降级而非崩溃")

    def test_advisory_note_no_verdict_claim(self):
        cd = vr.check_document(DOC, self._results())
        self.assertIn("非真伪问题", cd["note"])
        self.assertIn("人工复核候选", cd["note"])


class F13_Render(unittest.TestCase):
    def test_md_render_contains_coverage(self):
        _res = [{"index": i, "title": f"完整标题字段渲染测试条目第{i}篇论文",
                 "verdict": "verified", "note": "", "checks": {},
                 "needs_human_check": False, "tier": "-", "http_status": None}
                for i in (1, 2, 3)]
        cd = vr.check_document(DOC, _res)
        md = vr.render_md(_res, False, "general", context_check=cd)
        self.assertIn("引用覆盖", md)
        self.assertIn("漏引或冗列", md)


class F14_SingleFileMode(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)
        self.tmp = tempfile.mkdtemp()
        self.doc = os.path.join(self.tmp, "doc.md")
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(DOC)

    def test_one_file_offline_end_to_end(self):
        out = os.path.join(self.tmp, "r.md")
        rc = vr.main_with_args(["--check-document", self.doc, "--out", out,
                                "--offline"])
        self.assertEqual(rc, 0, f"单文件模式应 exit 0: rc={rc}")
        self.assertTrue(os.path.exists(out))
        j = json.load(open(out[:-3] + ".json", encoding="utf-8"))
        self.assertEqual(len(j["results"]), 3, "自提取 3 条参考文献")
        self.assertIn("context_check", j)
        cc = j["context_check"]
        self.assertEqual(cc["n_listed"], 3)
        self.assertEqual(cc["uncited_refs"], [3])
        md = open(out, encoding="utf-8").read()
        self.assertIn("引用覆盖", md)

    def test_no_refs_section_clear_error(self):
        doc2 = os.path.join(self.tmp, "norefs.md")
        with open(doc2, "w", encoding="utf-8") as f:
            f.write("# 只有正文\n\n没有任何参考文献节的内容。\n")
        out = os.path.join(self.tmp, "r2.md")
        rc = vr.main_with_args(["--check-document", doc2, "--out", out,
                                "--offline"])
        self.assertEqual(rc, 2, "无参考文献节且无 --refs 应明确报错")

    def test_refs_still_wins_when_given(self):
        # 显式 --refs 与 --check-document 同用=原语义（外部清单），不自动提取
        refs_file = os.path.join(self.tmp, "refs.json")
        with open(refs_file, "w", encoding="utf-8") as f:
            json.dump([{"title": "外部清单唯一条目引用测试文档",
                        "source": "X", "year": 2024}], f)
        out = os.path.join(self.tmp, "r3.md")
        rc = vr.main_with_args(["--refs", refs_file, "--check-document", self.doc,
                                "--out", out, "--offline"])
        self.assertEqual(rc, 0)
        j = json.load(open(out[:-3] + ".json", encoding="utf-8"))
        self.assertEqual(len(j["results"]), 1, "显式 --refs 优先")


if __name__ == "__main__":
    unittest.main()
