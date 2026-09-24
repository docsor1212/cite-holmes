#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cite-holmes v1.10.0 回归：引用级并行验证（--workers）+ 全局网络降级
+ S2 标题检索确认 + 批内结果缓存 + 降级态快速失败 + OpenAlex 429 话术。"""
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


class TestV110(unittest.TestCase):
    """v1.10.0 新功能测试。mock 模式沿用 TestV190 的 _seq。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ch_v110_")
        vr._net_reset()
        vr._S2_LAST[0] = 0.0
        vr._ARXIV_LAST[0] = 0.0
        vr._OPTS.update({"openalex_key": "", "s2_key": "", "mailto": ""})

    def tearDown(self):
        vr._net_reset()
        vr._OPTS.update({"openalex_key": "", "s2_key": "", "mailto": ""})

    class Resp:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    @staticmethod
    def _seq(bodies):
        """按序消费响应体/异常的 urlopen 替身（耗尽后重复最后一项）。"""

        class Dispatch:
            def __init__(self, items):
                self.i = 0
                self.items = items

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                b = self.items[min(self.i, len(self.items) - 1)]
                self.i += 1
                if isinstance(b, Exception):
                    raise b
                return b.body if hasattr(b, "body") else b

        return Dispatch(bodies)

    # ---------- 版本 ----------

    def test_version_bumped_110(self):
        self.assertEqual(vr.VERSION, "1.13.0")

    # ---------- 并行验证 ----------

    def _write_refs(self, refs):
        p = os.path.join(self.tmp, "refs.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False)
        return p

    @staticmethod
    def _fake_verify_one(stats):
        """verify_one 替身：记录最大并发与调用序，固定返回 verified 结果。"""
        lock = vr.threading.Lock()
        active = {"n": 0}

        def fake(ref, idx, offline, timeout, medical=False):
            with lock:
                active["n"] += 1
                stats["max_active"] = max(stats["max_active"], active["n"])
                stats["order"].append(idx)
            vr.threading.Event().wait(0.15)  # 模拟网络耗时，给并发留窗口
            with lock:
                active["n"] -= 1
            return {"index": idx, "title": str(ref.get("title") or "")[:48], "url": "",
                    "doi": str(ref.get("doi") or ""), "pmid": "", "arxiv": "",
                    "source": "", "year": None, "tier": "journal", "semantic": "",
                    "verdict": "verified", "http_status": 200, "note": "",
                    "needs_human_check": False, "checks": {}}

        return fake

    def test_parallel_workers_run_concurrently_and_ordered(self):
        # 8 条 × 0.15s，--workers 4：必须真并发（最大并发 >1），且结果按 index 有序
        stats = {"max_active": 0, "order": []}
        refs = [{"title": f"Paper {i}"} for i in range(1, 9)]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one",
                                        side_effect=self._fake_verify_one(stats)):
            rc = vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc1.sqlite3"), "--workers", "4",
                                    "--interval", "0"])
        self.assertEqual(rc, 0)
        self.assertEqual(stats["order"], list(range(1, 9)), "verify_one 每条恰好调用一次")
        self.assertGreaterEqual(stats["max_active"], 2, "--workers 4 应产生真并发")
        doc = json.load(open(out.rsplit(".", 1)[0] + ".json", encoding="utf-8"))
        self.assertEqual([r["index"] for r in doc["results"]], list(range(1, 9)),
                         "结果必须按 index 有序回填（报告顺序与串行一致）")

    def test_workers_one_stays_serial(self):
        stats = {"max_active": 0, "order": []}
        refs = [{"title": f"Paper {i}"} for i in range(1, 6)]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one",
                                        side_effect=self._fake_verify_one(stats)):
            vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc2.sqlite3"), "--workers", "1",
                               "--interval", "0"])
        self.assertEqual(stats["max_active"], 1, "--workers 1 应走串行路径")

    def test_offline_forces_serial(self):
        stats = {"max_active": 0, "order": []}
        refs = [{"title": f"Paper {i}"} for i in range(1, 6)]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one",
                                        side_effect=self._fake_verify_one(stats)):
            vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc3.sqlite3"), "--workers", "4",
                               "--offline"])
        self.assertEqual(stats["max_active"], 1, "offline 模式自动串行（无需并发）")

    def test_parallel_bad_entry_does_not_crash_batch(self):
        # 混入非对象条目：并行路径下该条降级 invalid，其余照常
        stats = {"max_active": 0, "order": []}
        refs = [{"title": "Good Paper One"}, "not-a-dict", {"title": "Good Paper Two"}]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one",
                                        side_effect=self._fake_verify_one(stats)):
            rc = vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc4.sqlite3"), "--workers", "2",
                                    "--interval", "0"])
        self.assertEqual(rc, 0)
        doc = json.load(open(out.rsplit(".", 1)[0] + ".json", encoding="utf-8"))
        self.assertEqual(doc["results"][1]["verdict"], "invalid")
        self.assertIn("条目不是对象", doc["results"][1]["note"])
        self.assertEqual(doc["results"][0]["verdict"], "verified")

    def test_parallel_verify_one_crash_becomes_invalid(self):
        # verify_one 内部抛异常 → 该条 invalid，绝不拖垮整批（并行下同样成立）
        def boom(ref, idx, offline, timeout, medical=False):
            if idx == 2:
                raise RuntimeError("simulated crash")
            return {"index": idx, "title": "t", "url": "", "doi": "", "pmid": "",
                    "arxiv": "", "source": "", "year": None, "tier": "-", "semantic": "",
                    "verdict": "partial", "http_status": None, "note": "",
                    "needs_human_check": False, "checks": {}}

        refs = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one", side_effect=boom):
            rc = vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc5.sqlite3"), "--workers", "3",
                                    "--interval", "0"])
        self.assertEqual(rc, 0)
        doc = json.load(open(out.rsplit(".", 1)[0] + ".json", encoding="utf-8"))
        self.assertEqual(doc["results"][1]["verdict"], "invalid")
        self.assertIn("RuntimeError", doc["results"][1]["note"])
        self.assertTrue(doc["results"][1]["needs_human_check"])

    # ---------- 批内缓存 ----------

    def test_cache_reuses_duplicate_doi(self):
        calls = {"n": 0}
        lock = vr.threading.Lock()

        def fake(ref, idx, offline, timeout, medical=False):
            with lock:
                calls["n"] += 1
            return {"index": idx, "title": str(ref.get("title") or "")[:48], "url": "",
                    "doi": str(ref.get("doi") or ""), "pmid": "", "arxiv": "",
                    "source": "", "year": None, "tier": "journal", "semantic": "",
                    "verdict": "verified", "http_status": 200, "note": "",
                    "needs_human_check": False, "checks": {}}

        refs = [{"title": "First", "doi": "10.1000/same"},
                {"title": "Second", "doi": "10.1000/same"}]
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        with unittest.mock.patch.object(vr, "verify_one", side_effect=fake):
            vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc6.sqlite3"), "--workers", "2",
                               "--interval", "0"])
        self.assertEqual(calls["n"], 1, "同 DOI 第二条应命中缓存，不重复验证")
        doc = json.load(open(out.rsplit(".", 1)[0] + ".json", encoding="utf-8"))
        self.assertIn("复用缓存判定", doc["results"][1]["note"])
        self.assertEqual(doc["results"][1]["index"], 2, "缓存命中后 index 归位")
        # mark_duplicates 照走：重复的 verified 降 partial（缓存不放大判定）
        self.assertEqual(doc["results"][1]["verdict"], "partial")
        self.assertIn("重复", doc["results"][1]["note"])

    def test_cache_key_priority(self):
        self.assertEqual(vr._cache_key({"doi": " 10.1/X ", "url": "https://a.com/b"}),
                         ("doi", "10.1/x"))
        self.assertEqual(vr._cache_key({"url": "https://a.com/b"}),
                         ("url", "https://a.com/b"))
        self.assertEqual(vr._cache_key({"pmid": "123456"}),
                         ("pmid", "123456"))
        self.assertEqual(vr._cache_key({"arxiv": "2607.22693"}),
                         ("arxiv", "2607.22693"))
        self.assertEqual(vr._cache_key({"title": "only title"}), ())

    # ---------- 全局网络降级 ----------

    def test_degraded_after_three_distinct_host_failures(self):
        vr._cb_record("https://h1.example/a", True)
        vr._cb_record("https://h1.example/b", True)  # 同主机第 2 次：熔断但不降级
        self.assertFalse(vr._NET_STATE["degraded"])
        vr._cb_record("https://h2.example/a", True)
        self.assertFalse(vr._NET_STATE["degraded"])
        vr._cb_record("https://h3.example/a", True)
        self.assertTrue(vr._NET_STATE["degraded"], "3 个不同主机传输失败 → 全局降级")
        # 降级后：未成功过的主机一律快速跳过
        self.assertTrue(vr._cb_open("https://h4.example/x"))
        self.assertIn("全局网络降级", vr._cb_skip_note("https://h4.example/x"))

    def test_success_unmarks_host_and_success_path_blocks_degradation(self):
        vr._cb_record("https://ok.example/a", True)
        vr._cb_record("https://ok.example/b", True)
        vr._cb_record("https://ok.example/c", False)  # 成功：计数清零 + 移出失败主机集
        # v1.9 语义保留：单主机熔断一旦打开，本批次内不自动恢复（成功只清零计数）
        self.assertTrue(vr._CB[vr._cb_host("https://ok.example/a")]["open"])
        self.assertNotIn(vr._cb_host("https://ok.example/a"),
                         vr._NET_STATE["fail_hosts"], "成功主机移出降级候选集")
        vr._cb_record("https://b2.example/a", True)
        vr._cb_record("https://c2.example/a", True)
        self.assertFalse(vr._NET_STATE["degraded"],
                         "剩余失败主机只有 2 个 → 不到降级阈值")

    def test_http_error_does_not_count_toward_degradation(self):
        # 站点有 HTTP 响应（反爬/限流）≠ 出海受限：3 个主机都「HTTP 失败」也不触发全局降级
        for h in ("https://x1.example/a", "https://x2.example/a", "https://x3.example/a"):
            vr._cb_record(h, True, degrade=False)
            vr._cb_record(h, True, degrade=False)  # 第 2 次触发单主机熔断
        self.assertFalse(vr._NET_STATE["degraded"])
        self.assertTrue(vr._CB[vr._cb_host("https://x1.example/a")]["open"],
                        "单主机熔断语义不变（仍计入 fails）")

    def test_degraded_check_url_skips_without_network(self):
        for h in ("https://h1.example/a", "https://h2.example/a", "https://h3.example/a"):
            vr._cb_record(h, True)
        calls = {"n": 0}

        def counting_urlopen(req, timeout=None):
            calls["n"] += 1
            raise AssertionError("降级态不得发起网络请求")

        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=counting_urlopen):
            reachable, status, note = vr.check_url("https://fresh.example/page", 5)
        self.assertFalse(reachable)
        self.assertIsNone(status)
        self.assertIn("全局网络降级", note)
        self.assertEqual(calls["n"], 0)

    def test_degraded_doi_metadata_skips_with_actionable_note(self):
        for h in ("https://h1.example/a", "https://h2.example/a", "https://h3.example/a"):
            vr._cb_record(h, True)
        adj, note, matched = vr.doi_metadata_match("10.1000/x", "Some Title", 2026, 5.0)
        self.assertEqual(adj, "")
        self.assertFalse(matched)
        self.assertIn("全局网络降级", note)
        self.assertIn("代理", note)

    def test_net_reset_clears_degradation(self):
        for h in ("https://h1.example/a", "https://h2.example/a", "https://h3.example/a"):
            vr._cb_record(h, True)
        self.assertTrue(vr._NET_STATE["degraded"])
        vr._net_reset()
        self.assertFalse(vr._NET_STATE["degraded"])
        self.assertFalse(vr._cb_open("https://h4.example/x"))

    def test_degraded_fast_fail_skips_retry(self):
        # 降级态下 check_url 传输失败不再重试（快速失败）
        for h in ("https://h1.example/a", "https://h2.example/a", "https://h3.example/a"):
            vr._cb_record(h, True)
        op = unittest.mock.MagicMock()
        op.open.side_effect = vr.urllib.error.URLError("timed out")
        with unittest.mock.patch.object(vr.urllib.request, "build_opener",
                                        return_value=op):
            reachable, status, note = vr.check_url("https://h9.example/page", 5)
        self.assertFalse(reachable)
        # 常规路径 HEAD+GET × (1 次重试) 最多 4 次尝试；降级态应立即放弃（≤2 次）
        self.assertLessEqual(op.open.call_count, 2, "降级态应快速失败，不再重试")

    # ---------- S2 标题检索确认 ----------

    def _no_id_ref(self):
        return {"title": "Deep Investigation of Citation Hallucination in Large Language Models",
                "url": "https://example.org/paper", "source": "Journal of Studies",
                "year": 2026}

    def test_s2_title_confirms_existence(self):
        s2 = json.dumps({"data": [{"title": "Deep Investigation of Citation "
                                   "Hallucination in Large Language Models",
                                   "year": 2026}]}).encode()
        oa = json.dumps({"results": []}).encode()
        seq = self._seq([self.Resp(oa), self.Resp(s2)])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=lambda req, timeout=None: seq), \
                unittest.mock.patch.object(vr, "check_url",
                                           return_value=(True, 200, "GET 200")):
            r = vr.verify_one(self._no_id_ref(), 1, False, 5.0)
        self.assertTrue(r["checks"]["s2_title"]["matched"])
        self.assertIn("Semantic Scholar 标题检索确认存在", r["note"])
        self.assertEqual(r["verdict"], "partial")  # blog 层 → 不因确认升 verified

    def test_s2_title_mismatch_silent_no_downgrade(self):
        s2 = json.dumps({"data": [{"title": "Totally Different Unrelated Paper",
                                   "year": 2015}]}).encode()
        oa = json.dumps({"results": []}).encode()
        seq = self._seq([self.Resp(oa), self.Resp(s2)])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=lambda req, timeout=None: seq), \
                unittest.mock.patch.object(vr, "check_url",
                                           return_value=(True, 200, "GET 200")):
            r = vr.verify_one(self._no_id_ref(), 1, False, 5.0)
        self.assertFalse(r["checks"]["s2_title"]["matched"])
        self.assertNotIn("Semantic Scholar", r["note"])
        self.assertNotIn("unreachable", r["verdict"])

    def test_s2_title_429_silent(self):
        seq = self._seq([unittest.mock.MagicMock(),
                         vr.urllib.error.HTTPError("u", 429, "rl", None, None)])
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=lambda req, timeout=None: seq), \
                unittest.mock.patch.object(vr, "check_url",
                                           return_value=(True, 200, "GET 200")), \
                unittest.mock.patch.object(vr, "openalex_title_check", return_value=""):
            r = vr.verify_one(self._no_id_ref(), 1, False, 5.0)
        self.assertFalse(r["checks"]["s2_title"]["matched"])
        self.assertNotIn("Semantic Scholar", r["note"])

    def test_s2_title_query_hyphen_normalized(self):
        # S2 官方文档：连字符查询无结果 → query 必须把连字符换成空格
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            raise vr.urllib.error.HTTPError("u", 429, "rl", None, None)

        title = "A State-of-the-art Survey on Machine-Learning-Based Detection"
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=fake_urlopen):
            vr.s2_title_confirm(title, 5.0)
        q = captured["url"].split("query=")[1].split("&")[0]
        decoded = urllib.parse.unquote(q)
        self.assertNotIn("-", decoded)
        self.assertIn("State of the art", decoded)

    def test_s2_title_short_title_no_call(self):
        def counting(req, timeout=None):
            raise AssertionError("短标题不得发起 S2 调用")

        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=counting):
            matched, note = vr.s2_title_confirm("Too short", 5.0)
        self.assertFalse(matched)
        self.assertEqual(note, "")

    def test_s2_title_degraded_skips(self):
        for h in ("https://h1.example/a", "https://h2.example/a", "https://h3.example/a"):
            vr._cb_record(h, True)
        calls = {"n": 0}

        def counting(req, timeout=None):
            calls["n"] += 1
            raise AssertionError("降级态不得发起 S2 调用")

        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=counting):
            matched, note = vr.s2_title_confirm(
                "A Sufficiently Long Academic Paper Title Here", 5.0)
        self.assertFalse(matched)
        self.assertEqual(calls["n"], 0)

    def test_s2_title_in_auditjson_catalog(self):
        p = os.path.join(self.tmp, "r.md")
        ap = os.path.join(self.tmp, "r.audit.json")
        rp = self._write_refs([{"title": "T", "url": "https://example.org/x"}])
        vr.main_with_args(["--refs", rp, "--out", p, "--offline",
                           "--export", "auditjson"])
        doc = json.load(open(ap, encoding="utf-8"))
        self.assertIn("s2_title", doc["checks_catalog"])

    # ---------- OpenAlex 429/403 话术 ----------

    def test_openalex_429_hint_mentions_key(self):
        err = vr.urllib.error.HTTPError("u", 429, "rl", None, None)
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=err):
            note = vr.openalex_title_check(
                "A Sufficiently Long Academic Paper Title Here", 5.0)
        self.assertIn("--openalex-key", note)
        self.assertIn("429", note)

    def test_openalex_403_hint_mentions_free_credits(self):
        err = vr.urllib.error.HTTPError("u", 403, "fr", None, None)
        with unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                        side_effect=err):
            note = vr.openalex_title_check(
                "A Sufficiently Long Academic Paper Title Here", 5.0)
        self.assertIn("--openalex-key", note)
        self.assertIn("100 credits", note)

    # ---------- main() 全局降级提示 ----------

    def test_main_marks_skipped_refs_with_degradation_note(self):
        # 降级在批内触发：3 个不同主机在批内传输失败（每主机 1 次即计入候选集），
        # 之后第 4 条的 check_url 被快速跳过并带「全局网络降级」备注
        refs = [{"title": f"Paper number {i} about testing", "url": f"https://h{i}.example/p"}
                for i in (1, 2, 3)]
        refs.append({"title": "Paper number 4 about testing",
                     "url": "https://fresh.example/p"})
        p = self._write_refs(refs)
        out = os.path.join(self.tmp, "r.md")
        op = unittest.mock.MagicMock()
        op.open.side_effect = vr.urllib.error.URLError("timed out")
        with unittest.mock.patch.object(vr.urllib.request, "build_opener",
                                        return_value=op),                 unittest.mock.patch.object(vr.urllib.request, "urlopen",
                                           side_effect=vr.urllib.error.URLError("t")):
            vr.main_with_args(["--refs", p, "--out", out, "--cache-path", os.path.join(self.tmp, "dc7.sqlite3"), "--workers", "1"])
        self.assertTrue(vr._NET_STATE["degraded"], "批内 3 主机失败应触发降级")
        doc = json.load(open(out.rsplit(".", 1)[0] + ".json", encoding="utf-8"))
        last = doc["results"][3]
        self.assertEqual(last["verdict"], "unreachable")
        self.assertIn("全局网络降级", last["note"])
        self.assertIn("代理", last["note"], "降级备注带可操作建议")


if __name__ == "__main__":
    unittest.main(verbosity=2)
