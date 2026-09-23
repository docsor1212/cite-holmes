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
  python verify_refs.py --refs refs.json --profile medical # 医学信源预设(期刊层域名扩展+社区层降级警示)
  python verify_refs.py --refs refs.json --export bibtex,csv # 导出verified-only参考文献(bibtex)+全量台账(csv)

引用字段支持 url / doi / pmid / arxiv 四选一（pmid 自动解析为 PubMed 页面，arxiv 自动解析为
arXiv abs 页面），去重覆盖 URL+DOI+PMID 及 arXiv 解析后的 URL。
v1.5：arXiv ID 元数据校验（export.arxiv.org 官方 API，不存在的 ID 直接判 invalid，
不被可达性检查误判 unreachable——沿用 DOI 元数据先行的判定顺序）；unreachable 条目
自动查 Wayback Machine 存档（有存档附对照链接，人工复核有抓手）。
v1.6：主机断路器（同一主机连续 2 次传输层失败 → 本批次跳过该主机外呼并诚实备注，
断网环境不再整批卡死）；可操作报错（超时给 --timeout 20 建议、DNS/拒连分类措辞、
待人工复核区加建议动作）；DOI↔PMID 交叉一致性（双键引用互证，抓「真 ID 拼接」伪造）；
期刊名一致性核查（复用 DOI 登记元数据，不符降 partial——抓「真 DOI 真论文假期刊」）。
v1.7：作者名一致性核查（复用 CSL author，任一姓氏命中即一致，全部不命中降 partial）；
能力边界矩阵（报告尾部结构化呈现已抓/未抓伪造类型）；--format html 自包含单文件报告
（零外链、移动端可读，给导师/编辑的分享件）。
v1.8：撤稿检测（Crossref/Retraction Watch API——真实存在的论文也可能已撤稿，
撤稿引用封顶 partial 并转入人工复核）；OpenAlex 书目级存在性核查（无 DOI/PMID/arXiv
的引用多一路正面确认信号，只确认不降级——收录有滞后，查无 ≠ 编造）；元数据端点
UA 轮换重试（403/406 韧性）；--easy 医学误触发修复。
v1.9：Semantic Scholar 第三源交叉确认（DOI 元数据获取失败时的第二路正面信号——
只确认不降级，S2 记录质量参差实测有误记，绝不以其不一致作负面判据）；
BibTeX 导入（--refs refs.bib 自动识别，Zotero/EndNote 导出文件零改造直查）；
OpenAlex API key 支持（2026-02 起生产调用需 key：--openalex-key 或环境变量）；
--mailto 进入 Crossref polite pool（机构用户限速更宽松）+ 429 Retry-After 遵从；
投稿前结论（arXiv 2026-05 起对含幻觉/未核引用投稿实施处罚——报告头部直接给出
可否提交的结论行）；--export auditjson 透明工作底稿（每条引用的逐项检查明细，
机器可读，回应"检测系统需要透明多源"的行业呼吁）。
v1.11：判定确定性保卫——arXiv API 偶发 406/403（批内多请求撞其反机器人窗口）
时不再静默跳过内容核验，指数退避重试后 fallback 官方着陆页 arxiv.org/abs/<id>
做标题比对（复用 0.50/0.82 阈值；着陆页 404 判 invalid），同一引用两次运行判定
不再漂移，并补齐与 DOI 路径（S2 第二源）的对称性；语义层工作底稿结构化
（semantic 字段支持 {claim, support, quote, note} 对象，auditjson/报告透出
semantic_audit 区；not_in_source/contradicted 封顶 partial+人工复核——把
「disclosing uncertainty」落成机器可读）；投稿前结论修正为 arXiv 2026-05 起
处罚并补会议（ICML 2026 桌拒）话术。
v1.10：引用级并行验证（--workers，默认 4——条与条相互独立，整批耗时约 ÷workers，
直攻「跨国数据库验证慢」）；全局网络降级模式（批内 ≥3 个不同主机传输层失败 →
其余外呼快速诚实跳过并给可操作建议，把「等很久」变成「快速结论」）；
Semantic Scholar 标题检索确认（无 DOI/PMID/arXiv 引用的第三路正面信号，只确认
不降级；query 连字符空格化——S2 官方文档确认连字符查询无结果）；批内结果缓存
（同 DOI/URL 二次出现复用判定，不重复外呼）；降级态快速失败（传输失败不再重试）。
v1.12：持久磁盘缓存（--cache 默认开，sqlite3 标准库存 ~/.cache/cite-holmes/，TTL 默认
168h——复跑不再出国，直攻评测 T 维；--strict 强制绕过保 CI 诚实；--refresh-cache
强制重验）；--proxy 显式代理；能力矩阵新增「不支持输入」行；包内私有工具清除。
"""

import argparse
import csv
import difflib
import hashlib
import ipaddress
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape as html_escape
from urllib.parse import urlparse, urlunparse, quote

VERSION = "1.12.0"

# ---------------- 可选配置（v1.9，main() 按命令行/环境覆写） ----------------
# OpenAlex 2026-02 起生产调用需 API key（每日免费额度）；Semantic Scholar 免钥
# 走共享限速池，带 key 独享 1 req/s。mailto 用于 Crossref polite pool（限速更宽松）。
_OPTS = {"openalex_key": "", "s2_key": "", "mailto": ""}


# ---------------- 主机断路器（v1.6，国内适配主攻）+ 全局网络降级（v1.10） ----------------
# 同一主机连续 _CB_THRESHOLD 次传输层失败（超时/连接重置/DNS 解析失败）→ 本批次内
# 跳过该主机的后续外呼并诚实备注，避免断网环境整批卡死（评测："需要等网络响应"）。
# HTTP 层失败（404/403/429 等站点有响应的情况）不触发熔断。main() 每次运行重置。
# v1.10 并行验证引入 _CB_LOCK：_cb_record 的「累计→熔断」是读改写序列，多 worker
# 并发下必须串行化（CPython dict 单操作原子不覆盖 check-then-act）。
# v1.10 全局网络降级：批内 ≥_NET_DEGRADE_THRESHOLD 个「不同主机」传输层失败 →
# 判定出海受限，未确认过成功的主机全部快速跳过（诚实备注+建议），不再逐主机烧超时
# ——评测 T 维失分点「国内网络偶有卡顿」的机制层缓解：等很久 → 快速结论。
_CB_THRESHOLD = 2
_CB = {}
_CB_LOCK = threading.Lock()
_NET_DEGRADE_THRESHOLD = 3
_NET_STATE = {"fail_hosts": set(), "ok_hosts": set(), "degraded": False}


def _net_reset() -> None:
    with _CB_LOCK:
        _CB.clear()
        _NET_STATE["fail_hosts"] = set()
        _NET_STATE["ok_hosts"] = set()
        _NET_STATE["degraded"] = False


def _cb_host(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{(p.hostname or '').lower()}" if p.hostname else ""


def _cb_open(url: str) -> bool:
    """该主机是否应跳过外呼：单主机熔断，或（v1.10）全局降级下从未成功过的主机。"""
    h = _cb_host(url)
    with _CB_LOCK:
        st = _CB.get(h)
        if st and st["open"]:
            return True
        return _NET_STATE["degraded"] and h not in _NET_STATE["ok_hosts"]


def _cb_skip_note(url: str) -> str:
    h = _cb_host(url)
    with _CB_LOCK:
        degraded = _NET_STATE["degraded"] and h not in _NET_STATE["ok_hosts"]
    if degraded:
        return ("全局网络降级：本批次已有多个外部主机连续传输失败（出海受限特征），"
                "跳过本次外呼（建议配置代理/更换网络后重跑），本条仅按结构/其他信息判定")
    return (f"网络断路器：{h} 本批次已连续 {_CB_THRESHOLD} 次传输失败，"
            "跳过本次外呼（避免整批卡死），本条仅按结构/其他信息判定")


def _cb_record(url: str, transport_fail: bool, degrade: bool = None) -> None:
    """transport_fail=True 记一次传输层失败（累计到阈值即熔断）；
    False（拿到任意 HTTP 响应或成功）清零。v1.10：同时维护全局降级状态。
    degrade 显式传 False 表示「计入单主机熔断但不计入全局降级」——用于站点有
    HTTP 响应却被个别函数按传输失败记账的路径（如 OpenAlex 403/429、Crossref
    限流）：出海链路本身是通的，不能因为站点级反爬/限流就判定全局网络受限。"""
    h = _cb_host(url)
    if not h:
        return
    if degrade is None:
        degrade = transport_fail
    with _CB_LOCK:
        st = _CB.setdefault(h, {"fails": 0, "open": False})
        if transport_fail:
            st["fails"] += 1
            if st["fails"] >= _CB_THRESHOLD:
                st["open"] = True
            if degrade and not _NET_STATE["degraded"] and h not in _NET_STATE["ok_hosts"]:
                _NET_STATE["fail_hosts"].add(h)
                if len(_NET_STATE["fail_hosts"]) >= _NET_DEGRADE_THRESHOLD:
                    _NET_STATE["degraded"] = True
        else:
            st["fails"] = 0
            _NET_STATE["ok_hosts"].add(h)
            _NET_STATE["fail_hosts"].discard(h)

# ---------------- 公共安全/转义帮手（v1.4 评审加固） ----------------

def ssrf_blocked(url: str) -> bool:
    """SSRF 字面量防护：URL 主机部分写明回环/内网/链路本地/保留 IP 或 localhost
    时拒绝请求。**刻意不做 DNS 解析判定**——污染网络环境下解析结果不可信，
    会把正常域名误判成内网地址（实测 pubmed/doi.org 均被解析污染误伤）。
    域名类 URL 的 DNS 层防护不在本工具承诺内。"""
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost") or \
            host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        addr = ipaddress.ip_address(host)  # 仅当主机部分本身就是 IP 字面量
    except ValueError:
        return False
    return (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_multicast)


def md_cell(text, limit=90):
    """Markdown 表格单元格转义：竖线转义、换行剥除、截断。"""
    t = str(text if text is not None else "")
    t = t.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return t[:limit]


def csv_safe(cell: str) -> str:
    """CSV 公式注入中和（OWASP 做法）：= + - @ 制表符 回车 开头的单元格前置单引号。"""
    c = str(cell)
    if c[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + c
    return c


def bib_safe(value: str) -> str:
    """BibTeX 字段值加固：剥除花括号与换行/控制字符，防 @entry 逃逸。"""
    v = str(value if value is not None else "")
    return v.replace("{", "").replace("}", "").replace("\r", " ").replace("\n", " ")

# ---------------- CiteScore 置信度评分（v1.3.0） ----------------
# 五态加权：verified +10 / partial +4 / unreachable 0 / unverified -2 / invalid -8
# 归一化到 0-100，等级 A(>=85) B(70-84) C(50-69) D(<50)
SCORE_WEIGHTS = {"verified": 10, "partial": 4, "unreachable": 0,
                 "unverified": -2, "invalid": -8}


def compute_scorecard(results: list) -> dict:
    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in SCORE_WEIGHTS}
    n = len(results)
    raw = sum(SCORE_WEIGHTS[v] * c for v, c in counts.items())
    score = round(100 * max(raw, 0) / (10 * n)) if n else 0
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"
    return {"score": score, "grade": grade, "total": n,
            "counts": counts, "weights": SCORE_WEIGHTS}


def _norm_name(s) -> str:
    """人名/期刊名规范化：小写、只留字母数字与 CJK。"""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(s or "").lower())


def _claimed_surnames(authors: str) -> list:
    """从 "Smith J, Zhang W, 王五" 形式的作者串提取姓氏 token（每段第一个词）。"""
    out = []
    for part in re.split(r"[,，;；、]", str(authors or "")):
        toks = part.strip().split()
        if toks:
            out.append(toks[0])
    return out


def _author_consistent(claimed: list, csl_authors) -> bool:
    """声称姓氏与 CSL 登记作者列表比对：任一命中即一致（拼写/变体从宽）。
    v1.7 二轮评审修正：①跨语言不可比（中文译名 vs 拼音登记）跳过判定——
    与期刊核查同款守卫；②单字母 initial 不参与子串匹配（防 "L."/"G." 命中
    无关长名，使检查对 APA 格式与长作者列表失效）；③规范化后为空的声称
    token 跳过。登记列表缺失或无声称作者 → 跳过判定。"""
    reg = []
    for a in csl_authors or []:
        if not isinstance(a, dict):
            continue
        for k in ("family", "given", "name"):
            v = _norm_name(a.get(k))
            if v:
                reg.append(v)
    claimed_n = [c for c in (_norm_name(x) for x in claimed) if c]
    if not reg or not claimed_n:
        return True

    def _has_cjk(s: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)

    # 跨语言不可比：声称侧含 CJK 而登记侧全拉丁（或反之）→ 跳过判定
    if _has_cjk(claimed_n[0]) != any(_has_cjk(r) for r in reg):
        return True
    for c in claimed_n:
        for r in reg:
            if c == r:
                return True
            if len(c) >= 2 and len(r) >= 2 and (c in r or r in c):
                return True
    return False


def capability_matrix() -> dict:
    """能力边界矩阵（v1.7）：机械层已抓伪造类型 vs 仍需语义层把关的类型。
    结构化呈现边界——「不能做什么」与「能做什么」同样值得写清楚。"""
    return {
        "caught": [
            "假 DOI（DOI.org 查无）", "真 DOI 配假论文（错引/张冠李戴）",
            "假 PMID（E-utilities 查无）", "假 arXiv ID（官方 API 查无）",
            "DOI↔PMID 拼接（两键各真但指向不同论文）", "期刊名不符", "作者名不符",
            "真实但已撤稿（Crossref/Retraction Watch 撤稿库）",
            "死链/不可达（自动附 Wayback 存档对照）", "重复引用（URL/DOI/PMID 三键去重）",
        ],
        "semantic": [
            "指向真实、可信页面的精心伪造——内容是否真支撑论断由模型的语义层判断"
            "（research_refs.json 的 semantic 字段），机械层不承诺捕获",
        ],
        "unsupported": [
            "PDF/Word 文档直读（请先手工提取引用条目再投喂）",
            "万方号/维普号等中文库专属编号（可经 URL 或标题间接核验）",
            "网页所述事实本身的对错（机械层只验来源存在与一致性，语义层归模型/人工）",
        ],
    }

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
        r"^www\.ema\.europa\.eu$", r"^arxiv\.org$", r"^export\.arxiv\.org$",
        r"^www\.thelancet\.com$",
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

# ---------------- 医学信源预设（--profile medical 时并入 journal 层） ----------------
MEDICAL_JOURNAL_PATTERNS = [
    r"\.cochranelibrary\.com$", r"^bestpractice\.bmj\.com$", r"^www\.bmj\.com$",
    r"^www\.embase\.com$", r"^clinicaltrials\.gov$", r"^www\.chinacdc\.cn$",
    r"^www\.cdc\.gov$", r"^www\.nmpa\.gov\.cn$", r"^www\.nice\.org\.uk$",
    r"\.wanfangdata\.com\.cn$", r"^guide\.medlive\.cn$", r"^rs\.yiigle\.com$",
    r"^(www\.)?chictr\.org\.cn$",
]

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
PMID_RE = re.compile(r"^\d{6,9}$")
# arXiv ID：新式 YYMM.NNNNN——MM 限 01-12（月份段非法的伪 ID 会让官方 API 挂起，
# 必须在客户端拒掉）——可带 v2 版本号；旧式 类目/编号（hep-th/9901001、math.GT/0309136）
ARXIV_NEW_RE = re.compile(r"^\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}(v\d+)?$", re.IGNORECASE)
ARXIV_OLD_RE = re.compile(r"^[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(v\d+)?$", re.IGNORECASE)
ARXIV_URL_RE = re.compile(
    r"^https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|format)/"
    r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7}|\d{2}(?:0[1-9]|1[0-2])\.\d{4,5})(v\d+)?", re.IGNORECASE)
REQUIRED_FIELDS = ("title", "url", "source", "year")


def extract_arxiv_id(ref: dict) -> str:
    """从引用中提取 arXiv ID（v1.5）：显式 arxiv 字段优先（支持 "arXiv:" 前缀），
    其次识别 url 中的 arxiv.org/abs|pdf/<id>。格式校验通过才返回，否则 ""。"""
    raw = str(ref.get("arxiv") or "").strip()
    if not raw:
        m = ARXIV_URL_RE.match(str(ref.get("url") or "").strip())
        if m:
            raw = m.group(1) + (m.group(2) or "")
    raw = re.sub(r"(?i)^arxiv\s*:\s*", "", raw).strip()
    if ARXIV_NEW_RE.match(raw) or ARXIV_OLD_RE.match(raw):
        return raw
    return ""


def classify_tier(url: str, medical: bool = False) -> str:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "unknown"
    for tier, patterns in TIER_RULES:
        for pat in patterns:
            if re.search(pat, host):
                return tier
    if medical:
        for pat in MEDICAL_JOURNAL_PATTERNS:
            if re.search(pat, host):
                return "journal"
    return "blog"


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    return urlunparse((p.scheme.lower(), (p.netloc or "").lower(), p.path.rstrip("/"),
                       "", "", ""))


PUBMED_URL_RE = re.compile(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?$")


def doi_metadata_match(doi: str, title: str, year, timeout: float,
                       source: str = "", authors: str = "") -> tuple:
    """DOI 元数据交叉验证（v1.4）：doi.org 内容协商取官方登记的 CSL 元数据，
    与引用声称的标题/年份比对——专抓「真 DOI 假论文」这类最像真引用的伪造。
    v1.6 新增：期刊名一致性核查（复用已取回的 container-title，零网络成本；
    不符降 partial——期刊改名常见，不判 invalid），抓「真 DOI 真论文假期刊」。
    v1.7 新增：作者名一致性核查（复用 CSL author 列表；声称姓氏至少一个命中
    登记列表即视为一致——拼写/变体从宽；全部不命中才降 partial）。
    瞬态网络错误自动重试一次。主机断路器生效。
    返回 (adjust, note, matched)：adjust ∈ {"", "partial", "invalid"}；
    matched=True 表示元数据成功取得且与声称标题一致。"""
    import difflib
    cb_url = f"https://doi.org/{doi}"
    if _cb_open(cb_url):
        return "", _cb_skip_note(cb_url) + "，未做 DOI 元数据核验", False
    mailto = _OPTS.get("mailto") or ""
    # doi.org 走 UA 联系方式（不加 query 参数——避免干扰个别 DOI 的解析行为）；
    # api.crossref.org 才用 ?mailto= polite pool 约定
    ua_contact = (f"cite-holmes/{VERSION}; +verified-deep-research "
                  "(https://skillhub.cn/skills/cite-holmes)")
    if mailto:
        ua_contact += f" mailto:{mailto}"
    req_url = cb_url
    ua_rot = [ua_contact,
              f"Mozilla/5.0 (compatible; cite-holmes/{VERSION}; +verified-deep-research)"]
    meta, fetch_err = None, ""
    retry_after = 0.0
    for attempt in range(2):
        req = urllib.request.Request(
            req_url, headers={
                "Accept": "application/vnd.citationstyles.csl+json",
                "User-Agent": ua_rot[min(attempt, 1)]})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                meta = json.loads(resp.read().decode("utf-8", "ignore"))
            fetch_err = ""
            _cb_record(cb_url, False)
            break
        except urllib.error.HTTPError as e:
            _cb_record(cb_url, False)
            if e.code == 404:
                return "invalid", "DOI 在 DOI.org 不存在（404）→ 疑似编造引用", False
            fetch_err = f"HTTP {e.code}"
            if e.code == 429:
                # v1.9：限速分层后的礼貌退避——尊重 Retry-After（封顶 5 秒）
                retry_after = 2.0
                try:
                    if e.headers and e.headers.get("Retry-After"):
                        retry_after = min(5.0, max(1.0, float(e.headers["Retry-After"])))
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            fetch_err = type(e).__name__
        if attempt == 0:
            time.sleep(retry_after if retry_after else 1.2)  # 瞬态抖动/限流稍候重试
    if meta is None:
        _cb_record(cb_url, True)  # 整次调用只记 1 次传输失败（重试是同一逻辑失败）
        return "", f"DOI 元数据获取失败（{fetch_err}），跳过内容核验", False
    mt = meta.get("title")
    meta_title = (mt[0] if isinstance(mt, list) else mt) or ""
    sim = difflib.SequenceMatcher(None, (title or "").lower(),
                                  str(meta_title).lower()).ratio()
    meta_year = None
    parts = (meta.get("issued") or {}).get("date-parts") or []
    if parts and parts[0]:
        meta_year = parts[0][0]
    # v1.6 期刊名一致性核查（零网络成本）：规范化后互不包含视为不符，
    # 降 partial（期刊改名常见，不判 invalid）。
    # 二轮评审 P1 修正：NLM 式缩写（N Engl J Med vs New England Journal of
    # Medicine）不算不符——短名各词按序匹配长名词首（可跳过虚词）即视为同一
    # 期刊；跨语言（拉丁 vs CJK）不具可比性，跳过判定。
    ct = meta.get("container-title")
    reg_journal = (ct[0] if isinstance(ct, list) and ct else ct) or ""
    jadj, jnote = "", ""
    src = (source or "").strip()
    if reg_journal and src:
        def _nj(s):
            return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(s).lower())

        def _tokens(s):
            return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", str(s).lower())

        def _is_abbrev(short_toks, long_toks):
            j = 0
            for st in short_toks:
                while j < len(long_toks) and not (
                        long_toks[j].startswith(st) or st[0] == long_toks[j][0]):
                    j += 1
                if j >= len(long_toks):
                    return False
                j += 1
            return True

        def _journal_same(x, y):
            a, b = _nj(x), _nj(y)
            if not a or not b:
                return True
            # 跨语言不可比（如中文译名 vs 英文登记名）：不判不符
            a_cjk = any("\u4e00" <= c <= "\u9fff" for c in a)
            b_cjk = any("\u4e00" <= c <= "\u9fff" for c in b)
            if a_cjk != b_cjk:
                return True
            if a in b or b in a:
                return True
            ta, tb = _tokens(x), _tokens(y)
            return _is_abbrev(ta, tb) or _is_abbrev(tb, ta)

        if not _journal_same(src, reg_journal):
            jadj = "partial"
            jnote = (f"；期刊名不符（声称 {str(src)[:40]} / DOI 登记 "
                     f"{str(reg_journal)[:40]}）→ 建议核对是否引错论文")
    # v1.7 作者名一致性核查（复用 CSL author，零网络成本）：任一声称姓氏命中
    # 登记列表即视为一致（拼写/变体从宽）；全部不命中才降 partial。
    aadj, anote = "", ""
    claimed = _claimed_surnames(authors)
    if claimed and not _author_consistent(claimed, meta.get("author")):
        aadj = "partial"
        more = " 等" if len([c for c in (_norm_name(x) for x in claimed) if c]) > 1 else ""
        anote = (f"；作者不符（声称 {claimed[0]}{more} 未见于 DOI 登记作者列表）"
                 f"→ 建议核对是否引错论文")
    if not title:
        return (jadj or aadj), (f"DOI 元数据核验完成（引用未提供标题，无法比对；"
                                f"登记年份 {meta_year or '未知'}）{jnote}{anote}"), True
    if title and sim < 0.50:
        return "invalid", (f"DOI 元数据标题相似度仅 {sim:.2f} → DOI 指向的不是这篇论文，"
                           f"疑似编造或错引（DOI 实际为《{str(meta_title)[:60]}》）"), True
    year_note = ""
    if meta_year and year:
        try:
            if abs(int(year) - int(meta_year)) >= 2:
                year_note = f"；年份不符（声称 {year} vs DOI 登记 {meta_year}）"
        except (TypeError, ValueError):
            pass
    if title and sim < 0.82:
        return "partial", f"DOI 元数据标题相似度 {sim:.2f}，建议人工复核{year_note}{jnote}{anote}", True
    return (jadj or aadj), f"DOI 元数据核验一致（相似度 {sim:.2f}）{year_note}{jnote}{anote}", True


_NCBI_LAST = [0.0]
_NCBI_LOCK = threading.Lock()


def _ncbi_rate_wait():
    """E-utilities 免钥上限 3 req/秒（超限封 IP）。v1.10 并行验证下必须全局
    串行化：锁内等足 0.4 秒间隔（2.5 req/s，留安全余量），与 arXiv/S2 同模式。"""
    with _NCBI_LOCK:
        wait = 0.4 - (time.time() - _NCBI_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _NCBI_LAST[0] = time.time()


def pubmed_pmid_exists(pmid: str, timeout: float) -> tuple:
    """经 NCBI E-utilities 核实 PMID 真实存在。

    PubMed 网页对不存在的 PMID 也返回 2xx/203（且带反爬壳页），HTTP 状态码
    无法区分真假——AI 编造的 PMID 必须靠 API 核实才能抓住。
    返回 (exists, note)。
    """
    u = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
         f"?db=pubmed&id={pmid}&retmode=json")
    if _cb_open(u):
        return True, _cb_skip_note(u) + "，按可达处理"
    _ncbi_rate_wait()
    try:
        req = urllib.request.Request(
            u, headers={"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            j = json.loads(resp.read().decode("utf-8", "ignore"))
        _cb_record(u, False)
        res = j.get("result") or {}
        item = res.get(str(pmid)) or {}
        if item.get("error") or str(pmid) not in (res.get("uids") or []):
            return False, "PMID 在 PubMed 不存在（E-utilities 核实）→ 疑似编造引用"
        return True, "PMID 经 E-utilities 核实存在"
    except urllib.error.HTTPError as e:
        _cb_record(u, False)
        return True, f"E-utilities 校验失败（HTTP {e.code}），按可达处理"
    except Exception as e:
        _cb_record(u, True)
        return True, f"E-utilities 校验失败（{type(e).__name__}），按可达处理"


def pmid_doi_crosscheck(pmid: str, doi: str, timeout: float) -> tuple:
    """v1.6 DOI↔PMID 交叉一致性：两键各自真实也可能「拼接造假」（PMID 是 A 论文的、
    DOI 是 B 论文的）。取 PMID 在 PubMed 登记的 DOI 与声称 DOI 比对：
    不一致 → invalid「拼接伪造特征」；一致 → 加一致备注；登记无 DOI → 跳过。
    返回 (adjust, note)，adjust ∈ {"", "invalid"}。断路器生效。"""
    u = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
         f"?db=pubmed&id={pmid}&retmode=json")
    if _cb_open(u):
        return "", _cb_skip_note(u) + "，DOI↔PMID 交叉未做"
    _ncbi_rate_wait()
    try:
        req = urllib.request.Request(
            u, headers={"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            j = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        _cb_record(u, False)
        return "", f"E-utilities 交叉查询失败（HTTP {e.code}），跳过 DOI↔PMID 交叉"
    except Exception as e:
        _cb_record(u, True)
        return "", f"E-utilities 交叉查询失败（{type(e).__name__}），跳过 DOI↔PMID 交叉"
    _cb_record(u, False)
    res = j.get("result") or {}
    item = res.get(str(pmid)) or {}
    reg = ""
    for a in item.get("articleids") or []:
        if a.get("idtype") == "doi":
            reg = (a.get("value") or "").strip()
            break
    if not reg:
        return "", "PMID 未登记 DOI，跳过 DOI↔PMID 交叉"
    if reg.lower().rstrip(".").rstrip("/") == doi.lower().strip().rstrip(".").rstrip("/"):
        return "", "DOI↔PMID 交叉一致（两键指向同一论文）"
    return "invalid", (f"DOI 与 PMID 指向不同论文（PMID {pmid} 登记为 {reg}，"
                       f"引用声称 {doi}）→ 拼接伪造特征，疑似编造引用")


_ARXIV_LAST = [0.0]
_ARXIV_LOCK = threading.Lock()


def _arxiv_rate_wait():
    """export.arxiv.org 官方礼貌上限：同一客户端 ≥3 秒/请求（仅 arXiv 查询互相控频）。
    v1.10：加锁——并行 worker 下也保持全局限速（先到者持锁等待，计时刻整体串行）。"""
    with _ARXIV_LOCK:
        wait = 3.0 - (time.time() - _ARXIV_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _ARXIV_LAST[0] = time.time()


def _arxiv_landing_fallback(arxiv_id: str, title: str, timeout: float,
                            api_err: str) -> tuple:
    """v1.11 arXiv 第二源 fallback（判定确定性保卫）：export.arxiv.org API 偶发
    406/403——批内多条 arXiv 引用时即便有 3 秒全局控频仍可撞上其反机器人窗口
    （实测单发全 200、批内稳定 406）。此前 API 失败即静默跳过内容核验，导致同一
    引用两次运行判定漂移（verified↔partial，GESIS 立场论文 arXiv:2607.22693
    批评的「inconsistent results across repeated runs of the same tool」）。
    fallback 拉官方着陆页 arxiv.org/abs/<id>（权威层）做标题比对，恢复确定性，
    并补齐与 DOI 路径（S2 第二源）的对称性。着陆页也不可达（全网降级特征）→
    维持可达性路径判定，但 note 明示「元数据核验未完成」，不静默。
    返回 (adjust, note, matched)，语义同 arxiv_metadata_match。"""
    landing = "https://arxiv.org/abs/" + quote(arxiv_id, safe="")
    if ssrf_blocked(landing):  # 与 wayback 同款守卫（域名固定，防御性一致）
        return "", (f"arXiv 元数据获取失败（{api_err}），着陆页核验跳过（SSRF 防护），"
                    "元数据核验未完成"), False
    if _cb_open(landing):
        return "", (f"arXiv 元数据获取失败（{api_err}），着陆页核验跳过（断路器/降级），"
                    "元数据核验未完成"), False
    req = urllib.request.Request(
        landing,
        headers={"User-Agent": f"Mozilla/5.0 (compatible; cite-holmes/{VERSION};"
                               " +verified-deep-research)",
                 "Accept": "text/html"})
    html_text, err = None, ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_text = resp.read().decode("utf-8", "ignore")
        _cb_record(landing, False)
    except urllib.error.HTTPError as e:
        # 站点有响应（HTTP 层失败）——走熔断清零记账，不计全局传输失败（与
        # _cb_record 的 degrade 语义一致：arxiv.org 可达≠全网通，不能误判降级）
        _cb_record(landing, False)
        if e.code == 404:
            # 官方着陆页 404 = 官方库查无该 ID（与 verify_one 的 abs 域 404 判定一致）
            return "invalid", (f"arXiv 元数据 API 失败（{api_err}）后官方着陆页亦 404 → "
                               "官方库查无该 ID，疑似编造引用"), False
        err = f"HTTP {e.code}"
    except Exception as e:  # 传输层失败（超时/DNS/拒连）——如实记账
        _cb_record(landing, True)
        err = type(e).__name__
    if html_text is None:
        return "", (f"arXiv 元数据获取失败（{api_err}）且官方着陆页不可达（{err}），"
                    "元数据核验未完成——本条仅按可达性/结构判定"), False
    m = re.search(r"<title>(.*?)</title>", html_text, re.S | re.IGNORECASE)
    if not m:
        return "", (f"arXiv 元数据获取失败（{api_err}），着陆页无标题可比对，"
                    "元数据核验未完成"), False
    page_title = re.sub(r"\s+", " ", m.group(1)).strip()
    # arXiv abs 页 <title> 形如 "[2607.22693] 标题"——剥掉 ID 前缀再比对
    page_title = re.sub(r"^\[" + re.escape(arxiv_id) + r"\]\s*", "", page_title,
                        count=1)
    sim = difflib.SequenceMatcher(None, (title or "").lower(),
                                  page_title.lower()).ratio()
    if title and sim < 0.50:
        return "invalid", (f"arXiv 元数据 API 失败（{api_err}），官方着陆页标题相似度"
                           f"仅 {sim:.2f} → ID 指向的不是这篇论文，疑似错引"
                           f"（arXiv 实际为《{page_title[:60]}》）"), True
    if title and sim < 0.82:
        return "partial", (f"arXiv 元数据 API 失败（{api_err}），官方着陆页标题相似度 "
                           f"{sim:.2f}，建议人工复核"), True
    note = (f"arXiv 元数据 API 不稳（{api_err}），经官方着陆页标题比对确认"
            + (f"（相似度 {sim:.2f}）" if title else "（引用未提供标题，仅确认存在）"))
    return "", note, True


def arxiv_metadata_match(arxiv_id: str, title: str, year, timeout: float) -> tuple:
    """arXiv ID 元数据交叉验证（v1.5）：export.arxiv.org 官方 API 取登记的 Atom 元数据，
    与引用声称的标题/年份比对——复用 DOI 的 0.50/0.82 相似度阈值体系。
    查无记录/格式错误的 ID 直接判 invalid（疑似编造），调用方（verify_one）保证
    该判定先于可达性检查，假 ID 不会被误判为 unreachable。
    返回 (adjust, note, matched)：adjust ∈ {"", "partial", "invalid"}；
    matched=True 表示元数据成功取得且与声称标题一致。"""
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom",
          "ax": "http://arxiv.org/schemas/atom"}
    api_url = ("https://export.arxiv.org/api/query?id_list="
               + quote(arxiv_id, safe="") + "&max_results=1")
    if _cb_open(api_url):
        return "", _cb_skip_note(api_url) + "，未做 arXiv 元数据核验", False
    _arxiv_rate_wait()
    ua_rot = [f"cite-holmes/{VERSION}; +verified-deep-research",
              f"Mozilla/5.0 (compatible; cite-holmes/{VERSION}; +verified-deep-research)"]
    xml_text, fetch_err = None, ""
    for attempt in range(2):
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": ua_rot[min(attempt, 1)]})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                xml_text = resp.read().decode("utf-8", "ignore")
            fetch_err = ""
            _cb_record(api_url, False)
            break
        except urllib.error.HTTPError as e:
            _cb_record(api_url, False)
            fetch_err = f"HTTP {e.code}"
        except Exception as e:
            fetch_err = type(e).__name__
        if attempt == 0:
            # v1.11 指数退避：406 反爬窗口对短间隔敏感（3s 仍撞），首败后多等 5s
            # 再守 3s 礼貌时隙；sleep 在锁外，不占其他 worker 的限速时隙
            time.sleep(5)
            _arxiv_rate_wait()  # 重试同样守 3 秒礼貌上限（v1.5 评审修正）
    if xml_text is None:
        _cb_record(api_url, True)  # 整次调用只记 1 次传输失败
        # v1.11：不再静默跳过——fallback 官方着陆页恢复判定确定性
        return _arxiv_landing_fallback(arxiv_id, title, timeout, fetch_err)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        # API 返回了非 XML（典型=反爬 HTML 页）——同样走着陆页 fallback
        return _arxiv_landing_fallback(arxiv_id, title, timeout,
                                       f"返回非预期格式（{e}）")
    entries = root.findall("a:entry", ns)
    # v1.11 评审修正：反爬/错误页常是格式良好的 HTML（合法 XML、可解析成功），
    # 但它不是 Atom feed——绝不能据此判「查无记录 → invalid」误杀真论文。
    # feed 根元素校验失败 → 着陆页 fallback 恢复确定性。
    if not (root.tag == "feed" or root.tag.endswith("}feed")):
        return _arxiv_landing_fallback(arxiv_id, title, timeout,
                                       "返回非 Atom 格式")
    if not entries:
        return "invalid", "arXiv ID 在官方 API 查无记录 → 疑似编造引用", False
    entry = entries[0]
    t = entry.find("a:title", ns)
    meta_title = re.sub(r"\s+", " ", (t.text or "")).strip() if t is not None else ""
    # 错误判据以官方 ax:error 元素为准；标题恰为 "Error" 的真实论文不误杀，
    # 仅当 summary 明确含格式错误文案时才作辅助判据（v1.5 评审修正）
    err = entry.find("ax:error", ns)
    summ = entry.find("a:summary", ns)
    err_text = ""
    if err is not None and err.text:
        err_text = err.text.strip()
    elif summ is not None and summ.text and "incorrect id format" in summ.text:
        err_text = summ.text.strip()
    if err_text:
        return "invalid", f"arXiv 官方 API 拒绝该 ID（{err_text[:60]}）→ 疑似编造引用", False
    pub = entry.find("a:published", ns)
    meta_year = None
    if pub is not None and pub.text:
        m = re.match(r"(\d{4})", pub.text.strip())
        if m:
            meta_year = int(m.group(1))
    sim = difflib.SequenceMatcher(None, (title or "").lower(),
                                  meta_title.lower()).ratio()
    if not title:
        return "", f"arXiv 元数据核验完成（引用未提供标题，无法比对；登记年份 {meta_year or '未知'}）", True
    if sim < 0.50:
        return "invalid", (f"arXiv 元数据标题相似度仅 {sim:.2f} → ID 指向的不是这篇论文，"
                           f"疑似编造或错引（arXiv 实际为《{meta_title[:60]}》）"), True
    year_note = ""
    if meta_year and year:
        try:
            if abs(int(year) - int(meta_year)) >= 2:
                year_note = f"；年份不符（声称 {year} vs arXiv 登记 {meta_year}）"
        except (TypeError, ValueError):
            pass
    if sim < 0.82:
        return "partial", f"arXiv 元数据标题相似度 {sim:.2f}，建议人工复核{year_note}", True
    return "", f"arXiv 元数据核验一致（相似度 {sim:.2f}）{year_note}", True


def wayback_available(url: str, timeout: float) -> str:
    """v1.5 unreachable 存档兜底：查 Wayback Machine 是否有历史存档。
    有 → 返回「Wayback 存档可用（YYYY-MM-DD）：<存档URL>（人工复核可对照）」；
    无存档/查询失败 → 返回 ""（静默跳过，不加额外文案）。SSRF 字面量防护同样
    适用——内网/保留地址不外发到 archive.org。"""
    if ssrf_blocked(url):
        return ""
    # 实测教训：archive.org 对全量百分号编码的 url 参数不匹配（原样 200+快照，
    # %3A%2F 编码形式 200 但快照集为空）——必须原文直传，仅编码破坏外层查询的字符
    q = quote(url, safe=":/?&=#%@+!$,;'~()*[]-._")
    wb_url = ("https://archive.org/wayback/available?url=" + q)
    # 断路器看真正的外呼对象 archive.org（v1.6 二轮评审 P1 修正）——
    # 目标主机熔断不影响存档查询（死站查存档正是本函数的主用例）
    if _cb_open(wb_url):
        return ""
    req = urllib.request.Request(
        wb_url,
        headers={"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                j = json.loads(resp.read().decode("utf-8", "ignore"))
            _cb_record(wb_url, False)
            closest = (j.get("archived_snapshots") or {}).get("closest") or {}
            if closest.get("available") and closest.get("url"):
                ts = str(closest.get("timestamp") or "")
                nice = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts
                return f"Wayback 存档可用（{nice}）：{closest['url']}（人工复核可对照）"
            return ""  # 有明确响应但无存档：确定性结果，不重试
        except urllib.error.HTTPError as e:
            _cb_record(wb_url, False)
            if e.code == 429 and attempt == 0:
                time.sleep(3.0)  # archive.org 对公共 IP 常见限流：退避一次
                continue
            return ""
        except Exception:
            _cb_record(wb_url, True)
            return ""
    return ""


def check_url(url: str, timeout: float, retries: int = 1) -> tuple:
    """返回 (reachable, status, note)。reachable 以 2xx/3xx/429(反爬) 计。
    瞬态网络错误（超时/连接重置）自动重试一次——国内网络偶发抖动不误判。
    内网/环回地址直接拒绝（SSRF 防护），不发起请求。
    v1.6：主机断路器生效；传输失败按成因给可操作话术（超时给 --timeout 建议）。"""
    if ssrf_blocked(url):
        return False, None, "内网/保留地址，验证请求已拒绝（SSRF 防护）"
    if _cb_open(url):
        return False, None, _cb_skip_note(url)
    note = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": f"Mozilla/5.0 (compatible; cite-holmes/{VERSION}; +verified-deep-research)",
            "Accept": "*/*",
        })
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        transient = False
        for method in ("HEAD", "GET"):
            try:
                req.method = method
                with opener.open(req, timeout=timeout) as resp:
                    _cb_record(url, False)
                    return True, resp.status, f"{method} {resp.status}"
            except urllib.error.HTTPError as e:
                _cb_record(url, False)  # 站点有响应：不算传输失败
                if method == "HEAD" and e.code in (403, 405, 501):
                    continue  # 站点拒绝 HEAD，降级 GET 重试
                if e.code == 429:
                    return True, 429, "HTTP 429（反爬限流，站点实际存在）"
                return False, e.code, f"HTTP {e.code}（站点拒绝或页面不存在）"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if method == "HEAD":
                    continue
                transient = True
                msg = str(e)
                if isinstance(e, TimeoutError) or "timed out" in msg or "timeout" in msg.lower():
                    note = "连接超时（站点慢或网络受限），建议 --timeout 20 重试"
                elif ("getaddrinfo" in msg or "name or service" in msg.lower()
                        or "no address" in msg.lower()):
                    note = "域名无法解析，连接失败（站点可能已下线或被网络拦截）"
                elif "refused" in msg or "reset" in msg.lower():
                    note = "连接被拒/重置（站点或网络问题）"
                else:
                    note = f"网络异常：{e}"[:120]
            except ValueError as e:
                return False, None, f"URL 格式无效：{e}"[:120]
        if transient and attempt < retries:
            time.sleep(1.5)  # 瞬态抖动稍候重试
    # 重试耗尽仍失败：每次 check_url 调用只记 1 次传输失败（重试是同一逻辑失败，
    # 逐次记录会导致一次调用即熔断）
    _cb_record(url, True)
    return False, None, note or "连接失败（站点不可达、域名不存在或网络受限）"


FIELD_ZH = {"title": "标题(title)", "url": "链接(url)", "source": "来源(source)", "year": "年份(year)"}


def crossref_retraction_check(doi: str, timeout: float) -> tuple:
    """v1.8 撤稿检测：Crossref REST API（Retraction Watch 数据，免费/每日更新）。
    判定：works 记录的 updated-by 列表中存在 type=="retraction" → 已撤稿。
    查询失败一律静默跳过（绝不因检查失败惩罚引用）。返回 (retracted, note)。"""
    mailto = _OPTS.get("mailto") or ""
    url = f"https://api.crossref.org/works/{quote(doi, safe='()/')}"
    if mailto:
        url += f"?mailto={quote(mailto, safe='@')}"
    if _cb_open(url):
        return False, ""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research "
                                        "(https://skillhub.cn/skills/cite-holmes)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            m = (json.loads(resp.read().decode("utf-8", "ignore")) or {}).get("message") or {}
        _cb_record(url, False)
        for item in m.get("updated-by") or []:
            if isinstance(item, dict) and item.get("type") == "retraction":
                notice = item.get("DOI") or ""
                when = ((item.get("updated") or {}).get("date-time") or "")[:10]
                extra = f"，撤稿通知 {notice}" if notice else ""
                when_note = f"（{when}）" if when else ""
                return True, (f"论文已撤稿（Crossref/Retraction Watch{when_note}{extra}）"
                              "→ 不得作为有效证据引用")
        return False, ""
    except urllib.error.HTTPError:
        _cb_record(url, True, degrade=False)  # 站点有响应（含 429 限流）：不计入全局降级
        return False, ""
    except Exception:
        _cb_record(url, True)
        return False, ""


def openalex_title_check(title: str, timeout: float) -> str:
    """v1.8 OpenAlex 书目级存在性核查（无 DOI/PMID/arXiv 引用的补充信号源）。
    只提供正面确认与近似提示，绝不下 invalid 判定——OpenAlex 收录有滞后，
    「查无」不等于「编造」（GESIS 失效模式 #3：库覆盖有限）。异常静默跳过。
    v1.9：支持 API key（2026-02 起 OpenAlex 生产调用需 key，--openalex-key /
    环境变量注入）；403 给可操作提示而非静默跳过。"""
    if len((title or "").strip()) < 18:
        return ""
    q = quote(title.strip(), safe="")
    url = (f"https://api.openalex.org/works?search={q}&per-page=1"
           "&select=display_name,publication_year")
    key = _OPTS.get("openalex_key") or ""
    if key:
        url += f"&api_key={quote(key, safe='')}"
    try:
        if _cb_open(url):
            return ""
        req = urllib.request.Request(
            url, headers={"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _cb_record(url, False)
            results = (json.loads(resp.read().decode("utf-8", "ignore"))
                       or {}).get("results") or []
        if not results:
            return "OpenAlex 未检索到明显匹配条目（可能未被收录，不作为编造依据）"
        w = results[0]
        mt = re.sub(r"\s+", " ", str(w.get("display_name") or "")).strip()
        my = w.get("publication_year")
        year_note = f"（{my}）" if my else ""
        t = title.strip().lower()
        mt_l = mt.lower()
        sim = difflib.SequenceMatcher(None, t, mt_l).ratio()
        pfx = difflib.SequenceMatcher(None, t, mt_l[:len(t)]).ratio() if len(mt_l) >= len(t) else 0.0
        best = max(sim, pfx)
        if best >= 0.82:
            return f"OpenAlex 书目确认存在：{mt[:60]}{year_note}"
        if best >= 0.60:
            return (f"OpenAlex 近似条目（标题相似度 {best:.2f}）：{mt[:60]}{year_note}，"
                    "建议人工复核")
        return (f"OpenAlex 未检索到明显匹配（最高相似度 {best:.2f}）；"
                "可能未被收录或较新，不作为编造依据")
    except urllib.error.HTTPError as e:
        _cb_record(url, True, degrade=False)  # 站点有响应：不计入全局网络降级
        if e.code == 403:
            return ("OpenAlex 拒绝访问（403）——2026 年起生产调用需 API key（无 key 每日仅 "
                    "100 credits 测试额度），可用 --openalex-key 或环境变量 OPENALEX_API_KEY 配置后重试")
        if e.code == 429:
            return ("OpenAlex 限流（429，常见于无 key 每日额度用尽）——可用 --openalex-key "
                    "或环境变量 OPENALEX_API_KEY 配置免费 key 后重试")
        return ""
    except Exception:
        _cb_record(url, True)
        return ""


_S2_LAST = [0.0]
_S2_LOCK = threading.Lock()


def _s2_rate_wait():
    """免钥走 S2 共享限速池（约 100 请求/5 分钟），客户端串行化 ≥1.5 秒/请求。
    v1.10：加锁——并行 worker 下保持全局串行（否则并发线程同时读到旧时刻，
    一起通过等待，实际请求间隔被压缩）。"""
    with _S2_LOCK:
        wait = 1.5 - (time.time() - _S2_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _S2_LAST[0] = time.time()


def s2_doi_confirm(doi: str, title: str, timeout: float) -> tuple:
    """v1.9 Semantic Scholar 第三源交叉确认——定位是「第二路正面信号」：
    仅在 DOI.org 元数据未能取得时（网络受限/瞬时 5xx）由 S2 再给一次存在性确认，
    着陆页反爬救回时与 DOI/arXiv 元数据同门槛（仍走层级/字段门控）。
    实测 S2 记录质量参差（存在把正式论文登记成期刊目录页的情况）——因此
    ①只确认不降级：标题不一致一律静默，绝不下调判定；
    ②查无/限流/失败一律静默跳过（S2 收录不全，查无 ≠ 编造）。
    返回 (matched, note)。key 只走 x-api-key 头（query 参数会进代理日志）。"""
    if not (title or "").strip():
        return False, ""  # 无标题无从比对，不浪费限速调用
    url = ("https://api.semanticscholar.org/graph/v1/paper/DOI:"
           + quote(doi, safe="") + "?fields=title,year")
    key = _OPTS.get("s2_key") or ""
    if _cb_open(url):
        return False, ""
    _s2_rate_wait()
    try:
        headers = {"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"}
        if key:
            headers["x-api-key"] = key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _cb_record(url, False)
            j = json.loads(resp.read().decode("utf-8", "ignore")) or {}
    except urllib.error.HTTPError:
        _cb_record(url, False)  # 站点有响应（404/429 等）：不算传输失败
        return False, ""
    except Exception:
        _cb_record(url, True)
        return False, ""
    mt = re.sub(r"\s+", " ", str(j.get("title") or "")).strip()
    my = j.get("year")
    if not mt or not (title or "").strip():
        return False, ""
    t = title.strip().lower()
    mt_l = mt.lower()
    sim = difflib.SequenceMatcher(None, t, mt_l).ratio()
    pfx = difflib.SequenceMatcher(None, t, mt_l[:len(t)]).ratio() if len(mt_l) >= len(t) else 0.0
    if max(sim, pfx) < 0.82:
        return False, ""  # 不一致静默：绝不以 S2 的不一致作负面判据
    year_note = f"（{my}）" if my else ""
    return True, f"Semantic Scholar 交叉确认存在：{mt[:60]}{year_note}（DOI.org 之外的第二路确认）"


def s2_title_confirm(title: str, timeout: float) -> tuple:
    """v1.10 Semantic Scholar 标题检索确认——无 DOI/PMID/arXiv 引用（.bib 导入常见）
    的第三路正面信号（与 OpenAlex 书目核查并列，互为备份：两库收录面不同）。
    与 s2_doi_confirm 同纪律：只确认不降级——查无/限流/失败一律静默跳过，
    绝不以下调判定（S2 收录不全 + 记录质量参差）。
    实现细节（S2 官方文档确认）：/paper/search 的 query 为纯文本，连字符词
    （如 state-of-the-art）查询无结果——先把连字符归一为空格再编码。
    返回 (matched, note)。key 只走 x-api-key 头。"""
    t = (title or "").strip()
    if len(t) < 18:
        return False, ""  # 过短标题检索噪声大，不浪费限速调用
    q = quote(re.sub(r"[-\u2010-\u2015]+", " ", t), safe="")
    url = (f"https://api.semanticscholar.org/graph/v1/paper/search"
           f"?query={q}&fields=title,year&limit=1")
    key = _OPTS.get("s2_key") or ""
    if _cb_open(url):
        return False, ""
    _s2_rate_wait()
    try:
        headers = {"User-Agent": f"cite-holmes/{VERSION}; +verified-deep-research"}
        if key:
            headers["x-api-key"] = key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _cb_record(url, False)
            j = json.loads(resp.read().decode("utf-8", "ignore")) or {}
    except urllib.error.HTTPError:
        _cb_record(url, False)  # 站点有响应（404/429 等）：不算传输失败
        return False, ""
    except Exception:
        _cb_record(url, True)
        return False, ""
    data = j.get("data")
    if not isinstance(data, list) or not data:
        return False, ""  # 查无 ≠ 编造（收录滞后），静默
    w = data[0] or {}
    mt = re.sub(r"\s+", " ", str(w.get("title") or "")).strip()
    my = w.get("year")
    if not mt:
        return False, ""
    t_l = t.lower()
    mt_l = mt.lower()
    sim = difflib.SequenceMatcher(None, t_l, mt_l).ratio()
    pfx = difflib.SequenceMatcher(None, t_l, mt_l[:len(t_l)]).ratio() if len(mt_l) >= len(t_l) else 0.0
    if max(sim, pfx) < 0.82:
        return False, ""  # 不一致静默：绝不以 S2 的不一致作负面判据
    year_note = f"（{my}）" if my else ""
    return True, f"Semantic Scholar 标题检索确认存在：{mt[:60]}{year_note}"


def missing_fields(ref: dict) -> list:
    miss = [f for f in REQUIRED_FIELDS if not ref.get(f)]
    if "url" in miss and (
            (ref.get("doi") and DOI_RE.match(str(ref["doi"]).strip())) or
            (ref.get("pmid") and PMID_RE.match(str(ref["pmid"]).strip())) or
            extract_arxiv_id(ref)):
        miss.remove("url")
    return [FIELD_ZH.get(f, f) for f in miss]


def ref_to_url(ref: dict) -> str:
    """url → doi → arxiv → pmid 四级解析，返回最终可检查的 URL。字段统一强转为字符串。"""
    url = str(ref.get("url") or "").strip()
    if url:
        return url
    doi = str(ref.get("doi") or "").strip()
    if doi and DOI_RE.match(doi):
        return f"https://doi.org/{doi}"
    arxiv = extract_arxiv_id(ref)
    if arxiv:
        return f"https://arxiv.org/abs/{arxiv}"
    pmid = str(ref.get("pmid") or "").strip()
    if pmid and PMID_RE.match(pmid):
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return ""


# ---------------- BibTeX 导入（v1.9，对标 Zotero/EndNote 工作流） ----------------

def _bib_unbrace(value: str) -> str:
    """BibTeX 字段值清理：还原常见 TeX 转义（\\& → & 等）、去花括号与转义残留、
    压缩空白。刻意不做重音展开（Schr\\"oder 类）——标题比对走模糊相似度，无需精确。"""
    v = re.sub(r"\\([{}&%$#_])", r"\1", str(value or ""))
    v = v.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", v).strip()


