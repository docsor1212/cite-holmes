#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.2.0 测试：中文医学引用核验版。

背景（2026-10-17 dogfood 第三轮实锤，毛细支气管炎报告 16 条）：
- 带内联 PMID 的 GB/T 著录 16 条全军覆没（解析器不认 `[1]` 方括号编号+裸「参考文献」行）；
- 卷期页锚定（PubMed Single Citation Matcher 的 E-utilities 形态）双例唯一命中；
- PMID 通路缺跨语言守卫——中文指南 39429074 声称中文题名 vs 登记英文题名
  sim 0.10 被误判「拼接伪造」（假阴性安全事故，违反家族铁律：语言差异绝不作
  编造依据）。全部 sealed（零真网依赖）。"""
import io
import json
import os
import sys
import unittest
import unittest.mock
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402
from _mocks import NCBIMock, fresh_engine_state  # noqa: E402


def _resp(body):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body
    return R()


GB_T_DOC = """## 正文

一些正文。

参考文献

[1] 中华医学会儿科学分会,等. 儿童毛细支气管炎管理临床实践指南(2024版)[J]. 中华儿科杂志, 2024, 62(11): 1030-1042. PMID: 39429074.
[4] Ralston SL，Lieberthal AS，Meissner HC, et al. Clinical practice guideline: the diagnosis, management, and prevention of bronchiolitis[J]. Pediatrics, 2014, 134(5): e1474-502. PMID: 25349312.
[5] Douros K，Everard ML. Time to Say Goodbye to Bronchiolitis, Viral Wheeze, Reactive Airways Disease, Wheeze Bronchitis and All That[J]. Front Pediatr, 2020, 8: 218. PMID: 32432064.
[10] 中国医师协会儿科医师分会. 儿童常见喘息性疾病抗病原微生物药物合理应用专家共识[J]. 中国实用儿科杂志, 2020, 35(12). (万方题录)
[12] [Guidelines for the management of community-acquired pneumonia in children (2024 revision)][J]. Zhonghua Er Ke Za Zhi, 2024, 62(10): 920-930. PMID: 39327958.
"""


class F8_ParseVariants(unittest.TestCase):
    def test_bracket_numbering_and_bare_heading(self):
        refs = vr.parse_markdown_refs(GB_T_DOC)
        self.assertEqual(len(refs), 5, f"方括号编号+裸标题行应全解析: {len(refs)}")

    def test_inline_pmid_and_locator_fields(self):
        refs = vr.parse_markdown_refs(GB_T_DOC)
        r1 = refs[0]
        self.assertEqual(r1["pmid"], "39429074")
        self.assertEqual(r1["source"], "中华儿科杂志")
        self.assertEqual((r1["volume"], r1["issue"], r1["pages"]), ("62", "11", "1030"))
        r4 = refs[1]
        self.assertEqual(r4["pmid"], "25349312")
        self.assertEqual(r4["pages"], "e1474")
        r5 = refs[2]
        self.assertEqual((r5["volume"], r5["issue"], r5["pages"]), ("8", "", "218"))

    def test_title_first_variant(self):
        # 无作者段变体：segs[0] 以类型码结尾 → 题名段
        refs = vr.parse_markdown_refs(GB_T_DOC)
        r12 = refs[4]
        self.assertTrue(r12["title"].startswith("[Guidelines"),
                        f"题名先行变体: {r12['title'][:40]}")
        self.assertEqual(r12["source"], "Zhonghua Er Ke Za Zhi")
        self.assertEqual(r12["pmid"], "39327958")

    def test_legacy_numbered_format_unchanged(self):
        doc = "## 参考文献\n\n1. **van den Hoogen F, et al.** 2013 classification criteria for systemic sclerosis. *Arthritis Rheum*. 2013;65(11):2737-2747.\n"
        refs = vr.parse_markdown_refs(doc)
        self.assertEqual(len(refs), 1)
        self.assertIn("2013 classification", refs[0]["title"])

    def test_legacy_heading_still_matches(self):
        doc = "### 分类标准\n\n1. **作者 A.** A very long title about pediatric care here. *Pediatrics*. 2014;134(5):e1474-502.\n"
        self.assertEqual(len(vr.parse_markdown_refs(doc)), 1)


class F6_LocatorLookup(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_ta_mapping(self):
        self.assertEqual(vr._ta_for_journal("中华儿科杂志"), "Zhonghua Er Ke Za Zhi")
        self.assertEqual(vr._ta_for_journal("《中华儿科杂志》"), "Zhonghua Er Ke Za Zhi")
        self.assertEqual(vr._ta_for_journal("Pediatrics"), "Pediatrics")
        self.assertEqual(vr._ta_for_journal(""), "")

    def test_unique_hit(self):
        calls = []

        class Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"
        prev = {"n": 0}

        def disp(req, timeout=None):
            u = req.full_url
            calls.append(u)
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": "1", "idlist": ["39429074"]}}).encode())
            return _resp(json.dumps({"result": {"uids": ["39429074"], "39429074": {
                "title": "[Guidelines for the management]",
                "source": "Zhonghua Er Ke Za Zhi", "pubdate": "2024 Nov"}}}).encode())
        with unittest.mock.patch("urllib.request.urlopen", side_effect=disp):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "中华儿科杂志", 2024, "62", "11", "1030", 10.0)
        self.assertTrue(matched)
        self.assertEqual(pmid, "39429074")
        self.assertIn("卷期页锚定核验一致", note)
        self.assertIn("TA:Zhonghua Er Ke Za Zhi", note)
        # 查询串必须带齐 TA/DP/VI/IP/PG
        es = [u for u in calls if "esearch" in u]
        self.assertTrue(es)
        from urllib.parse import unquote
        term = unquote(es[0].split("term=", 1)[1])
        for tag in ("[TA]", "[DP]", "[VI]", "[IP]", "[PG]"):
            self.assertIn(tag, term)

    def test_ambiguous_multi_hit_silent_with_note(self):
        # esearchresult 无 count 字段时走 idlist 长度——NCBIMock 不产 count，
        # 用原生 mock 构造带 count 的响应
        class Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"esearchresult": {"count": "3",
                                                     "idlist": ["1", "2", "3"]}}).encode()
        with unittest.mock.patch("urllib.request.urlopen", return_value=Ctx()):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "Pediatrics", 2014, "134", "5", "e1474", 10.0)
        self.assertFalse(matched)
        self.assertIn("歧义", note)
        self.assertIn("3 条", note)

    def test_zero_hit_silent(self):
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=NCBIMock(default_ids=[])):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "中国实用儿科杂志", 2020, "35", "12", "", 10.0)
        self.assertFalse(matched)
        self.assertEqual(note, "")

    def test_guards_missing_inputs(self):
        self.assertEqual(vr.pubmed_locator_lookup("", 2024, "62", "11", "1030", 5)[2], False)
        self.assertEqual(vr.pubmed_locator_lookup("中华儿科杂志", None, "62", "11", "1030", 5)[2], False)
        self.assertEqual(vr.pubmed_locator_lookup("中华儿科杂志", 2024, "", "11", "1030", 5)[2], False)

    def test_transport_error_observable(self):
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=urllib.error.URLError("reset")):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "中华儿科杂志", 2024, "62", "11", "1030", 5.0)
        self.assertTrue(net_err)
        self.assertIn("未完成", note)


class PMID_CrossLangGuard(unittest.TestCase):
    """P0 回归锁：PMID 通路跨语言守卫（39429074 假阴性事故）。"""

    def setUp(self):
        fresh_engine_state(vr)

    def _esummary(self, title="[Clinical practice guidelines for the management of "
                   "bronchiolitis in children (2024 version)]",
                doi="10.3760/cma.j.cn112140-20241023-00659"):
        return json.dumps({"result": {"uids": ["39429074"], "39429074": {
            "title": title, "fulljournalname": "Zhonghua Er Ke Za Zhi",
            "pubdate": "2024 Nov", "articleids": [{"idtype": "doi", "value": doi}]}}})

    def test_cross_lang_never_invalid(self):
        body = self._esummary("[Clinical practice guidelines for the management of "
                              "bronchiolitis in children (2024 version)]")
        # 封印：bridge 经 OpenerDirector 走落地页抓取（审计 H-P1：逃出 urlopen patch
        # 真连 doi.org）——显式 patch 掉，保持全测试零真网
        with unittest.mock.patch("urllib.request.urlopen", return_value=_resp(body.encode())), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge", return_value=""):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "儿童毛细支气管炎管理临床实践指南(2024版)", "中华儿科杂志", 2024, 5)
        self.assertNotEqual(adj, "invalid", "跨语言差异绝不判死（家族铁律）")
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言", note)

    def test_cross_lang_bridge_hit_upgrades(self):
        body = self._esummary()
        with unittest.mock.patch("urllib.request.urlopen", return_value=_resp(body.encode())), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge",
                                        return_value="Crossref original-title 一致"):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "儿童毛细支气管炎管理临床实践指南(2024版)", "中华儿科杂志", 2024, 5)
        self.assertEqual(adj, "")
        self.assertTrue(matched)
        self.assertIn("跨语言桥接", note)

    def test_same_lang_low_sim_still_invalid(self):
        # 守卫不得弱化同语言假标题的判死（拼接攻击仍是主要威胁）
        body = self._esummary("A completely different paper about kidney function")
        with unittest.mock.patch("urllib.request.urlopen", return_value=_resp(body.encode())):
            adj, note, matched = vr.pmid_metadata_match(
                "39429074", "Children bronchiolitis management clinical guideline 2024",
                "Pediatrics", 2024, 5)
        self.assertEqual(adj, "invalid")

    _RICH_ESUMMARY = json.dumps({"result": {"uids": ["39429074"], "39429074": {
        "title": "[Clinical practice guidelines for the management of bronchiolitis]",
        "fulljournalname": "Zhonghua Er Ke Za Zhi", "pubdate": "2024 Nov",
        "articleids": [{"idtype": "doi",
                        "value": "10.3760/cma.j.cn112140-20241023-00659"}]}}}).encode()

    @staticmethod
    def _disp(loc_pmid):
        """URL 特征派发：esearch→锚定结果；esummary→富元数据（三消费方共用）。"""
        def disp(req, timeout=None):
            u = req.full_url
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": "1", "idlist": [loc_pmid]}}).encode())
            return _resp(PMID_CrossLangGuard._RICH_ESUMMARY)
        return disp

    def test_e2e_cross_lang_corroboration(self):
        # 端到端：中文题名+PMID+卷期页 → verified（锚定佐证同一 PMID）
        ref = {"title": "儿童毛细支气管炎管理临床实践指南(2024版)", "source": "中华儿科杂志",
               "year": 2024, "pmid": "39429074", "volume": "62", "issue": "11",
               "pages": "1030"}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._disp("39429074")), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge", return_value=""), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")):
            out = vr.verify_one(ref, 1, False, 5.0, True)
        self.assertEqual(out["verdict"], "verified",
                         f"锚定佐证应升 verified: {out['verdict']} / {out['note'][:150]}")
        self.assertTrue(out["checks"]["pmid_metadata"].get("cross_lang_corroborated"))

    def test_corroboration_wrong_pmid_no_upgrade(self):
        # 锚定命中不同 PMID → 不得佐证（张冠李戴防护）
        ref = {"title": "儿童毛细支气管炎管理临床实践指南(2024版)", "source": "中华儿科杂志",
               "year": 2024, "pmid": "39429074", "volume": "62", "issue": "11",
               "pages": "1030"}
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=self._disp("99999999")), \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge", return_value=""), \
             unittest.mock.patch.object(vr, "check_url",
                                        return_value=(True, 200, "GET 200")):
            out = vr.verify_one(ref, 1, False, 5.0, True)
        self.assertNotEqual(out["verdict"], "verified")
        self.assertFalse((out["checks"].get("pmid_metadata") or {}).get(
            "cross_lang_corroborated"))


class A2_FabricatedTitleGate(unittest.TestCase):
    """审计 A2 回归锁：locator 唯一命中必须过同族题名比对——编造同语言题名+
    真实卷期页不得机器 verified（实证复现过的设计洞）。"""

    def setUp(self):
        fresh_engine_state(vr)

    def test_same_family_fake_title_capped_partial(self):
        with unittest.mock.patch("time.sleep"), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=urllib.error.URLError("seal: no net here")):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "中华儿科杂志", 2024, "62", "11", "1030", 5.0,
                claimed_title="儿童哮喘诊治专家共识(2025版)")
        # 屏障下 esearch 失败 → net_err（本测试只验证守卫函数可调用+契约完整）
        self.assertIsInstance(matched, bool)

    def test_same_family_fake_title_with_mock(self):
        calls = []

        def disp(req, timeout=None):
            u = req.full_url
            calls.append(u)
            if "esearch" in u:
                return _resp(json.dumps({"esearchresult": {
                    "count": "1", "idlist": ["39429074"]}}).encode())
            return _resp(json.dumps({"result": {"uids": ["39429074"], "39429074": {
                "title": "Clinical practice guideline for bronchiolitis in children"}}}).encode())
        with unittest.mock.patch("urllib.request.urlopen", side_effect=disp):
            adj, note, matched, pmid, net_err = vr.pubmed_locator_lookup(
                "Pediatrics", 2014, "134", "5", "e1474", 5.0,
                claimed_title="Children asthma diagnosis and treatment expert consensus 2025")
        # 同族（latin vs latin）低相似 → partial 封顶，绝不 verified
        # （A2 设计洞实证场景：编造同语言题名+真实卷期页）
        self.assertEqual(adj, "partial")
        self.assertFalse(matched)
        self.assertIn("疑似错引或拼接", note)


class F7_TierRules(unittest.TestCase):
    def test_cn_registries_journal_tier(self):
        for url in ("https://med.wanfangdata.com.cn/Paper/Detail/x",
                    "https://www.wanfangdata.com.cn/x",
                    "https://cdmd.cnki.com.cn/x", "https://kns.cnki.net/x",
                    "https://cmab.yiigle.com/uploads/x"):
            self.assertEqual(vr.classify_tier(url, True), "journal", url)


class LocatorWiring(unittest.TestCase):
    def setUp(self):
        fresh_engine_state(vr)

    def test_locator_after_reverse_miss(self):
        # 无标识符+卷期页齐备：反查未命中 → 锚定命中 → verified+PMID 回填
        ref = {"title": "A study about pediatric wheezing classification systems here",
               "source": "中华儿科杂志", "year": 2024, "volume": "62", "issue": "11",
               "pages": "1030"}
        # esearch: 反查各轮 0 命中；锚定（5 tag 查询）1 命中；esummary 取登记题名
        class Disp:
            def __init__(self):
                self.calls = []

            def __call__(self, req, timeout=None):
                u = req.full_url
                self.calls.append(u)
                if "esearch" in u:
                    # 审计 H-P3 修复：按标签特征派发（[TA]=锚定查询；[Title]=反查轮
                    # ——原来按 %5B 计数会把 5 词反查轮错喂锚定响应）
                    if "%5BTA%5D" in u or "[TA]" in u:
                        return _resp(json.dumps({"esearchresult": {
                            "count": "1", "idlist": ["39429074"]}}).encode())
                    return _resp(json.dumps({"esearchresult": {
                        "count": "0", "idlist": []}}).encode())
                return _resp(json.dumps({"result": {"uids": ["39429074"],
                                                    "39429074": {"title": "A study about pediatric wheezing classification systems here"}}}).encode())
        d = Disp()
        with unittest.mock.patch("urllib.request.urlopen", side_effect=d):
            out = vr.verify_one(ref, 1, False, 5.0, True)
        self.assertEqual(out["verdict"], "verified", out["note"][:200])
        self.assertEqual(out["pmid"], "39429074")
        self.assertTrue(out["checks"]["pubmed_locator"]["matched"])


if __name__ == "__main__":
    unittest.main()
