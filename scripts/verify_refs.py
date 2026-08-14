#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_refs.py — cite-holmes skill 的引用机械验证器。

对研究引用清单做机器可判定的检查（可达性 / 域名权威度 / 字段完整性 / 去重），
输出五态判定报告（Markdown + JSON）。语义验证（来源是否真的支持论断）由模型
在研究流程中完成，本脚本不做语义判断。

五态：
  verified     可达 + 权威层(official/journal/preprint/media) + 字段完整
  partial      可达，但社区/博客层来源，或必填字段缺失
  unreachable  404/超时/反爬（needs_human_check，≠ 不存在）
  invalid      无 URL/DOI 或格式错误
  unverified   --offline 或跳过检查

纯标准库，跨平台（win32/linux/darwin），控频访问。
用法：
  python verify_refs.py --refs research_refs.json --out verify_report.md
  python verify_refs.py --claims '[{"title":"...","url":"https://...","source":"X","year":2026}]'
  python verify_refs.py --refs refs.json --offline        # 不联网，仅结构检查
  python verify_refs.py --refs refs.json --strict         # unreachable/invalid 视为失败(CI 用)
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse

VERSION = "1.0.0"

# ---------------- 输出编码（Windows GBK 控制台兜底） ----------------
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------- 域名权威度分层 ----------------
# 自上而下首个命中者生效；未命中默认 blog。
TIER_RULES = [
    ("official", [
        r"\.gov(\.[a-z]{2})?$", r"\.edu(\.[a-z]{2})?$", r"\.gov\.cn$", r"\.edu\.cn$",
        r"^docs\.", r"^developer\.", r"^documentation\.", r"^support\.",
        r"^www\.anthropic\.com$", r"^openai\.com$", r"^www\.nature\.com$",
        r"^www\.nejm\.org$", r"^www\.who\.int$", r"^www\.fda\.gov$",
        r"^www\.ema\.europa\.eu$", r"^arxiv\.org$", r"^www\.thelancet\.com$",
        r"^jamanetwork\.com$", r"^pubmed\.ncbi\.nlm\.nih\.gov$", r"^doi\.org$",
        r"^www\.sciencedirect\.com$", r"^link\.springer\.com$", r"^ieeexplore\.ieee\.org$",
        r"^www\.stats\.gov\.cn$", r"^www\.nhc\.gov\.cn$",
    ]),
    ("journal", [
        r"^pubmed\.ncbi\.nlm\.nih\.gov$", r"^doi\.org$", r"^journals?\.",
        r"^academic\.", r"^scholar\.", r"^kns\.", r"^oa\.cqvip\.com$", r"^yiigle\.com$",
    ]),
    ("preprint", [r"^arxiv\.org$", r"^biorxiv\.org$", r"^medrxiv\.org$", r"^ssrn\.com$", r"^chemrxiv\.org$"]),
    ("media", [
        r"^www\.reuters\.com$", r"^apnews\.com$", r"^www\.bbc\.", r"^www\.nytimes\.com$",
        r"^www\.bloomberg\.com$", r"^www\.ft\.com$", r"^www\.economist\.com$",
        r"^news\.yahoo\.com$", r"^www\.thepaper\.cn$", r"^www\.caixin\.com$",
        r"^www\.jiemian\.com$", r"^36kr\.com$", r"^www\.infoq\.cn$", r"^techcrunch\.com$",
        r"^www\.theverge\.com$", r"^arstechnica\.com$", r"^www\.wired\.com$",
    ]),
    ("community", [
        r"^github\.com$", r"^stackoverflow\.com$", r"^en\.wikipedia\.org$",
        r"^zh\.wikipedia\.org$", r"^www\.zhihu\.com$", r"^zhuanlan\.zhihu\.com$",
        r"^stackexchange\.com$", r"^www\.reddit\.com$", r"^news\.ycombinator\.com$",
        r"^www\.v2ex\.com$", r"^segmentfault\.com$", r"^juejin\.cn$",
    ]),
    ("social", [
        r"(^|\.)x\.com$", r"(^|\.)twitter\.com$", r"(^|\.)weibo\.com$", r"(^|\.)t\.me$",
        r"(^|\.)facebook\.com$", r"(^|\.)youtube\.com$", r"(^|\.)bilibili\.com$",
        r"(^|\.)douyin\.com$", r"(^|\.)xiaohongshu\.com$", r"(^|\.)medium\.com$",
    ]),
]
TRUSTED_TIERS = {"official", "journal", "preprint", "media"}

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
REQUIRED_FIELDS = ("title", "url", "source", "year")