def _bib_entry_to_ref(etype: str, f: dict) -> dict:
    """BibTeX 字段 → 引用 schema。source 依次取 journal/booktitle/journaltitle/
    publisher；howpublished 含 \\url 宏时只取链接不进 source（避免垃圾来源名）。"""
    def g(k):
        return _bib_unbrace(f.get(k, ""))

    url = g("url")
    if not url:
        for k in ("url", "howpublished", "note"):
            m = re.search(r"\\url\{([^}]+)\}", str(f.get(k) or ""))
            if m:
                url = m.group(1).strip()
                break
    src = (g("journal") or g("booktitle") or g("journaltitle") or g("publisher"))
    if not src:
        hp = str(f.get("howpublished") or "")
        if hp and "\\url" not in hp:
            src = _bib_unbrace(hp)
    ref = {"title": g("title"),
           # BibTeX 多作者分隔符 " and " 归一为逗号——姓氏提取按逗号分段
           "authors": g("author").replace(" and ", ", "), "source": src,
           "year": re.sub(r"[^0-9]", "", g("year"))[:4] or None,
           "doi": g("doi"), "url": url,
           "pmid": re.sub(r"[^0-9]", "", g("pmid"))}
    eprint = g("eprint")
    if eprint and g("archiveprefix").lower() in ("arxiv", ""):
        ref["arxiv"] = eprint
    return {k: v for k, v in ref.items() if v not in ("", None)} or {"title": ""}


