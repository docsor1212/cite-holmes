#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.3.0 留出集评测 runner（公开口径，任何人都可复现）。

评测对象：机械层判定（五态）。默认跑内置金标集（examples/demo_refs.json，
8 条其中 3 处预埋伪造——随包公开的设计性夹具）；--refs 指向带 expected
字段的标注集走同一核验栈。

指标（离线口径，逐项定义在 docs/benchmark.md）：
  capture_rate       预埋伪造被判非 verified 的比例（越高越好）
  strict_capture     预埋伪造被判 invalid 的比例（结构层能实锤的比例）
  false_kill_rate    非伪造条目被判 invalid 的比例（越低越好，误伤）
  distribution       五态判定分布

诚实边界：默认 --offline 只测结构层；online 注册库核验结果随上游数据
漂移，数字只对运行当日快照负责（docs/benchmark.md 有完整口径）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify_refs as vr  # noqa: E402

# 内置金标集的公开设计（examples/demo_refs.json 实测形态）：#6=假 DOI、
# #7=假 arXiv、#8=无任何标识符——offline 结构层实锤对象是 #8（缺标识符→
# invalid）；#6/#7 良构伪造 offline 诚实降 partial（docs/benchmark.md 边界 1）
GOLDEN_PLANTED = (6, 7, 8)
GOLDEN_CLEAN = (1, 2, 3, 4, 5)


def run_eval(refs_path: str = "", offline: bool = True) -> dict:
    """跑评测并返回指标 dict。refs_path 空=内置金标集。"""
    if refs_path:
        doc = json.load(open(refs_path, encoding="utf-8"))
        refs = doc["refs"] if isinstance(doc, dict) else doc
        exp = (doc.get("expected") if isinstance(doc, dict) else None) or {}
        planted = {int(k) for k, v in exp.items() if v == "planted"}
        clean = {int(k) for k, v in exp.items() if v == "clean"}
        assert planted or clean, "标注集须含 expected: {\"1\": \"planted\"|\"clean\", ...}"
    else:
        _demo = os.path.join(HERE, "..", "examples", "demo_refs.json")
        refs = json.load(open(_demo, encoding="utf-8"))
        planted, clean = set(GOLDEN_PLANTED), set(GOLDEN_CLEAN)
    results = []
    for i, ref in enumerate(refs, 1):
        results.append(vr.verify_one(ref, i, offline, 10.0, False))
    v = {r["index"]: r["verdict"] for r in results}
    n_planted, n_clean = len(planted), len(clean)
    captured = sum(1 for i in planted if v.get(i) not in (None, "verified"))
    strict = sum(1 for i in planted if v.get(i) == "invalid")
    killed = sum(1 for i in clean if v.get(i) == "invalid")
    dist = {}
    for r in results:
        dist[r["verdict"]] = dist.get(r["verdict"], 0) + 1
    return {
        "version": vr.VERSION,
        "mode": "offline 结构层" if offline else "online 注册库",
        "n": len(refs),
        "capture_rate": round(captured / n_planted, 4) if n_planted else None,
        "strict_capture": round(strict / n_planted, 4) if n_planted else None,
        "false_kill_rate": round(killed / n_clean, 4) if n_clean else None,
        "distribution": dist,
        "per_ref": {str(i): v.get(i) for i in sorted(v)},
    }


def render_md(m: dict) -> str:
    def _pct(x):
        return f"{x:.0%}" if isinstance(x, (int, float)) else "—（无该侧样本）"
    lines = ["# 留出集评测摘要（cite-holmes 公开口径）", "",
             f"- 引擎：v{m['version']} · 模式：{m['mode']} · 条数：{m['n']}",
             f"- 捕获率 capture_rate：{_pct(m['capture_rate'])}（预埋伪造被判非 verified）",
             f"- 实锤率 strict_capture：{_pct(m['strict_capture'])}（预埋伪造被判 invalid）",
             f"- 误伤率 false_kill_rate：{_pct(m['false_kill_rate'])}（非伪造被判 invalid）",
             f"- 判定分布：{m['distribution']}",
             "", "复现：python tools/run_eval.py（默认内置金标集 offline 口径）；"
             "完整方法论与历史数字见 docs/benchmark.md。"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="cite-holmes 留出集评测（公开口径）")
    ap.add_argument("--refs", default="", help="标注集 JSON（含 expected 字段；缺省用内置金标集）")
    ap.add_argument("--net", action="store_true", help="online 注册库口径（数字只对当日快照负责）")
    ap.add_argument("--json-out", default="eval_result.json")
    ap.add_argument("--md-out", default="eval_summary.md")
    args = ap.parse_args()
    m = run_eval(args.refs, offline=not args.net)
    try:  # 审计 P2-2：输出不可写=友好失败（对齐 v5.2 自立标准）
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        with open(args.md_out, "w", encoding="utf-8") as f:
            f.write(render_md(m))
    except OSError as e:
        print(f"评测输出写入失败：{type(e).__name__}（{args.json_out} / {args.md_out}）",
              file=sys.stderr)
        return 2
    print(render_md(m))
    print(f"JSON：{args.json_out}\nMD：{args.md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