def classify_tier(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "unknown"
    for tier, patterns in TIER_RULES:
        for pat in patterns:
            if re.search(pat, host):
                return tier
    return "blog"


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    return urlunparse((p.scheme.lower(), (p.netloc or "").lower(), p.path.rstrip("/"),
                       "", "", ""))


def check_url(url: str, timeout: float) -> tuple:
    """返回 (reachable, status, note)。reachable 以 2xx/3xx/429(反爬) 计。"""
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": "Mozilla/5.0 (compatible; cite-holmes/1.0; +verified-deep-research)",
        "Accept": "*/*",
    })
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    for method in ("HEAD", "GET"):
        try:
            req.method = method
            with opener.open(req, timeout=timeout) as resp:
                return True, resp.status, f"{method} {resp.status}"
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue  # 站点拒绝 HEAD，降级 GET 重试
            if e.code == 429:
                return True, 429, "HTTP 429（反爬限流，站点实际存在）"
            return False, e.code, f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            if method == "HEAD":
                continue
            return False, None, f"{type(e).__name__}: {e}"[:120]
    return False, None, "HEAD/GET 均失败"


def missing_fields(ref: dict) -> list:
    miss = [f for f in REQUIRED_FIELDS if not ref.get(f)]
    if "url" in miss and ref.get("doi") and DOI_RE.match(str(ref["doi"]).strip()):
        miss.remove("url")
    return miss


def verify_one(ref: dict, idx: int, offline: bool, timeout: float) -> dict:
    out = {"index": idx, "title": ref.get("title") or "(无标题)", "url": ref.get("url") or "",
           "source": ref.get("source") or "", "year": ref.get("year"),
           "tier": ref.get("tier") or "", "semantic": ref.get("semantic", ""),
           "verdict": "unverified", "http_status": None, "note": "", "needs_human_check": False}

    url = (ref.get("url") or "").strip() or (
        f"https://doi.org/{ref['doi'].strip()}" if ref.get("doi") else "")
    if not url:
        out.update(verdict="invalid", note="缺少 url 且无可解析的 doi")
        return out
    if not re.match(r"^https?://", url):
        out.update(verdict="invalid", note=f"url 非 http(s) 格式: {url[:60]}")
        return out

    if not out["tier"]:
        out["tier"] = classify_tier(url)
    out["url"] = url

    if offline:
        out["note"] = "offline 模式未做可达性检查"
    else:
        reachable, status, note = check_url(url, timeout)
        out["http_status"], out["note"] = status, note
        if not reachable:
            out.update(verdict="unreachable", needs_human_check=True,
                       note=f"{note}（可能反爬/临时故障，不等于不存在）")
            return out

    miss = missing_fields(ref)
    if out["tier"] in TRUSTED_TIERS and not miss:
        out["verdict"] = "verified"
    else:
        why = []
        if out["tier"] not in TRUSTED_TIERS:
            why.append(f"来源层级为 {out['tier']}（非权威层）")
        if miss:
            why.append(f"缺字段 {','.join(miss)}")
        out["verdict"] = "partial"
        out["note"] = (out["note"] + "；" if out["note"] else "") + "；".join(why)
    return out


def mark_duplicates(results: list) -> None:
    seen = {}
    for r in results:
        key = normalize_url(r["url"]) if r["url"] else None
        if key and key in seen:
            r["note"] = (r["note"] + "；" if r["note"] else "") + f"与 #{seen[key]} 重复（同 URL）"
            if r["verdict"] == "verified":
                r["verdict"] = "partial"
        elif key:
            seen[key] = r["index"]


VERDICT_ZH = {"verified": "✅ verified", "partial": "🟡 partial", "unreachable": "⚠️ unreachable",
              "invalid": "❌ invalid", "unverified": "⏸ unverified"}


