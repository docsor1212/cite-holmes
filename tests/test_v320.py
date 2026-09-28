#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3.2.0：BLUF 规范符合性(JSON 对象化)+撤稿本地缓存。"""
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


def SC(invalid=0, unverif=0, unreachable=0, partial=0, verified=2):
    return {"score": 80, "grade": "B", "total": invalid+unverif+unreachable+partial+verified,
            "counts": {"verified": verified, "partial": partial, "unreachable": unreachable,
                       "unverified": unverif, "invalid": invalid}}


class TestBlufSpecConformance(unittest.TestCase):
    def test_t1_dict_five_keys(self):
        d = vr.render_bluf_dict([{"needs_human_check": False}], SC())
        for k in ("verdict", "key_numbers", "blocker", "next_action",
                  "cite_holmes_version"):
            self.assertIn(k, d)
        self.assertEqual(d["cite_holmes_version"], vr.VERSION)

    def test_t2_yaml_from_dict_single_source(self):
        rs = [{"needs_human_check": True}]
        d = vr.render_bluf_dict(rs, SC(invalid=1, verified=1))
        y = vr.render_bluf(rs, SC(invalid=1, verified=1))
        self.assertTrue(y.startswith("---"))
        self.assertIn(d["verdict"], y)
        self.assertIn(d["next_action"], y)

    def test_t3_worst_actionable_rule(self):
        # invalid 在场 → verdict 提清除;全 verified → 可进投稿
        self.assertIn("清除", vr.render_bluf_dict([], SC(invalid=1, verified=1))["verdict"])
        self.assertIn("投稿", vr.render_bluf_dict([], SC())["verdict"])
        self.assertIn("复核", vr.render_bluf_dict([], SC(unverif=1, verified=1))["verdict"])

    def test_t4_json_report_bluf_is_object(self):
        """规范 L1:json.bluf 必须是对象(不再是 YAML 字符串)。端到端离线跑。"""
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as td:
            js = os.path.join(td, "r.json")
            p = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts",
                            "verify_refs.py"),
                            "--claims", json.dumps([{"title": "T", "doi": "10.9999/x"}]),
                            "--out", os.path.join(td, "r.md"), "--json-out", js,
                            "--offline"], capture_output=True, text=True)
            d = json.load(open(js, encoding="utf-8"))
            self.assertIsInstance(d["bluf"], dict, "bluf 必须为对象(BLUF spec L1)")
            self.assertIn("verdict", d["bluf"])
            self.assertIsInstance(d.get("bluf_yaml"), str)  # 兼容字段在

    def test_t5_validator_passes_our_json(self):
        """自家校验器(bluf_spec)现在应 L1 PASS 我们的 JSON——规范闭环。"""
        import subprocess, tempfile
        val = os.path.expanduser("~/ZCodeProject/skill/bluf_spec/bluf_validator.py")
        if not os.path.exists(val):
            self.skipTest("校验器不在本机路径")
        with tempfile.TemporaryDirectory() as td:
            js = os.path.join(td, "r.json")
            subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts",
                            "verify_refs.py"),
                            "--claims", json.dumps([{"title": "T", "doi": "10.9999/x"}]),
                            "--out", os.path.join(td, "r.md"), "--json-out", js,
                            "--offline"], capture_output=True, text=True)
            r = subprocess.run([sys.executable, val, js], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)


class TestRetractionLocalCache(unittest.TestCase):
    def setUp(self):
        self._old = dict(vr._OPTS)
        vr._RETRACTION_CACHE[0] = None  # 重置惰性缓存

    def tearDown(self):
        vr._OPTS.clear()
        vr._OPTS.update(self._old)
        vr._RETRACTION_CACHE[0] = None

    def test_t6_hit_zero_network(self):
        """命中本地索引:零网络调用即返回撤稿。"""
        import tempfile, json as j
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            j.dump({"10.1000/x": {"date": "4/9/2026", "type": "Retraction",
                                  "reason": "r"}}, f)
            path = f.name
        vr._OPTS["retraction_cache"] = path
        with mock.patch.object(vr.urllib.request, "urlopen",
                               side_effect=AssertionError("不该走网络")):
            r, note = vr.crossref_retraction_check("10.1000/X", 5)  # 大小写不敏感
        self.assertTrue(r)
        self.assertIn("本地 Retraction Watch", note)

    def test_t7_miss_falls_to_network(self):
        """未命中:回退网络路径(此处模拟网络 404→False)。"""
        import tempfile, json as j
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            j.dump({"10.1000/x": {"date": "d", "type": "t"}}, f)
            path = f.name
        vr._OPTS["retraction_cache"] = path
        resp = type("R", (), {"read": lambda self: b"{}", "status": 404})
        class Boom(urllib.error.HTTPError if False else Exception):
            pass
        import urllib.error
        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {},
                                         __import__("io").BytesIO(b"{}"))
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=fake), \
             mock.patch.object(vr, "_cb_open", return_value=False), \
             mock.patch.object(vr, "_cb_record"):
            r, note = vr.crossref_retraction_check("10.9999/miss", 5)
        self.assertFalse(r)

    def test_t8_bad_cache_file_no_crash(self):
        """坏缓存文件=视为空,不炸主流程,回退网络。"""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            f.write("{broken json")
            path = f.name
        vr._OPTS["retraction_cache"] = path
        import urllib.error, io as _io
        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {},
                                         _io.BytesIO(b"{}"))
        with mock.patch.object(vr.urllib.request, "urlopen", side_effect=fake), \
             mock.patch.object(vr, "_cb_open", return_value=False), \
             mock.patch.object(vr, "_cb_record"):
            r, _ = vr.crossref_retraction_check("10.1/y", 5)
        self.assertFalse(r)

    def test_t9_unconfigured_none(self):
        vr._OPTS.pop("retraction_cache", None)
        self.assertIsNone(vr._retraction_local("10.1000/x"))


if __name__ == "__main__":
    unittest.main()