def parse_bibtex(text: str) -> list:
    """v1.9 最小 BibTeX 解析器（纯 stdlib）：支持 @article/@inproceedings/@book/
    @misc 等常规条目、嵌套花括号值、引号值与多行字段。@comment/@preamble/@string
    跳过。解析不抛异常——坏条目降级为缺字段引用，由后续检查如实标注；
    完全无法解析时返回空列表（调用方给可操作报错）。"""
    refs = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "@":
            i += 1
            continue
        m = re.match(r"@([A-Za-z]+)\s*([{(])\s*([^,\s]*)\s*,", text[i:])
        if not m:
            i += 1
            continue
        etype = m.group(1).lower()
        close_ch = "}" if m.group(2) == "{" else ")"
        i += m.end()
        if etype in ("comment", "preamble", "string"):
            continue
        fields = {}
        depth = 1
        while i < n and depth > 0:
            ch = text[i]
            if ch == close_ch:
                depth -= 1
                i += 1
                if depth == 0:
                    break
                continue
            fm = re.match(r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", text[i:])
            if not fm:
                i += 1 if ch not in ", \t\r\n" else re.match(r"[, \t\r\n]+", text[i:]).end()
                continue
            i += fm.end()
            if i < n and text[i] == "{":  # 花括号值：计数嵌套
                k, d = i + 1, 1
                while k < n and d > 0:
                    if text[k] == "{":
                        d += 1
                    elif text[k] == "}":
                        d -= 1
                    k += 1
                raw = text[i + 1:k - 1]
                i = k
            elif i < n and text[i] == '"':  # 引号值（内部可含花括号）
                k = text.find('"', i + 1)
                k = n if k < 0 else k
                raw = text[i + 1:k]
                i = k + 1
            else:  # 裸值（数字/缩写）
                k = i
                while k < n and text[k] not in ",}\n)":
                    k += 1
                raw = text[i:k].strip()
                i = k
            fields[fm.group(1).lower()] = raw
            while i < n and text[i] in ", \t\r\n":
                i += 1
        if fields:
            refs.append(_bib_entry_to_ref(etype, fields))
    return refs


def load_refs_file(path: str) -> list:
    """--refs 加载：JSON 数组或 BibTeX（v1.9）。.bib 扩展名直接走 BibTeX 解析；
    JSON 解析失败且内容以 @ 开头时自动降级 BibTeX（用户存错扩展名也能跑）。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if path.lower().endswith(".bib"):
        refs = parse_bibtex(text)
        if not refs:
            raise ValueError("BibTeX 文件中没有解析到任何条目（应有 @article{...} 等）")
        return refs
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if text.lstrip().startswith("@"):
            refs = parse_bibtex(text)
            if not refs:
                raise ValueError("内容以 @ 开头但 BibTeX 解析到 0 条，请检查文件格式")
            return refs
        raise


def verify_one(ref: dict, idx: int, offline: bool, timeout: float, medical: bool = False) -> dict:
    def _s(v):
        return str(v) if v is not None else ""

    title_in = _s(ref.get("title"))
    out = {"index": idx, "title": title_in or "(无标题)",
           "url": _s(ref.get("url")).strip(),
           "doi": _s(ref.get("doi")).strip(), "pmid": _s(ref.get("pmid")).strip(),
           "arxiv": extract_arxiv_id(ref),
           "source": _s(ref.get("source")).strip(), "year": ref.get("year"),
           "tier": ref.get("tier") or "", "semantic": ref.get("semantic", ""),
           "verdict": "unverified", "http_status": None, "note": "", "needs_human_check": False,
           "checks": {},  # v1.9 透明工作底稿：逐项检查的结构化明细（随 JSON 报告/auditjson 导出）
           "semantic_audit": build_semantic_audit(ref)}  # v1.11 语义层底稿（dict 输入才非空）

    pmid = out["pmid"]
    doi_adj, doi_matched = "", False
    arxiv_adj, arxiv_matched = "", False
    retracted = False
    url = ref_to_url(ref)
    if not url:
        raw_arxiv = str(ref.get("arxiv") or "").strip()
        if raw_arxiv and not out["arxiv"]:
            out.update(verdict="invalid",
                       note="arxiv 字段格式无法识别（应为 YYMM.NNNNN 或 category/NNNNNNN）")
        else:
            out.update(verdict="invalid",
                       note="缺少 url 且无可解析的 doi/pmid/arxiv" +
                            ("（pmid 须为 6-9 位数字）" if pmid else ""))
        return out
    if not re.match(r"^https?://", url, re.IGNORECASE):
        out.update(verdict="invalid", note=f"url 非 http(s) 格式: {url[:60]}")
        return out

    if not out["tier"]:
        out["tier"] = classify_tier(url, medical)
    out["url"] = url
    if medical and out["tier"] in ("community", "social", "blog"):
        out["note"] = "医学模式：社区/社交/博客层来源不得支撑医学结论（仅作线索）"
    elif medical and out["tier"] == "preprint":
        out["note"] = "医学模式：预印本未经同行评审，证据强度受限"

    if offline:
        out["note"] = (out["note"] + "；" if out["note"] else "") + "offline 模式未做可达性检查"
    else:
        # 带 DOI 的引用优先走元数据核验：能同时判定「存在性」与「内容匹配」，
        # 且假 DOI 的 404 在这里直接判 invalid（不会先被可达性检查误判为 unreachable）
        retracted = False
        s2_matched = False
        if out["doi"] and DOI_RE.match(out["doi"]):
            doi_adj, note, doi_matched = doi_metadata_match(
                out["doi"], str(ref.get("title") or ""), ref.get("year"), timeout,
                str(ref.get("source") or ""),
                str(ref.get("authors") or ""))
            out["checks"]["doi_metadata"] = {"matched": doi_matched, "adjust": doi_adj}
            if note:
                out["note"] = (out["note"] + "；" if out["note"] else "") + note
            if doi_adj == "invalid":
                out.update(verdict="invalid", needs_human_check=True)
                return out
            # v1.9 Semantic Scholar 第三源：DOI.org 元数据没拿到时（网络受限/瞬时故障）
            # 的第二路正面确认——只确认不降级（S2 记录质量参差，不一致静默）
            if not doi_matched:
                s2_matched, s2note = s2_doi_confirm(
                    out["doi"], str(ref.get("title") or ""), timeout)
                out["checks"]["s2"] = {"matched": s2_matched}
                if s2note:
                    out["note"] = (out["note"] + "；" if out["note"] else "") + s2note
            # v1.8 撤稿检测：真实存在的论文也可能是撤稿状态，不得作为有效证据
            retracted, retnote = crossref_retraction_check(out["doi"], timeout)
            out["checks"]["retraction"] = {"retracted": retracted}
            if retnote:
                out["note"] = (out["note"] + "；" if out["note"] else "") + retnote
                out["needs_human_check"] = True
        # 带 arXiv ID 的引用同层核验（无 DOI 时）：官方 API 查无记录 → 直接 invalid，
        # 同样先于可达性检查，避免假 ID 被误判为 unreachable（v1.5）
        elif out["arxiv"]:
            arxiv_adj, note, arxiv_matched = arxiv_metadata_match(
                out["arxiv"], str(ref.get("title") or ""), ref.get("year"), timeout)
            out["checks"]["arxiv_metadata"] = {"matched": arxiv_matched, "adjust": arxiv_adj}
            if note:
                out["note"] = (out["note"] + "；" if out["note"] else "") + note
            if arxiv_adj == "invalid":
                out.update(verdict="invalid", needs_human_check=True)
                return out
        # v1.6：双键引用（doi+pmid）做交叉一致性——两键各自真实也可能拼接造假，
        # 元数据层判定，先于可达性检查
        if (out["doi"] and DOI_RE.match(out["doi"])
                and out["pmid"] and PMID_RE.match(out["pmid"])):
            xadj, xnote = pmid_doi_crosscheck(out["pmid"], out["doi"], timeout)
            out["checks"]["doi_pmid_crosscheck"] = {"done": True}
            if xnote:
                out["note"] = (out["note"] + "；" if out["note"] else "") + xnote
            if xadj == "invalid":
                out.update(verdict="invalid", needs_human_check=True)
                return out
        reachable, status, note = check_url(url, timeout)
        out["http_status"] = status
        out["checks"]["url"] = {"reachable": reachable, "status": status}
        out["note"] = (out["note"] + "；" if out["note"] else "") + note
        if not reachable:
            # DOI/arXiv 注册元数据或 S2 交叉已确认存在 + 着陆页反爬（403/429）→
            # 引用存在性已被官方注册库证实，不能因反爬误判为 unreachable。评审修正：
            # 救回不再无条件盖 verified——层级/字段门控照走，防"真 ID + 403 博客链接"骗过权威层
            if (doi_matched or arxiv_matched or s2_matched) and status in (403, 429):
                label = ("DOI" if doi_matched else "arXiv" if arxiv_matched
                         else "Semantic Scholar")
                out["note"] = (out["note"] + "；" if out["note"] else "") + \
                    f"着陆页反爬（HTTP {status}），但 {label} 注册元数据核验一致——存在性已确认"
                # v1.5 二轮评审 P1：元数据本身判 partial（相似度 0.50-0.82）时，
                # 救回同样不得给 verified——与 200 路径末尾的降级不变量保持一致，
                # 防"疑似错引"借反爬救回混进 verified（进而流入 bibtex/strict CI）
                if (out["tier"] in TRUSTED_TIERS and not missing_fields(ref)
                        and doi_adj != "partial" and arxiv_adj != "partial"):
                    out["verdict"] = "verified"
                else:
                    out["verdict"] = "partial"
                if retracted and out["verdict"] == "verified":
                    out["verdict"] = "partial"
                    out["needs_human_check"] = True
                return out
            # v1.5：arXiv ID 以 arxiv.org/abs 为官方解析器——官方站可达却对该 ID
            # 返回 404 → 官方库查无此 ID，判 invalid（官方 API 被墙时兜底）。
            # 评审修正（P0）：仅当元数据核验未能确认存在时才允许此判定——
            # 官方 API 刚确认过存在时，脏 URL 的 404 不得反转成 invalid；
            # 此逻辑仅适用于解析器域名，普通网页 404 仍是 unreachable
            elif status == 404 and not (doi_matched or arxiv_matched) and re.match(
                    r"^https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf)/", url, re.IGNORECASE):
                out.update(verdict="invalid", needs_human_check=True,
                           note=(out["note"] + "；" if out["note"] else "") +
                                "arXiv 官方站对该 ID 返回 404（官方库查无）→ 疑似编造引用")
                return out
            out.update(verdict="unreachable", needs_human_check=True,
                       note=(out["note"] + "；" if out["note"] else "") + "可能反爬/临时故障，不等于不存在")
            # v1.5 存档兜底：不可达 ≠ 不存在，附 Wayback 存档链给人工复核做对照
            wb = wayback_available(url, timeout)
            out["checks"]["wayback"] = {"archive_found": bool(wb)}
            if wb:
                out["note"] = (out["note"] + "；" if out["note"] else "") + wb
            return out
        m = PUBMED_URL_RE.match(url)
        if m:
            pmid_ok, pmid_note = pubmed_pmid_exists(m.group(1), timeout)
            if not pmid_ok:
                out.update(verdict="invalid", needs_human_check=True,
                           note=(out["note"] + "；" if out["note"] else "") + pmid_note)
                return out
            out["note"] = (out["note"] + "；" if out["note"] else "") + pmid_note
        # v1.8 OpenAlex 书目级核查：无 DOI/PMID/arXiv 的引用多一路正面确认信号；
        # v1.10 S2 标题检索为并列第二路（两库收录面不同，互为备份；同样只确认不降级）
        if not out["doi"] and not out["pmid"] and not out["arxiv"]:
            oa_note = openalex_title_check(str(ref.get("title") or ""), timeout)
            out["checks"]["openalex"] = {"ran": True, "confirmed": "确认存在" in oa_note}
            if oa_note:
                out["note"] = (out["note"] + "；" if out["note"] else "") + oa_note
            s2t_matched, s2t_note = s2_title_confirm(str(ref.get("title") or ""), timeout)
            out["checks"]["s2_title"] = {"matched": s2t_matched}
            if s2t_note:
                out["note"] = (out["note"] + "；" if out["note"] else "") + s2t_note

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

    # v1.4：元数据核验判为 partial 时，verified 降级为 partial
    if (doi_adj == "partial" or arxiv_adj == "partial") and out["verdict"] == "verified":
        out["verdict"] = "partial"
    if retracted and out["verdict"] == "verified":
        out["verdict"] = "partial"
        out["needs_human_check"] = True
    # offline 模式只做结构核验（格式/字段/层级/去重），可达性未验证——
    # 诚实起见 verified 封顶为 partial（避免离线盖章"已验证"）
    if offline and out["verdict"] == "verified":
        out["verdict"] = "partial"
        out["note"] = (out["note"] + "；" if out["note"] else "") + \
            "offline 模式最高判 partial（可达性未验证）"
    return out


# ---------------- 语义层工作底稿（v1.11，semantic_audit） ----------------
# 模型在研究流程中对每条引用做语义判定（该来源是否真的支撑所引论断），v1.11 起
# 支持把判定以结构化对象写进 research_refs.json 的 semantic 字段，机械层负责校验
# 结构、透传进 auditjson/报告，并对否定性判定封顶——落实 GESIS 立场论文
# （arXiv:2607.22693）「disclosing their own uncertainty」的行业呼吁：
# 检测系统的语义不确定性必须可披露、可审计，而不是藏在模型"感觉"里。
# support 取值：supported（支撑）/ partial（部分支撑）/ not_in_source（来源未
# 包含该论断）/ contradicted（来源与论断相矛盾）/ unclear（无法判定）。
SEMANTIC_SUPPORTS = ("supported", "partial", "not_in_source", "contradicted",
                     "unclear")
_SEMANTIC_CAP = ("not_in_source", "contradicted")


def build_semantic_audit(ref: dict):
    """解析 semantic 字段：dict（新）→ 结构化底稿对象；字符串/缺失（旧）→ None。
    非法 support 值按 unclear 处理并留注记——宁可降级也不让脏数据静默通过。"""
    s = ref.get("semantic")
    if not isinstance(s, dict):
        return None
    support = str(s.get("support") or "").strip().lower()
    note = ""
    if support not in SEMANTIC_SUPPORTS:
        if support:
            note = f"semantic.support 非法值「{support[:30]}」，按 unclear 处理"
        support = "unclear"
    own_note = str(s.get("note") or "").strip()
    if note and own_note:
        note = note + "；" + own_note
    else:
        note = note or own_note
    return {"claim": str(s.get("claim") or "").strip(),
            "support": support,
            "quote": str(s.get("quote") or "").strip(),
            "note": note}


def apply_semantic_cap(results: list) -> None:
    """v1.11 语义封顶：语义判定 not_in_source / contradicted 时，机械层 verified
    不得覆盖——封顶 partial 并转人工复核（能力边界矩阵明示语义层不归机械层承诺，
    但模型已做出的否定性判定机械层必须尊重）。在 mark_duplicates 之后统一执行：
    所有判定已收齐，verify_one 的任何 early-return 路径都被覆盖，且串行/并行/
    缓存复用三条路径行为一致。invalid 条目不动（不得反向"提升"为 partial）。"""
    for r in results:
        sa = r.get("semantic_audit") or {}
        if sa.get("support") not in _SEMANTIC_CAP:
            continue
        if r.get("verdict") == "invalid":
            continue
        if r.get("verdict") == "verified":
            r["verdict"] = "partial"
        r["needs_human_check"] = True
        why = ("来源未包含所引论断" if sa.get("support") == "not_in_source"
               else "来源内容与该论断相矛盾")
        r["note"] = ((r.get("note") + "；") if r.get("note") else "") + \
            f"语义层判定 {sa.get('support')}（{why}）→ 封顶 partial，需人工复核"


def _cache_key(ref: dict) -> tuple:
    """v1.10 批内缓存键：doi → url → pmid → arxiv 取首个可用标识；全无则 ()（不缓存）。
    仅作缓存命中优化，不参与判定；判定顺序与 mark_duplicates 去重一致（url/doi/pmid）。"""
    doi = str(ref.get("doi") or "").strip()
    if doi:
        return ("doi", doi.lower())
    u = str(ref.get("url") or "").strip()
    if u:
        return ("url", normalize_url(u))
    pmid = str(ref.get("pmid") or "").strip()
    if pmid:
        return ("pmid", pmid)
    ax = extract_arxiv_id(ref)
    if ax:
        return ("arxiv", ax)
    return ()


# ---------------- 持久磁盘缓存（v1.12：复跑不出国——直攻评测 T 维） ----------------
# ~/.cache/cite-holmes/cache.sqlite3（标准库 sqlite3）。键=影响判定的全部输入字段
# （同 DOI 不同声称标题/年份必须分开——标题相似度判定依赖声称值）+ 验证器版本 + 预设。
# 只缓存稳定判定 verified/partial/invalid；unreachable（瞬态）与 offline 结果不缓存。
# --strict 强制绕过读（CI 诚实）；--refresh-cache 绕过读但仍写；写失败静默（缓存绝不影响验证）。
_DC_CACHEABLE = {"verified", "partial", "invalid"}


def _dc_key(ref: dict, profile: str) -> str:
    basis = {k: ref.get(k) for k in ("doi", "url", "pmid", "arxiv", "title",
                                     "year", "source", "authors", "tier")}
    basis["_v"] = VERSION
    basis["_p"] = profile
    raw = json.dumps(basis, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _dc_path(args) -> str:
    return os.path.abspath(os.path.expanduser(args.cache_path))


def _dc_get(path: str, key: str, ttl_h: float):
    """命中且未过期 → (result_dict, age_hours)；未命中/坏库/坏行 → None（静默）。"""
    if not key:
        return None
    try:
        import sqlite3
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS dc("
                         "k TEXT PRIMARY KEY, ts REAL, payload TEXT)")
            row = conn.execute("SELECT ts, payload FROM dc WHERE k=?", (key,)).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    if not row:
        return None
    ts, payload = row
    age_h = (time.time() - ts) / 3600.0
    if age_h > max(0.0, ttl_h):
        return None
    try:
        r = json.loads(payload)
    except Exception:
        return None
    if not isinstance(r, dict) or not r.get("verdict"):
        return None
    return r, age_h


def _dc_put(path: str, key: str, result: dict) -> None:
    if not key:
        return
    try:
        import sqlite3
        os.makedirs(os.path.dirname(path), exist_ok=True)
        slim = {k: v for k, v in result.items() if k != "index"}
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS dc("
                         "k TEXT PRIMARY KEY, ts REAL, payload TEXT)")
            conn.execute("INSERT OR REPLACE INTO dc(k, ts, payload) VALUES (?,?,?)",
                         (key, time.time(), json.dumps(slim, ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # 缓存写失败绝不影响验证本身


def mark_duplicates(results: list) -> None:
    seen = {}
    kind_zh = {"url": "URL", "doi": "DOI", "pmid": "PMID"}
    for r in results:
        keys = []
        if r.get("url"):
            keys.append(("url", normalize_url(r["url"])))
        if r.get("doi"):
            keys.append(("doi", r["doi"].lower()))
        if r.get("pmid"):
            keys.append(("pmid", r["pmid"]))
        hit = next(((k, seen[v]) for k, v in keys if v in seen), None)
        if hit:
            kind, first = hit
            r["note"] = (r["note"] + "；" if r["note"] else "") + f"与 #{first} 重复（同{kind_zh[kind]}）"
            if r["verdict"] == "verified":
                r["verdict"] = "partial"
        else:
            for _, v in keys:
                seen[v] = r["index"]


VERDICT_ZH = {"verified": "✅ verified", "partial": "🟡 partial", "unreachable": "⚠️ unreachable",
              "invalid": "❌ invalid", "unverified": "⏸ unverified"}


def export_bibtex(results: list, path: str) -> int:
    """仅导出 verified 条目为 BibTeX（可直接导入论文参考文献管理器）。返回条数。
    字段值经 bib_safe 加固（剥除花括号/换行，防 @entry 逃逸），citation key 保证唯一。"""
    n = 0
    used_keys = set()
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            if r["verdict"] != "verified":
                continue
            n += 1
            title = bib_safe(r.get("title") or "untitled").strip() or "untitled"
            # 评审修正：year 未经消毒可携带换行/花括号逃逸 @entry，只留数字
            ys = re.sub(r"[^0-9]", "", str(r.get("year") or ""))[:4] if r.get("year") else ""
            year = ys or "n.d."
            words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", title)[:3]
            key = ("holmes" + ys + "".join(words))[:42] or f"ref{r['index']}"
            k2 = key
            sfx = 2
            while k2 in used_keys:
                k2 = f"{key}_{sfx}"
                sfx += 1
            used_keys.add(k2)
            fields = [f"  title = {{{bib_safe(title)}}}"]
            if r.get("source"):
                fields.append(f"  journal = {{{bib_safe(r.get('source'))}}}")
            if r.get("year"):
                fields.append(f"  year = {{{year}}}")
            if r.get("url"):
                fields.append(f"  url = {{{bib_safe(r.get('url'))}}}")
            if r.get("doi"):
                fields.append(f"  doi = {{{bib_safe(r.get('doi'))}}}")
            if r.get("arxiv"):
                fields.append(f"  eprint = {{{bib_safe(r.get('arxiv'))}}}")
                fields.append("  archivePrefix = {arXiv}")
            notes = ["cite-holmes verified"]
            if r.get("pmid"):
                notes.append(f"PMID: {r['pmid']}")
            fields.append("  note = {{{}}}".format(bib_safe("; ".join(notes))))
            f.write("@misc{" + k2 + ",\n" + ",\n".join(fields) + "}\n\n")
    return n


def export_csv(results: list, path: str) -> None:
    """全量审计台账 CSV（utf-8-sig，Excel 直接打开不乱码）。单元格做公式注入中和。"""
    cols = ["index", "title", "verdict", "tier", "http_status", "needs_human_check",
            "year", "source", "url", "doi", "pmid", "arxiv", "note"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in results:
            row = [csv_safe(str(r.get(c) if r.get(c) is not None else "")) for c in cols]
            w.writerow(row)


def export_audit(results: list, path: str, offline: bool, profile: str) -> None:
    """v1.9 透明工作底稿（auditjson）：每条引用的逐项检查明细，机器可读。
    供人工复核、机构审计与流程合规——回应"检测系统需要透明多源"的行业呼吁
    （arXiv 2607.22693：五家检测工具均不可无人监督运行，透明度是刚需）。"""
    doc = {
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "offline": offline, "profile": profile,
        "checks_catalog": {
            "doi_metadata": "DOI.org CSL 元数据（标题/年份/期刊/作者交叉核验）",
            "retraction": "Crossref/Retraction Watch 撤稿库",
            "s2": "Semantic Scholar 第三源交叉确认（只确认不降级）",
            "s2_title": "Semantic Scholar 标题检索确认（无 DOI/PMID/arXiv 引用的正面信号，只确认不降级）",
            "arxiv_metadata": "arXiv 官方 API（标题/年份）",
            "arxiv_landing_fallback": "arXiv API 失败时官方着陆页标题比对（v1.11 确定性保卫）",
            "url": "可达性检查（HEAD→GET 降级）",
            "openalex": "OpenAlex 书目级存在性（只确认不降级）",
            "wayback": "Wayback Machine 存档对照（unreachable 时）",
            "doi_pmid_crosscheck": "DOI↔PMID 拼接伪造检测",
            "semantic_audit": "语义层工作底稿（v1.11，模型判定结构化透出；not_in_source/contradicted 封顶 partial）"},
        "results": [{"index": r.get("index"), "title": r.get("title"),
                     "verdict": r.get("verdict"), "tier": r.get("tier"),
                     "http_status": r.get("http_status"),
                     "needs_human_check": bool(r.get("needs_human_check")),
                     "checks": r.get("checks") or {},
                     "semantic_audit": r.get("semantic_audit"),
                     "note": r.get("note", "")}
                    for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def precheck_conclusion(sc: dict) -> str:
    """v1.9 投稿前结论（一行）：arXiv 自 2026-05 起对含幻觉/未核引用的投稿实施
    处罚（最长禁投一年；v1.11 据 Nature 2026-05-19 报道修正起始月份），ICML 2026
    等会议亦将幻觉引用列为桌拒理由——报告头部直接给出可否提交的结论。"""
    c = sc["counts"]
    parts = [f"{c[k]} 条 {k}" for k in ("invalid", "unreachable", "unverified") if c[k]]
    if parts:
        return ("⚠️ 投稿前结论：不建议直接提交——存在 " + " / ".join(parts)
                + "，先完成人工复核（arXiv 自 2026-05 起、ICML 2026 等会议已对"
                "含幻觉/未核引用的投稿实施处罚）")
    if c["partial"]:
        return (f"🟡 投稿前结论：可提交，但建议先处理 {c['partial']} 条 partial"
                "（降级使用项，正文引用需注明保留意见）")
    return "✅ 投稿前结论：全部 verified——可进入投稿流程"


def render_md(results: list, offline: bool, profile: str = "general") -> str:
    sc = compute_scorecard(results)
    c = sc["counts"]
    lines = [
        "# 引用机械验证报告",
        f"- 验证器：verify_refs.py v{VERSION} · 模式：{'offline（未联网）' if offline else 'online'}"
        + (" · 医学信源预设" if profile == "medical" else ""),
    ]
    if profile == "medical":
        lines.append("- ⚠️ 免责声明：本报告仅为信源机械核验，不构成证据分级结论或医疗建议；"
                     "预印本/社区层来源不得支撑医学结论。")
    lines.append(f"- {precheck_conclusion(sc)}")
    lines += [
        "",
        "## CiteScore 置信度评分",
        f"### **{sc['score']} / 100 · {sc['grade']} 级**",
        "",
        f"- 总计 {sc['total']} 条：✅verified {c['verified']} · 🟡partial {c['partial']} · "
        f"⚠️unreachable {c['unreachable']} · ❌invalid {c['invalid']} · ⏸unverified {c['unverified']}",
        "- 计分：verified +10 / partial +4 / unreachable 0 / unverified −2 / invalid −8，"
        "满分 = 10 × 条数，归一化 0-100",
        "",
        "| # | 标题 | 层级 | HTTP | 判定 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        title = md_cell(r["title"], 48)
        # 含 Wayback 存档链的备注放宽截断（存档 URL 普遍 >90 字符，截断即废链）
        note = md_cell(r["note"], 200 if "web.archive.org" in (r.get("note") or "") else 90)
        lines.append(f"| {r['index']} | {title} | {r['tier']} | "
                     f"{r['http_status'] or '-'} | {VERDICT_ZH[r['verdict']]} | {note} |")
    flagged = [r for r in results if r["needs_human_check"] or r["verdict"] in ("invalid", "unverified")]
    if flagged:
        lines += ["", "## 待人工复核", ""]
        for r in flagged:
            lim = 200 if "web.archive.org" in (r.get("note") or "") else 110
            act = {"invalid": "建议：删除或更换信源",
                   "unreachable": "建议：人工打开原链复核",
                   "unverified": "建议：在线环境重跑验证"}.get(r["verdict"], "建议：按备注复核")
            lines.append(f"- #{r['index']} {md_cell(r['title'], 60)} → {r['verdict']}"
                         f"（{act}）：{md_cell(r['note'], lim)}")
    # v1.11 语义层判定区：仅当引用带结构化 semantic 字段时输出（无则与 v1.10
    # 输出逐字节一致，老消费者零感知）。机械层只做结构化透出与封顶，判定由模型做出。
    sem_rows = [r for r in results if r.get("semantic_audit")]
    if sem_rows:
        lines += ["", "## 语义层判定（模型在研究流程中做出，机械层结构化透出）", "",
                  "| # | support | 论断（claim） | 原文摘句 |",
                  "|---|---|---|---|"]
        for r in sem_rows:
            sa = r["semantic_audit"]
            lines.append(f"| {r['index']} | {md_cell(sa.get('support'), 16)} | "
                         f"{md_cell(sa.get('claim'), 60)} | "
                         f"{md_cell(sa.get('quote'), 60)} |")
        lines += ["", "support 取值：supported 支撑 / partial 部分支撑 / not_in_source "
                  "来源未包含 / contradicted 相矛盾 / unclear 无法判定；"
                  "not_in_source 与 contradicted 的条目已封顶 partial 并转人工复核。"]
    lines += ["", "## 能力边界矩阵", "",
              "- ✅ 机械层已抓伪造类型：" + "；".join(capability_matrix()["caught"]),
              "- 🧠 仍需语义层把关：" + "；".join(capability_matrix()["semantic"]),
              "- 🚫 不支持的输入：" + "；".join(capability_matrix()["unsupported"]),
              "", "## 判定说明", "",
              "- `verified`：可达 + 权威层(official/journal/preprint/media) + 字段完整 —— 可支撑正文结论",
              "- `partial`：可达但社区/博客层来源，或字段缺失 —— 降级使用，结论需注明",
              "- `unreachable`：抓取失败（404/超时/反爬）—— 不等于不存在，需人工打开复核",
              "- `invalid`：无 URL/DOI 或格式错误 —— 不得进入报告",
              "- 语义验证（来源是否支持论断）由模型完成，本报告只覆盖机械层", ""]
    return "\n".join(lines)


def render_html(results: list, offline: bool, profile: str = "general") -> str:
    """v1.7：自包含单文件 HTML 报告——零外链（无外部 CSS/JS/字体）、移动端可读，
    用作给导师/编辑的存档分享件（与 BibTeX/CSV 台账并列的第三种交付物）。
    动态内容全部经 html_escape；备注中的 URL 转为可点击链接。"""
    sc = compute_scorecard(results)
    c = sc["counts"]
    e = html_escape
    vcls = {"verified": "v-ok", "partial": "v-part", "unreachable": "v-unreach",
            "invalid": "v-bad", "unverified": "v-unk"}

    def linkify(note: str) -> str:
        s = e(str(note or ""))
        return re.sub(r"(https?://[^\s<\"]+)",
                      lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', s)

    rows = []
    for r in results:
        rows.append(
            f"<tr><td>{r['index']}</td>"
            f"<td>{e(str(r.get('title') or ''))}</td>"
            f"<td>{e(str(r.get('tier') or ''))}</td>"
            f"<td>{r.get('http_status') if r.get('http_status') is not None else '-'}</td>"
            f"<td class='{vcls[r['verdict']]}'><b>{VERDICT_ZH[r['verdict']]}</b></td>"
            f"<td class='note'>{linkify(r.get('note'))}</td></tr>")

    actions = {"invalid": "建议：删除或更换信源", "unreachable": "建议：人工打开原链复核",
               "unverified": "建议：在线环境重跑验证"}
    review = []
    for r in results:
        if r.get("needs_human_check") or r["verdict"] in ("invalid", "unverified"):
            act = actions.get(r["verdict"], "建议：按备注复核")
            review.append(f"<li>#{r['index']} {e(str(r.get('title') or ''))} → "
                          f"<b>{r['verdict']}</b>（{act}）：{linkify(r.get('note'))}</li>")
    review_html = ("<h2>待人工复核</h2><ul>" + "".join(review) + "</ul>") if review else ""

    cap = capability_matrix()
    cap_html = (f"<h2>能力边界矩阵</h2>"
                f"<p>✅ <b>机械层已抓伪造类型</b>：{e('；'.join(cap['caught']))}</p>"
                f"<p>🧠 <b>仍需语义层把关</b>：{e('；'.join(cap['semantic']))}</p>"
                f"<p>🚫 <b>不支持的输入</b>：{e('；'.join(cap['unsupported']))}</p>")

    # v1.11 语义层判定区（仅当引用带结构化 semantic 字段时输出）
    sem_rows = [r for r in results if r.get("semantic_audit")]
    if sem_rows:
        sem_trs = "".join(
            f"<tr><td>{r['index']}</td>"
            f"<td>{e(str(r['semantic_audit'].get('support') or ''))}</td>"
            f"<td>{e(str(r['semantic_audit'].get('claim') or ''))}</td>"
            f"<td>{e(str(r['semantic_audit'].get('quote') or ''))}</td></tr>"
            for r in sem_rows)
        sem_html = (f"<h2>语义层判定</h2>"
                    f"<p class='meta'>模型在研究流程中做出，机械层结构化透出；"
                    f"not_in_source / contradicted 条目已封顶 partial 并转人工复核。</p>"
                    f"<table><tr><th>#</th><th>support</th><th>论断（claim）</th>"
                    f"<th>原文摘句</th></tr>{sem_trs}</table>")
    else:
        sem_html = ""

    med = ("<p class='disclaim'>⚠️ 免责声明：本报告仅为信源机械核验，不构成证据分级结论"
           "或医疗建议；预印本/社区层来源不得支撑医学结论。</p>") if profile == "medical" else ""
    pcls = "disclaim" if sc["counts"]["invalid"] or sc["counts"]["unreachable"] or sc["counts"]["unverified"] else "preok"
    pre = (f"<p class='{pcls}'>{e(precheck_conclusion(sc))}</p>")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>引用机械验证报告 · CiteScore {sc['score']}/{sc['grade']}</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
margin:0 auto;padding:16px;max-width:960px;color:#1c2733;background:#fbfaf7;line-height:1.55}}
h1{{font-size:1.3em}} .score{{font-size:2.6em;font-weight:700}}
.v-ok{{color:#1a7f37}} .v-part{{color:#9a6700}} .v-unreach{{color:#b45309}}
.v-bad{{color:#c1341b}} .v-unk{{color:#57606a}}
.preok{{color:#1a7f37;background:#e9f7ee;padding:8px 12px;border-radius:6px}}
table{{border-collapse:collapse;width:100%;font-size:.88em;background:#fff}}
td,th{{border:1px solid #d8d2c4;padding:6px 8px;vertical-align:top;text-align:left}}
td.note{{word-break:break-all}} a{{color:#0b5394;word-break:break-all}}
.disclaim{{color:#9a6700;background:#fdf6dd;padding:8px 12px;border-radius:6px}}
.meta{{color:#57606a}} footer{{margin-top:24px;color:#57606a;font-size:.85em;
border-top:1px solid #d8d2c4;padding-top:8px}}
</style></head><body>
<h1>引用机械验证报告</h1>
<p class="score">{sc['score']}<span style="font-size:.45em;color:#57606a"> / 100 · {sc['grade']} 级</span></p>
<p class="meta">验证器 verify_refs.py v{VERSION} · 模式：{'offline（未联网）' if offline else 'online'}
{' · 医学信源预设' if profile == 'medical' else ''}<br>
总计 {sc['total']} 条：✅verified {c['verified']} · 🟡partial {c['partial']} ·
⚠️unreachable {c['unreachable']} · ❌invalid {c['invalid']} · ⏸unverified {c['unverified']}</p>
{med}
{pre}
<table><tr><th>#</th><th>标题</th><th>层级</th><th>HTTP</th><th>判定</th><th>说明</th></tr>
{''.join(rows)}</table>
{review_html}
{sem_html}
{cap_html}
<h2>判定说明</h2>
<ul>
<li><b>verified</b>：可达 + 权威层 + 字段完整——可支撑正文结论</li>
<li><b>partial</b>：可达但社区/博客层，或字段/期刊/作者存疑——降级使用</li>
<li><b>unreachable</b>：抓取失败——不等于不存在，需人工打开复核</li>
<li><b>invalid</b>：无 URL/DOI、编号不存在或格式错误——不得进入报告</li>
</ul>
<footer>语义验证（来源是否支持论断）由模型完成，本报告只覆盖机械层；
指向真实可信页面的精心伪造仍需人工判断。cite-holmes · Cite Holmes</footer>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="deep-research 引用机械验证器（五态判定）")
    ap.add_argument("--refs", help="引用清单路径：JSON 数组（research_refs.json）或 BibTeX（refs.bib，v1.9）")
    ap.add_argument("--claims", help="内联 JSON 引用数组（同 --refs 的 schema）")
    ap.add_argument("--out", default="verify_report.md", help="Markdown 报告输出路径")
    ap.add_argument("--json-out", help="JSON 报告输出路径（默认 <out>.json）")
    ap.add_argument("--offline", action="store_true", help="不联网，仅结构/字段检查")
    ap.add_argument("--strict", action="store_true", help="unreachable/invalid 计为失败（exit 1）")
    ap.add_argument("--timeout", type=float, default=10.0, help="单 URL 超时秒数（默认 10）")
    ap.add_argument("--interval", type=float, default=1.0, help="请求间隔秒数（默认 1.0）")
    ap.add_argument("--profile", choices=["general", "medical"], default="general",
                    help="信源预设：medical=医学期刊层域名扩展(Cochrane/CTS/NMPA/CDC/万方等)+社区层降级警示")
    ap.add_argument("--export", help="附加导出，逗号分隔：bibtex（仅verified，可直接进论文）/ "
                    "csv（全量审计台账）/ auditjson（v1.9 透明工作底稿：逐项检查明细）")
    ap.add_argument("--format", choices=["md", "html"], default="md",
                    help="报告格式：md（默认）或 html（自包含单文件，零外链，可直接分享/存档）")
    ap.add_argument("--easy", action="store_true",
                    help="傻瓜模式：自动识别医学引用启用医学预设，验证后自动导出 bibtex+csv，无需其他参数")
    ap.add_argument("--openalex-key", default="",
                    help="OpenAlex API key（2026-02 起生产调用需要；也可用环境变量 OPENALEX_API_KEY）")
    ap.add_argument("--s2-key", default="",
                    help="Semantic Scholar API key（免钥为共享限速池；也可用环境变量 S2_API_KEY）")
    ap.add_argument("--mailto", default="",
                    help="联系邮箱：进入 Crossref polite pool（限速更宽松），机构/CI 用户建议配置")
    ap.add_argument("--workers", type=int, default=4,
                    help="引用并行验证线程数（默认 4；1=串行；offline 模式自动串行）。"
                         "条与条独立，整批耗时约 ÷N；v1.10 新增")
    ap.add_argument("--no-cache", action="store_true",
                    help="关闭持久磁盘缓存（v1.12 默认开：TTL 内复跑直接复用稳定判定，零外呼）")
    ap.add_argument("--cache-ttl", type=float, default=168.0,
                    help="磁盘缓存有效期小时数（默认 168=7 天；撤稿状态等可变信息以 TTL 为界）")
    ap.add_argument("--cache-path", default="~/.cache/cite-holmes/cache.sqlite3",
                    help="磁盘缓存文件路径（默认 ~/.cache/cite-holmes/cache.sqlite3）")
    ap.add_argument("--refresh-cache", action="store_true",
                    help="绕过缓存读取强制重验（结果仍回写缓存）")
    ap.add_argument("--proxy", default="",
                    help="显式 HTTP(S) 代理地址（如 http://127.0.0.1:7890）；"
                          "不指定时自动遵循 HTTP_PROXY/HTTPS_PROXY 环境变量")
    args = ap.parse_args()
    medical = args.profile == "medical"
    _net_reset()  # 断路器+全局网络降级状态按批次重置（v1.6/v1.10）
    if args.proxy.strip():
        proxy = args.proxy.strip()
        if "://" not in proxy:
            proxy = "http://" + proxy
        urllib.request.install_opener(urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})))
        print(f"[proxy] 显式代理已启用：{proxy}")
    args.cache = not args.no_cache
    args.cache_path = os.path.expanduser(args.cache_path)
    _OPTS.update({
        "openalex_key": args.openalex_key or os.environ.get("OPENALEX_API_KEY", ""),
        "s2_key": args.s2_key or os.environ.get("S2_API_KEY", ""),
        "mailto": args.mailto.strip(),
    })

    if not args.refs and not args.claims:
        ap.error("需要 --refs 或 --claims 之一")
    try:
        if args.claims:
            refs = json.loads(args.claims)
        else:
            refs = load_refs_file(args.refs)  # v1.9：JSON 或 BibTeX 自动识别
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ 读取引用清单失败：{e}", file=sys.stderr)
        print("   支持 JSON 数组（research_refs.json）或 BibTeX 文件（v1.9 起 --refs refs.bib）",
              file=sys.stderr)
        return 2
    if not isinstance(refs, list) or not refs:
        print("❌ 引用清单须为非空数组（JSON 或 BibTeX）", file=sys.stderr)
        return 2

    if args.easy:
        # 傻瓜模式：有 PMID/PubMed 信号 → 直接启用医学预设；仅医学期刊域命中
        # （如万方）需 ≥2 条才触发——v1.8 修复：单条万方来源的技术类清单被误判成医学清单
        hints = False
        med_hits = 0
        for r in refs:
            if not isinstance(r, dict):
                continue
            u = str(r.get("url") or "")
            if str(r.get("pmid") or "").strip() or "pubmed" in u.lower():
                hints = True
                break
            try:
                if classify_tier(u, True) == "journal" and classify_tier(u, False) == "blog":
                    med_hits += 1
            except Exception:
                pass
        if not hints and med_hits >= 2:
            hints = True
        if hints:
            args.profile = "medical"
        if not args.export:
            args.export = "bibtex,csv"
        medical = args.profile == "medical"
        print(f"[easy] 傻瓜模式：医学预设={'开' if medical else '关'}；自动导出 {args.export}")

    def _safe_verify_one(i, ref):
        # 单条坏数据（非对象/标量/处理异常）降级为该条 invalid，绝不拖垮整批
        if not isinstance(ref, dict):
            return {"index": i, "title": str(ref)[:48], "url": "", "doi": "", "pmid": "",
                    "arxiv": "", "source": "", "year": None, "tier": "-", "semantic": "",
                    "verdict": "invalid",
                    "http_status": None, "note": "条目不是对象", "needs_human_check": False,
                    "checks": {}}
        # v1.12 持久磁盘缓存：TTL 内复用稳定判定（复跑零外呼）；--strict 绕过读保 CI
        # 诚实；--refresh-cache 绕过读但仍写；offline 不读不写（offline 判定不可入库）。
        # 仅带标识符(doi/url/pmid/arxiv)的引用入缓存——与批内缓存同口径；
        # 纯标题引用不走磁盘缓存（其判定多为结构性 invalid，无外呼可省）
        dc_key = (_dc_key(ref, args.profile)
                  if (args.cache and not args.offline and _cache_key(ref)) else "")
        if dc_key and not args.strict and not args.refresh_cache:
            hit = _dc_get(_dc_path(args), dc_key, args.cache_ttl)
            if hit is not None:
                r, age_h = hit
                r = dict(r)
                r["index"] = i
                r["note"] = ((r.get("note") + "；") if r.get("note") else "") +                     f"磁盘缓存命中（{age_h:.0f}h 前验证；--refresh-cache 强制重验）"
                return r
        try:
            r = verify_one(ref, i, args.offline, args.timeout, medical)
        except Exception as e:
            return {"index": i, "title": str(ref.get("title") or "")[:48] or "(无标题)",
                    "url": "", "doi": "", "pmid": "", "arxiv": "", "source": "", "year": None,
                    "tier": "-", "semantic": "", "verdict": "invalid",
                    "http_status": None, "note": f"条目处理异常（{type(e).__name__}）",
                    "needs_human_check": True, "checks": {}}
        if dc_key and r.get("verdict") in _DC_CACHEABLE:
            _dc_put(_dc_path(args), dc_key, r)
        return r

    results = [None] * len(refs)
    workers = max(1, int(args.workers or 1))
    if args.offline or workers <= 1 or len(refs) <= 1:
        # 串行路径（offline 模式 / --workers 1 / 单条）：保留逐条 interval 控频
        for i, ref in enumerate(refs, 1):
            r = _safe_verify_one(i, ref)
            results[i - 1] = r
            print(f"[{i}/{len(refs)}] {VERDICT_ZH[r['verdict']]} {r['title'][:40]}")
            if not args.offline and i < len(refs) and args.interval > 0:
                time.sleep(args.interval)
    else:
        # v1.10 引用级并行验证：条与条相互独立（共享状态仅断路器/限速器，均已加锁），
        # 整批耗时约 ÷workers——直攻评测 T 维「跨国数据库验证慢」。进度行按完成顺序
        # 打印（带真实序号），最终结果按 index 有序回填，报告/JSON 顺序与串行一致。
        # 并行下不做逐条 interval（并发本身就是节流；单主机礼貌由断路器+限速锁保证）。

        def _task(i, ref):
            # 双保险：任何意外异常都降级为该条 invalid，绝不拖垮整批
            try:
                return _safe_verify_one(i, ref)
            except Exception as e:
                return {"index": i,
                        "title": (str(ref.get("title") if isinstance(ref, dict) else ref)[:48]
                                  or "(无标题)"),
                        "url": "", "doi": "", "pmid": "", "arxiv": "", "source": "",
                        "year": None, "tier": "-", "semantic": "", "verdict": "invalid",
                        "http_status": None, "note": f"条目处理异常（{type(e).__name__}）",
                        "needs_human_check": True, "checks": {}}

        with ThreadPoolExecutor(max_workers=min(workers, len(refs))) as ex:
            # v1.10 批内缓存（领导者-跟随者）：同 DOI/URL/PMID/arXiv 只验证一次。
            # 并行下两条同键引用会同时起飞，「先查缓存后存储」永远轮空——④c 真网
            # 验收抓到，改为派发前去重：首个入键者为领导者，其余为跟随者，待领导者
            # 完成后复制判定（跟随者零网络调用）。
            futs = {}
            leader_of, followers = {}, {}
            for i, ref in enumerate(refs, 1):
                key = _cache_key(ref) if isinstance(ref, dict) else ()
                if key and key in leader_of:
                    followers.setdefault(leader_of[key], []).append(i)
                    continue
                if key:
                    leader_of[key] = i
                futs[i] = ex.submit(_task, i, ref)
            for fut in as_completed(futs.values()):
                r = fut.result()
                results[r["index"] - 1] = r
                print(f"[{r['index']}/{len(refs)}] {VERDICT_ZH[r['verdict']]} {r['title'][:40]}")
            for lead_idx in sorted(followers):
                lead = results[lead_idx - 1]
                for j in followers[lead_idx]:
                    r = dict(lead)
                    r["checks"] = dict(lead.get("checks") or {})
                    r["index"] = j
                    # v1.11 语义底稿按各自引用重建（缓存只复用机械判定——同
                    # DOI/URL 的两条引用可以引向不同论断，语义判定不得共享）
                    r["semantic_audit"] = build_semantic_audit(refs[j - 1])
                    r["note"] = ((lead.get("note") + "；") if lead.get("note") else "") + \
                        "同 DOI/URL 本批已验证，复用缓存判定"
                    results[j - 1] = r
                    print(f"[{j}/{len(refs)}] {VERDICT_ZH[r['verdict']]} {r['title'][:40]}")
        if _NET_STATE["degraded"]:
            print("⚠️ 全局网络降级：本批次多个外部主机连续传输失败（出海受限特征），"
                  "部分外呼已快速跳过——建议配置代理/更换网络后重跑以获得更完整结果")

    mark_duplicates(results)
    apply_semantic_cap(results)  # v1.11：语义否定判定封顶（在去重后统一执行）
    scorecard = compute_scorecard(results)
    content = (render_html(results, args.offline, args.profile) if args.format == "html"
               else render_md(results, args.offline, args.profile))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(content)
    json_path = args.json_out or (args.out.rsplit(".", 1)[0] + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "profile": args.profile, "offline": args.offline,
                   "scorecard": scorecard, "results": results},
                  f, ensure_ascii=False, indent=2)
    print(f"CiteScore: {scorecard['score']}/100 ({scorecard['grade']} 级，{scorecard['total']} 条)")

    if args.export:
        base = args.out.rsplit(".", 1)[0] if "." in args.out else args.out
        for fmt in [x.strip().lower() for x in args.export.split(",") if x.strip()]:
            if fmt == "bibtex":
                p = base + ".bib"
                n = export_bibtex(results, p)
                print(f"导出：{p}（{n} 条 verified，可直接进论文）")
            elif fmt == "csv":
                p = base + ".csv"
                export_csv(results, p)
                print(f"导出：{p}（{len(results)} 条全量审计台账）")
            elif fmt == "auditjson":
                p = base + ".audit.json"
                export_audit(results, p, args.offline, args.profile)
                print(f"导出：{p}（透明工作底稿：逐项检查明细）")
            else:
                print(f"⚠️ 未知导出格式 {fmt}（支持 bibtex,csv,auditjson）", file=sys.stderr)

    bad = [r for r in results if r["verdict"] in ("unreachable", "invalid")]
    print(f"\n报告：{args.out}\nJSON：{json_path}")
    if bad:
        print(f"⚠️ {len(bad)} 条 unreachable/invalid" + ("（strict 模式 → exit 1）" if args.strict else ""))
    return 1 if (args.strict and bad) else 0


def main_with_args(argv: list) -> int:
    """程序化调用入口（测试/其他脚本用）。argv 不含脚本名。"""
    old = sys.argv
    sys.argv = [sys.argv[0]] + list(argv)
    try:
        return main()
    finally:
        sys.argv = old


if __name__ == "__main__":
    sys.exit(main())