def render_md(results: list, offline: bool) -> str:
    n = lambda v: sum(1 for r in results if r["verdict"] == v)
    lines = [
        "# 引用机械验证报告",
        f"- 验证器：verify_refs.py v{VERSION} · 模式：{'offline（未联网）' if offline else 'online'}",
        f"- 总计 {len(results)} 条：✅verified {n('verified')} · 🟡partial {n('partial')} · "
        f"⚠️unreachable {n('unreachable')} · ❌invalid {n('invalid')} · ⏸unverified {n('unverified')}",
        "",
        "| # | 标题 | 层级 | HTTP | 判定 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        title = str(r["title"]).replace("|", "\\|")[:48]
        lines.append(f"| {r['index']} | {title} | {r['tier']} | "
                     f"{r['http_status'] or '-'} | {VERDICT_ZH[r['verdict']]} | {r['note'] or '-'} |")
    flagged = [r for r in results if r["needs_human_check"] or r["verdict"] in ("invalid", "unverified")]
    if flagged:
        lines += ["", "## 待人工复核", ""]
        for r in flagged:
            lines.append(f"- #{r['index']} {r['title']} → {r['verdict']}：{r['note']}")
    lines += ["", "## 判定说明", "",
              "- `verified`：可达 + 权威层(official/journal/preprint/media) + 字段完整 —— 可支撑正文结论",
              "- `partial`：可达但社区/博客层来源，或字段缺失 —— 降级使用，结论需注明",
              "- `unreachable`：抓取失败（404/超时/反爬）—— 不等于不存在，需人工打开复核",
              "- `invalid`：无 URL/DOI 或格式错误 —— 不得进入报告",
              "- 语义验证（来源是否支持论断）由模型完成，本报告只覆盖机械层", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="deep-research 引用机械验证器（五态判定）")
    ap.add_argument("--refs", help="research_refs.json 路径")
    ap.add_argument("--claims", help="内联 JSON 引用数组（同 --refs 的 schema）")
    ap.add_argument("--out", default="verify_report.md", help="Markdown 报告输出路径")
    ap.add_argument("--json-out", help="JSON 报告输出路径（默认 <out>.json）")
    ap.add_argument("--offline", action="store_true", help="不联网，仅结构/字段检查")
    ap.add_argument("--strict", action="store_true", help="unreachable/invalid 计为失败（exit 1）")
    ap.add_argument("--timeout", type=float, default=10.0, help="单 URL 超时秒数（默认 10）")
    ap.add_argument("--interval", type=float, default=1.0, help="请求间隔秒数（默认 1.0）")
    args = ap.parse_args()

    if not args.refs and not args.claims:
        ap.error("需要 --refs 或 --claims 之一")
    try:
        refs = (json.loads(args.claims) if args.claims
                else json.load(open(args.refs, encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ 读取引用清单失败：{e}", file=sys.stderr)
        return 2
    if not isinstance(refs, list) or not refs:
        print("❌ 引用清单须为非空 JSON 数组", file=sys.stderr)
        return 2

    results = []
    for i, ref in enumerate(refs, 1):
        if not isinstance(ref, dict):
            results.append({"index": i, "title": str(ref)[:48], "url": "", "source": "",
                            "year": None, "tier": "-", "semantic": "", "verdict": "invalid",
                            "http_status": None, "note": "条目不是对象", "needs_human_check": False})
            continue
        r = verify_one(ref, i, args.offline, args.timeout)
        results.append(r)
        print(f"[{i}/{len(refs)}] {VERDICT_ZH[r['verdict']]} {r['title'][:40]}")
        if not args.offline and i < len(refs) and args.interval > 0:
            time.sleep(args.interval)

    mark_duplicates(results)
    md = render_md(results, args.offline)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    json_path = args.json_out or (args.out.rsplit(".", 1)[0] + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "offline": args.offline, "results": results},
                  f, ensure_ascii=False, indent=2)

    bad = [r for r in results if r["verdict"] in ("unreachable", "invalid")]
    print(f"\n报告：{args.out}\nJSON：{json_path}")
    if bad:
        print(f"⚠️ {len(bad)} 条 unreachable/invalid" + ("（strict 模式 → exit 1）" if args.strict else ""))
    return 1 if (args.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
