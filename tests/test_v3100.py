#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.10.0 测试:跨语言标题桥接核验(F1)+克隆引用搭档检测(F2)+--doctor 自检(F3)
+VERIFY 渐进披露重排(F4)。全部离线(桥接网络路径以 mock 覆盖,真网验收见发布前 E2E)。"""
import importlib.util
import io
import urllib.error
import json
import os
import sys
import unittest
import unittest.mock
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def _mk(i, title, doi="", verdict="verified", note=""):
    return {"index": i, "title": title, "doi": doi, "verdict": verdict,
            "note": note, "checks": {}, "tier": "official", "http_status": 200,
            "needs_human_check": False}


class TestCjkNorm(unittest.TestCase):
    """F1 前置:_cjk_norm 归一化(全角/空格/标点)。"""

    def test_fullwidth_folded(self):
        self.assertEqual(vr._cjk_norm("深度学习 综述（上）"), vr._cjk_norm("深度学习综述(上)"))

    def test_english_lower(self):
        self.assertEqual(vr._cjk_norm("Attention Is ALL You Need!"),
                         vr._cjk_norm("attention is all you need"))

    def test_mixed(self):
        a = vr._cjk_norm("BERT：预训练 deep 双向编码器，v2.0")
        b = vr._cjk_norm("bert预训练deep双向编码器v20")
        self.assertEqual(a, b)

    def test_keeps_cjk(self):
        self.assertTrue(all("\u4e00" <= c <= "\u9fff" for c in vr._cjk_norm("氢键复合物中键长变化")))

    def test_empty(self):
        self.assertEqual(vr._cjk_norm(None), "")
        self.assertEqual(vr._cjk_norm(""), "")


class TestCrossLingualBridge(unittest.TestCase):
    """F1:三级桥接(T1 零网络/T2 落地页/T3 OpenAlex)——只升不降。"""

    def test_t1_original_title_hit(self):
        meta = {"original-title": ["氢键复合物中键长变化与振动频率移动相关性重访"]}
        out = vr._cross_lingual_bridge("10.1/x", "氢键复合物中键长变化与振动频率移动相关性重访",
                                       meta, 3.0)
        self.assertIn("original-title", out)

    def test_t1_fullwidth_variant_hit(self):
        meta = {"original-title": ["深度学习综述（上）"]}
        out = vr._cross_lingual_bridge("10.1/x", "深度学习综述(上)", meta, 3.0)
        self.assertIn("original-title", out)

    def test_t2_landing_page_meta_hit(self):
        html = ('<html><head><title>Correlation between Bond-Length</title>'
                '<meta name="citation_title" content="氢键复合物中键长变化与振动频率移动相关性重访">'
                "</head><body>x</body></html>")
        meta = {"resource": {"primary": {"URL": "http://landing.example/paper"}}}
        with unittest.mock.patch("urllib.request.build_opener") as bo:
            bo.return_value.open = lambda req, timeout: io.BytesIO(html.encode())
            out = vr._cross_lingual_bridge("10.1/x", "氢键复合物中键长变化与振动频率移动相关性重访",
                                           meta, 3.0)
        self.assertIn("落地页题名", out)

    def test_t2_landing_page_body_hit(self):
        # meta 无 citation_title,但 <head> 区 <title> 同载中文原题(双语页常见;
        # 审计 A6 后子串命中只认 head 区)
        html = ("<html><head><title>氢键复合物中键长变化与振动频率移动相关性重访 "
                "- 物理化学学报</title></head><body>English content only</body></html>")
        meta = {"resource": {"primary": {"URL": "http://landing.example/paper"}}}
        with unittest.mock.patch("urllib.request.build_opener") as bo:
            bo.return_value.open = lambda req, timeout: io.BytesIO(html.encode())
            out = vr._cross_lingual_bridge("10.1/x", "氢键复合物中键长变化与振动频率移动相关性重访",
                                           meta, 3.0)
        self.assertIn("落地页", out)

    def test_network_failure_silent(self):
        # 网络失败必须静默返回空串——桥接不通绝不变成编造依据
        meta = {"resource": {"primary": {"URL": "http://127.0.0.1:1/x"}}}
        out = vr._cross_lingual_bridge("10.1/x", "完全不相关的中文题目测试", meta, 0.3)
        self.assertEqual(out, "")

    def test_ssrf_guard_blocks_internal_resource_url(self):
        # 安全门:注册库返回的 resource.URL 指向内网/回环时拒绝请求
        for bad in ("http://127.0.0.1:8500/admin", "http://10.0.0.5/x",
                    "http://192.168.1.1/router", "http://localhost:8080/"):
            meta = {"resource": {"primary": {"URL": bad}}}
            with unittest.mock.patch("urllib.request.urlopen") as mu:
                out = vr._cross_lingual_bridge("10.1/x", "完全不相关的中文题目内容", meta, 3.0)
                mu.assert_not_called()
            self.assertEqual(out, "")

    def test_scheme_whitelist_blocks_file(self):
        # 审计 A2:file:// 等 hostname 为空方案在 ssrf_blocked 放行——须被 scheme 门拦下
        meta = {"resource": {"primary": {"URL": "file:///etc/passwd"}}}
        with unittest.mock.patch.object(vr.urllib.request, "build_opener") as bo:
            out = vr._cross_lingual_bridge("10.1/x", "完全不相关的中文题目内容", meta, 3.0)
            bo.assert_not_called()
        self.assertEqual(out, "")

    def test_redirect_to_internal_blocked(self):
        # 审计 A1:落地页 302 → 内网地址必须拒绝(逐跳复查)
        meta = {"resource": {"primary": {"URL": "http://landing.example/p"}}}
        responses = iter([])

        def err_factory(loc):
            return unittest.mock.Mock(
                code=302, headers={"Location": loc})

        class FakeHE(urllib.error.HTTPError):
            def __init__(self, loc):
                self.code = 302
                self.headers = {"Location": loc}

            def read(self, n=-1):
                return b""

        calls = []

        def fake_opener_open(req, timeout):
            calls.append(req.full_url if hasattr(req, "full_url") else str(req))
            raise FakeHE("http://169.254.169.254/latest/meta-data/")

        with unittest.mock.patch.object(vr.urllib.request, "build_opener") as bo:
            bo.return_value.open = fake_opener_open
            out = vr._cross_lingual_bridge(
                "10.1/x", "完全不相关的中文题目内容", meta, 3.0)
        self.assertEqual(out, "")
        # 第 1 跳(落地页)确实被请求;302 指向的内网地址必须拦在 open 之前
        self.assertTrue(any("landing.example" in c for c in calls))
        self.assertFalse(any("169.254" in c for c in calls))

    def test_head_zone_only_body_hit_rejected(self):
        # 审计 A6:正文区(非 head)出现声称题名不再构成「同载」证据
        html = ("<html><head><title>Some Paper</title></head>"
                "<body><ol><li>参考文献：氢键复合物中键长变化与振动频率移动相关性重访. 2011.</li></ol>"
                "</body></html>")
        meta = {"resource": {"primary": {"URL": "http://landing.example/p"}}}
        with unittest.mock.patch.object(vr.urllib.request, "build_opener") as bo:
            bo.return_value.open = lambda req, timeout: io.BytesIO(html.encode())
            out = vr._cross_lingual_bridge(
                "10.1/x", "氢键复合物中键长变化与振动频率移动相关性重访", meta, 3.0)
        self.assertEqual(out, "")

    def test_bridge_hit_keeps_author_mismatch(self):
        # 审计 B1:桥接命中时作者不符信号必须透出(adjust=partial)
        meta = {"title": ["An English Title About topic"],
                "issued": {"date-parts": [[2011]]},
                "original-title": ["氢键复合物中键长变化与振动频率移动相关性重访"],
                "author": [{"family": "Zhang", "given": "San"}]}
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(meta).encode())
            mu.return_value.code = 200
            adj, note, matched, _ = vr.doi_metadata_match(
                "10.4/w", "氢键复合物中键长变化与振动频率移动相关性重访",
                2011, timeout=3.0, authors="Wang Wu")
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言桥接", note)
        self.assertIn("作者不符", note)

    def test_bridge_hit_keeps_journal_mismatch(self):
        # 审计 B1:桥接命中时同语言期刊名不符必须透出(adjust=partial)
        # (中文声称 vs 英文登记刊名属跨语言,既定守卫不判——英文 vs 英文才判)
        meta = {"title": ["An English Title About topic"],
                "issued": {"date-parts": [[2011]]},
                "original-title": ["氢键复合物中键长变化与振动频率移动相关性重访"],
                "container-title": ["Totally Different Journal"]}
        with unittest.mock.patch("urllib.request.urlopen") as mu:
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(meta).encode())
            mu.return_value.code = 200
            adj, note, matched, _ = vr.doi_metadata_match(
                "10.4/w", "氢键复合物中键长变化与振动频率移动相关性重访",
                2011, timeout=3.0, source="Nature")
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言桥接", note)
        self.assertIn("期刊名不符", note)

    def test_doi_metadata_match_bridge_miss_keeps_partial(self):
        # 桥接未命中 → 维持 partial(守卫方向不变)
        meta = {"title": ["An Unrelated English Paper Title About Something Else"],
                "issued": {"date-parts": [[2015]]}, "original-title": ""}
        with unittest.mock.patch("urllib.request.urlopen") as mu, \
             unittest.mock.patch.object(vr, "_cross_lingual_bridge", return_value=""):
            mu.return_value.__enter__ = lambda s: io.BytesIO(json.dumps(meta).encode())
            mu.return_value.code = 200
            adj, note, matched, _ = vr.doi_metadata_match(
                "10.2/y", "完全不同的中文虚构标题内容", 2020, timeout=3.0)
        self.assertEqual(adj, "partial")
        self.assertIn("跨语言", note)


class TestClonePairs(unittest.TestCase):
    """F2:克隆引用搭档检测(零网络,只注记不改判定)。"""

    def test_r1_same_title_different_doi(self):
        rs = [_mk(1, "Attention Is All You Need", "10.1234/real"),
              _mk(2, "Attention  Is All You Need!", "10.9999/fake")]
        n = vr.detect_clone_pairs(rs)
        self.assertEqual(n, 1)
        self.assertIn("克隆引用对 #1↔#2", rs[0]["note"])
        self.assertIn("克隆引用对 #1↔#2", rs[1]["note"])
        self.assertIn("同题不同 DOI", rs[0]["note"])
        for r in rs:  # 判定铁律:克隆是线索不是定罪
            self.assertEqual(r["verdict"], "verified")

    def test_r2_same_doi_different_title(self):
        rs = [_mk(1, "深度学习在医学影像中的应用研究", "10.2222/same"),
              _mk(2, "深度学习在医学影像中的进展研究", "10.2222/same")]
        n = vr.detect_clone_pairs(rs)
        self.assertEqual(n, 1)
        self.assertIn("拼接变体", rs[0]["note"])

    def test_no_false_positive_on_unrelated(self):
        rs = [_mk(1, "Quantum Computing Supremacy", "10.3333/q1"),
              _mk(2, "Deep Learning for Protein Folding", "10.3333/q2"),
              _mk(3, "胃肠道间质瘤的靶向治疗进展", "10.4444/z1")]
        n = vr.detect_clone_pairs(rs)
        self.assertEqual(n, 0)
        self.assertTrue(all(not r["note"] for r in rs))

    def test_same_doi_same_title_not_cloned(self):
        # 同 DOI 同标题=真重复,由 mark_duplicates 管,克隆检测不越权
        rs = [_mk(1, "Same Paper Title Here", "10.5555/dup"),
              _mk(2, "Same Paper Title Here", "10.5555/dup")]
        self.assertEqual(vr.detect_clone_pairs(rs), 0)

    def test_collect_idempotent(self):
        rs = [_mk(1, "Attention Is All You Need", "10.1234/a"),
              _mk(2, "Attention Is All You Need", "10.9999/b")]
        vr.detect_clone_pairs(rs)
        p1 = vr.collect_clone_pairs(rs)
        p2 = vr.collect_clone_pairs(rs)
        self.assertEqual(p1, p2)
        self.assertEqual(len(p1), 1)

    def test_short_titles_skipped(self):
        rs = [_mk(1, "Short one", "10.1/a"), _mk(2, "Short two", "10.1/b")]
        self.assertEqual(vr.detect_clone_pairs(rs), 0)

    def test_cjk_sig_not_empty_and_no_false_merge(self):
        # 审计 B3:纯中文标题指纹不得为空串——异题同 DOI 的两条中文引用不判真重复
        a = vr._dup_title_sig({"title": "氢键复合物中键长变化与振动频率移动相关性重访"})
        b = vr._dup_title_sig({"title": "完全不同的一篇中文论文标题关于其他主题"})
        self.assertTrue(a and b)
        self.assertNotEqual(a, b)
        rs = [_mk(1, "氢键复合物中键长变化与振动频率移动相关性重访", "10.6/c1"),
              _mk(2, "完全不同的一篇中文论文标题关于其他主题", "10.6/c1")]
        vr.mark_duplicates(rs)
        self.assertNotIn("与 #1 重复", rs[1]["note"])

    def test_cjk_sig_same_title_still_merges(self):
        # 同中文标题+同 DOI 仍按真重复合并(回归保障)
        rs = [_mk(1, "氢键复合物中键长变化与振动频率移动相关性重访", "10.6/c1"),
              _mk(2, "氢键复合物中键长变化与振动频率移动相关性重访", "10.6/c1")]
        vr.mark_duplicates(rs)
        self.assertIn("与 #1 重复", rs[1]["note"])

    def test_batch_flow_wires_clone_detection(self):
        # 主流程接线:mark_duplicates 后 clone 注记在场(离线路径)
        rs = [_mk(1, "Attention Is All You Need", "10.1234/a"),
              _mk(2, "Attention  Is All You Need!", "10.9999/b")]
        vr.mark_duplicates(rs)
        vr.detect_clone_pairs(rs)
        self.assertIn("克隆引用对", rs[0]["note"])

    def test_render_md_has_clone_section(self):
        rs = [_mk(1, "Attention Is All You Need", "10.1234/a"),
              _mk(2, "Attention Is All You Need", "10.9999/b")]
        vr.detect_clone_pairs(rs)
        md = vr.render_md(rs, offline=True)
        self.assertIn("克隆引用对", md)
        self.assertIn("#1 ↔ #2", md)

    def test_render_html_has_clone_section(self):
        rs = [_mk(1, "Attention Is All You Need", "10.1234/a"),
              _mk(2, "Attention Is All You Need", "10.9999/b")]
        vr.detect_clone_pairs(rs)
        html = vr.render_html(rs, offline=True)
        self.assertIn("克隆引用对", html)

    def test_render_md_no_section_when_clean(self):
        rs = [_mk(1, "Quantum Computing Supremacy", "10.1/a"),
              _mk(2, "Protein Folding Prediction", "10.1/b")]
        md = vr.render_md(rs, offline=True)
        self.assertNotIn("## 克隆引用对", md)  # 能力矩阵词条不算区块;区块标题不出现


class TestDoctor(unittest.TestCase):
    """F3:--doctor 环境自检(零外呼默认)。"""

    def test_doctor_zero_network_pass(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = vr.run_doctor(net=False)
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("verify_refs.py v3.12.0", out)
        self.assertIn("verdict: all clear", out)
        self.assertNotIn("探针", out)  # 零外呼:无探针段

    def test_doctor_cache_warn_on_unwritable(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = vr.run_doctor(net=False,
                                 cache_path="/proc/nonexistent_dir/cache.sqlite3")
        self.assertIn("缓存目录", buf.getvalue())

    def test_doctor_net_probes_present(self):
        # --net 时探针段出现(网络 mock 全部失败也应输出 FAIL/授权处置,退出码=1)
        buf = io.StringIO()
        with redirect_stdout(buf), \
             unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=OSError("offline")):
            code = vr.run_doctor(net=True, timeout=0.2)
        out = buf.getvalue()
        self.assertIn("探针·DOI.org", out)
        self.assertIn("verdict: FAIL", out)
        self.assertEqual(code, 1)

    def test_doctor_never_prints_key_values(self):
        # 键值绝不回显(安全声明)
        old = os.environ.get("OPENALEX_API_KEY")
        os.environ["OPENALEX_API_KEY"] = "secret-value-xyz"
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                vr.run_doctor(net=False)
            self.assertNotIn("secret-value-xyz", buf.getvalue())
            self.assertIn("已设置", buf.getvalue())
        finally:
            if old is None:
                del os.environ["OPENALEX_API_KEY"]
            else:
                os.environ["OPENALEX_API_KEY"] = old


class TestCapabilityAndDocs(unittest.TestCase):
    """F4/F5:能力矩阵与文档一致性。"""

    def test_capability_matrix_lists_new_catches(self):
        cap = vr.capability_matrix()
        self.assertTrue(any("跨语言" in x for x in cap["caught"]))
        self.assertTrue(any("克隆引用对" in x for x in cap["caught"]))

    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "3.12.0")

    def test_skill_md_version_and_doctor(self):
        p = os.path.join(HERE, "..", "SKILL.md")
        t = open(p, encoding="utf-8").read()
        self.assertIn("version: 3.12.0", t)
        self.assertIn("--doctor", t)
        self.assertIn("cross-lingual title bridging", t.lower())
        self.assertIn("clone-pair detection", t.lower())

    def test_skill_zh_version_and_doctor(self):
        p = os.path.join(HERE, "..", "SKILL_ZH.md")
        t = open(p, encoding="utf-8").read()
        self.assertIn("--doctor", t)
        self.assertIn("跨语言标题桥接", t)
        self.assertIn("克隆引用对检测", t)

    def test_verify_reorder_command_first(self):
        # 渐进披露:VERIFY 段命令块必须先于特性散文(语义层之后是任务表)
        t = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
        seg = t.split("### 4. VERIFY")[1].split("### 5.")[0]
        self.assertLess(seg.index("```bash"), seg.index("**Mechanical layer"))
        self.assertIn("| Task | Flags |", seg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
