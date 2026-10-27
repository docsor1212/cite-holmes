#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.1.0 测试骨架（release.py 自动生成——请填充本版特定断言）。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402


class TestVersion(unittest.TestCase):
    def test_version_bumped(self):
        self.assertEqual(vr.VERSION, "5.5.0")
        self.assertIn("version: 5.5.0",
                      open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
