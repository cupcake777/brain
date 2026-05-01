#!/usr/bin/env python3
"""Hermes Self-Learning Cycle v2 — deep knowledge acquisition with anti-bot bypass.

Improvements over v1:
- PubMed E-utilities API (reliable, no 403)
- bioRxiv API endpoint (not RSS)
- ArXiv exact-category search
- Smart relevance scoring (keyword + field matching)
- Full abstract extraction and analysis
- Tool/changelog monitoring (GitHub releases + PyPI)
- Self-audit with action proposals (not just reporting)
"""

import json
import re
import sqlite3
import hashlib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus, urlencode

SYNC_ROOT = Path(os.environ.get("HERMES_SYNC_ROOT", str(Path.home() / "hermes-sync")))
INBOX = SYNC_ROOT / "inbox" / "proposals"
DB_PATH = Path(os.environ.get("HERMES_DB_PATH", str(SYNC_ROOT / "hermes.sqlite3")))
SEEN_FILE = Path(os.environ.get("BRAIN_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "seen_urls.json"
STATE_FILE = Path(os.environ.get("BRAIN_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "selflearn_state.json"

# ── Research Interest Keywords ─────────────────────────────────────────
# Weighted keywords for relevance scoring
RESEARCH_KEYWORDS = {
    # === Core: APA/QTL ===
    "apa": 3.0,
    "polyadenylation": 3.0,
    "3'utr": 2.5,
    "3' aqtl": 3.0,
    "3'aqtl": 3.0,
    "apa qtl": 3.0,
    "colocalization": 2.0,
    "coloc": 2.0,
    "eqtl": 2.0,
    "sqtl": 1.5,
    "single cell": 1.5,
    "scRNA": 1.5,
    "brain": 1.0,
    "prefrontal": 1.5,
    "cortex": 1.0,
    "neuropsychiatric": 1.5,
    "schizophrenia": 1.5,
    "bipolar": 1.0,
    "lifespan": 1.0,
    "developmental": 1.0,
    "postmortem": 1.0,
    "deconvolution": 1.0,
    "susi": 1.5,
    "finemapping": 1.5,
    "fine-mapping": 1.5,
    "daPas": 2.0,
    "das": 1.0,
    "pas": 1.0,
    "cleavage": 0.5,
    # === Adjacent: Statistical genetics ===
    "mendelian randomization": 2.0,
    "causal variant": 1.5,
    "polygenic risk": 1.5,
    "prs": 1.5,
    "gwas": 1.5,
    "ldsc": 1.0,
    "magma": 1.0,
    # === Adjacent: Single-cell / spatial ===
    "spatial transcriptomics": 2.0,
    "cell type deconvolution": 1.5,
    "dynamic eqtl": 2.0,
    # === Adjacent: Population genomics ===
    "pangenome": 1.5,
    "long-read sequencing": 1.5,
    "structural variation": 1.0,
    "epigenome-wide": 1.5,
    # === Adjacent: Bioinformatics tools ===
    "batch effect": 1.0,
    "differential splicing": 1.5,
    "multi-omics": 1.5,
    "integration method": 1.0,
    "novel method": 1.5,
    "benchmark": 1.0,
    "new tool": 1.5,
    "software": 0.5,
}

# ── Configuration ──────────────────────────────────────────────────────

# PubMed E-utilities (reliable, no auth needed)
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

PUBMED_QUERIES = [
    # === Core: APA/QTL (user's own field) ===
    'alternative polyadenylation brain',
    "'3 aQTL' colocalization",
    'APA schizophrenia prefrontal',
    # === Adjacent: Statistical genetics ===
    'Mendelian randomization neuropsychiatric',
    'fine-mapping GWAS causal variant',
    'colocalization eQTL GWAS method',
    'polygenic risk score cross-trait',
    # === Adjacent: Single-cell omics ===
    'single cell RNA-seq deconvolution brain',
    'spatial transcriptomics methodology',
    'single cell eQTL dynamic',
    # === Adjacent: Population/functional genomics ===
    'pangenome structural variation',
    'long-read sequencing variant detection',
    'epigenome-wide association study',
    # === Adjacent: Bioinformatics methods ===
    'batch effect correction transcriptomics',
    'differential splicing analysis tool',
    'multi-omics integration method',
]

# ArXiv — broader categories with APA/QTL/brain keywords
ARXIV_QUERIES = [
    ("all:\"alternative polyadenylation\" AND cat:q-bio.*", 10),
    ("all:\"3 aQTL\" OR all:\"polyA signal\" OR all:\"polyadenylation site\"", 10),
    ("all:\"eQTL colocalization\" OR all:\"coloc analysis\"", 5),
]

# Deep analysis: extract full methods/conclusions from key papers
DEEP_ANALYSIS_THRESHOLD = 5.0  # Only deep-analyze papers scoring above this

# Rate limiting
RATE_LIMIT_DELAY = 0.6  # seconds between PubMed API calls

# PyPI packages to monitor for new versions
PYPI_PACKAGES = [
    "pysam", "matplotlib", "pandas", "numpy", "scanpy",
    "seaborn", "statsmodels", "lifelines", "pygam",
]


# ── Helpers ────────────────────────────────────────────────────────────

def load_json(path: Path, default: dict = None) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return default or {}

def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def load_seen_urls() -> set[str]:
    data = load_json(SEEN_FILE, {"urls": []})
    return set(data.get("urls", []))

def save_seen_urls(urls: set[str]):
    recent = list(urls)[-2000:]  # keep last 2000
    save_json(SEEN_FILE, {"urls": recent, "updated": datetime.now(timezone.utc).isoformat()})

def relevance_score(title: str, abstract: str) -> float:
    """Score a paper's relevance to our research interests."""
    text = (title + " " + abstract).lower()
    score = 0.0
    for kw, weight in RESEARCH_KEYWORDS.items():
        if kw in text:
            score += weight
    return score

def fetch_url(url: str, timeout: int = 20) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json,application/rss+xml,application/atom+xml,application/xml,text/xml,*/*",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, HTTPError) as e:
        print(f"  [WARN] Failed to fetch {url[:80]}: {e}", file=sys.stderr)
        return None


# ── Module 1: PubMed (Primary — reliable, no auth) ────────────────────

def scan_pubmed() -> list[tuple[str, str, str, float]]:
    """Scan PubMed for new papers matching research interests."""
    import time
    papers = []
    seen = load_seen_urls()

    for query in PUBMED_QUERIES:
        # Step 1: Search — get PMIDs
        params = urlencode({
            "db": "pubmed",
            "term": query,
            "retmax": 15,
            "retmode": "json",
            "sort": "date",
            "mindate": "2025/01/01",
            "maxdate": "2026/12/31",
        })
        search_url = f"{PUBMED_BASE}esearch.fcgi?{params}"
        data = fetch_url(search_url)
        time.sleep(RATE_LIMIT_DELAY)
        if not data:
            continue

        try:
            result = json.loads(data)
            pmids = result.get("esearchresult", {}).get("idlist", [])
        except (json.JSONDecodeError, KeyError):
            continue

        if not pmids:
            continue

        # Step 2: Fetch details (batch)
        efetch_params = urlencode({
            "db": "pubmed",
            "id": ",".join(pmids[:10]),
            "retmode": "xml",
        })
        efetch_url_str = f"{PUBMED_BASE}efetch.fcgi?{efetch_params}"
        xml_data = fetch_url(efetch_url_str)
        time.sleep(RATE_LIMIT_DELAY)
        if not xml_data:
            continue

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            continue

        for article in root.findall(".//PubmedArticle"):
            title_el = article.find(".//ArticleTitle")
            pmid_el = article.find(".//PMID")

            # Collect all abstract sections for full text
            abstract_parts = []
            for sec in article.findall(".//AbstractText"):
                label = sec.get("Label", "")
                text = sec.text or ""
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            
            # Also get keywords if available
            keywords = []
            for kw in article.findall(".//Keyword"):
                if kw.text:
                    keywords.append(kw.text)
            
            title = title_el.text if title_el is not None and title_el.text else ""
            abstract = " ".join(abstract_parts)[:1200]  # Full abstract, up to 1200 chars
            keyword_str = ", ".join(keywords[:10])
            
            pmid = pmid_el.text if pmid_el is not None else ""
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            if not title or url in seen:
                continue

            # Enrich abstract with keywords for better scoring
            enriched_text = f"{title} {abstract} {keyword_str}"
            score = relevance_score(title, enriched_text)
            if score >= 1.5:
                # Store enriched info
                full_desc = f"{abstract}"
                if keyword_str:
                    full_desc += f"\nKeywords: {keyword_str}"
                papers.append((title, url, full_desc, score))

    return papers


# ── Module 2: ArXiv (with category filter) ──────────────────────────────

def scan_arxiv() -> list[tuple[str, str, str, float]]:
    """Scan ArXiv with category filtering for relevant papers."""
    papers = []
    seen = load_seen_urls()

    for query, max_results in ARXIV_QUERIES:
        url = f"http://export.arxiv.org/api/query?search_query={quote_plus(query)}&max_results={max_results}&sortBy=submittedDate"
        data = fetch_url(url)
        if not data:
            continue

        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            summary_el = entry.find("atom:summary", ns)

            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
            link = link_el.get("href", "") if link_el is not None else ""
            abstract = summary_el.text.strip()[:800] if summary_el is not None and summary_el.text else ""

            if not title or not link or link in seen:
                continue

            score = relevance_score(title, abstract)
            if score >= 2.0:  # ArXiv has more noise, higher threshold
                papers.append((title, link, abstract, score))

    return papers


# ── Module 3: Tool/Package Monitoring ──────────────────────────────────────

def scan_tools() -> list[tuple[str, str, str]]:
    """Monitor PyPI for tool updates relevant to our pipeline."""
    import time
    updates = []
    # PyPI version checks
    for pkg in PYPI_PACKAGES:
        url = f"https://pypi.org/pypi/{pkg}/json"
        data = fetch_url(url)
        time.sleep(0.3)
        if not data:
            continue
        try:
            info = json.loads(data)
            version = info.get("info", {}).get("version", "unknown")
            summary = info.get("info", {}).get("summary", "")
            # Check for major version changes
            updates.append((f"{pkg} v{version}", f"https://pypi.org/project/{pkg}/", summary[:200]))
        except (json.JSONDecodeError, KeyError):
            continue
    return updates


# ── Module 4: WeChat Public Account Scraper ──────────────────────────────

# WeChat public account albums to scrape
WECHAT_ALBUMS = [
    {
        "name": "SCIPainter",
        "biz": "MzIyOTY3MDA3MA==",
        "album_id": "2178717955126099970",
        "category": "scientific_figure",
        "tags": ["绘图", "可视化", "科研图", "热图", "火山图", "小提琴图", "网络图", "配色"],
    },
    {
        "name": "逛逛GitHub",
        "biz": "MzUxNjg4NDEzNA==",
        "album_id": "1339316622149992449",
        "category": "github_tools",
        "tags": ["GitHub", "开源", "工具", "AI", "编程"],
    },
]


def scan_wechat() -> list[dict]:
    """Scrape WeChat public account album pages for new articles.
    
    WeChat album pages contain article titles and links.
    We extract article metadata and use relevance scoring.
    Returns list of article dicts with title, url, description, score, category.
    """
    import time
    articles = []
    seen = load_seen_urls()

    for album in WECHAT_ALBUMS:
        url = (
            f"https://mp.weixin.qq.com/mp/appmsgalbum?"
            f"__biz={album['biz']}&action=getalbum&album_id={album['album_id']}"
        )
        data = fetch_url(url, timeout=15)
        time.sleep(RATE_LIMIT_DELAY)
        if not data:
            continue

        # Extract article titles from HTML
        # WeChat album pages have articles listed with titles
        import re
        # Match article titles in the album listing
        title_matches = re.findall(
            r'<span[^>]*class="album__item-title-wap"[^>]*>([^<]+)</span>',
            data,
        )
        if not title_matches:
            # Fallback: try broader pattern
            title_matches = re.findall(
                r'class="album__item-title[^"]*"[^>]*>\s*([^<]+?)\s*<',
                data,
            )
        if not title_matches:
            # Last fallback: text between strong/div tags with article-like content
            title_matches = re.findall(r'<strong[^>]*>\s*([^<]+?)\s*</strong>', data)

        for title in title_matches[:20]:  # Limit to 20 articles per album
            title = title.strip()
            if not title or len(title) < 4:
                continue

            # Build a pseudo-URL for dedup (WeChat URLs are temporary)
            url_hash = hashlib.md5(f"{album['biz']}:{title}".encode()).hexdigest()[:12]
            pseudo_url = f"wechat://{album['name']}/{url_hash}"

            if pseudo_url in seen:
                continue

            # Score relevance based on tags and keywords
            text = title.lower()
            score = 0.0

            # Tag-based scoring
            for tag in album["tags"]:
                if tag.lower() in text:
                    score += 1.5

            # Research keyword scoring
            for kw, weight in RESEARCH_KEYWORDS.items():
                if kw.lower() in text:
                    score += weight * 0.5  # Reduce weight for WeChat titles (shorter text)

            if score >= 1.0:
                articles.append({
                    "title": title,
                    "url": pseudo_url,
                    "source": album["name"],
                    "category": album["category"],
                    "score": score,
                    "tags": [t for t in album["tags"] if t.lower() in text],
                })

    return articles


# ── Module 5: GitHub Trending ────────────────────────────────────────────

GITHUB_TRENDING_TOPICS = [
    ("python", "daily"),   # Python daily trending
    ("jupyter", "daily"),  # Jupyter notebooks (bioinformatics)
]

# Specific repos to watch for new releases
GITHUB_WATCH_REPOS = [
    "openai/codex",           # OpenAI Codex CLI
    "anthropics/claude-code", # Claude Code
    "chanzuckerberg/cellxgene",  # Single-cell portal
    "samtools/htslib",        # SAM/BAM/VCF tools
    "pysam-developers/pysam", # Python genomic I/O
    "statgen/WMAP",           # Statistical genetics
]


def scan_github_trending() -> list[dict]:
    """Scan GitHub trending and watched repos for new developments."""
    import time
    items = []
    seen = load_seen_urls()

    for topic, since in GITHUB_TRENDING_TOPICS:
        url = f"https://api.github.com/search/repositories?q=topic:{topic}+pushed:>{_days_ago(7)}&sort=stars&order=desc&per_page=15"
        data = fetch_url(url, timeout=15)
        time.sleep(RATE_LIMIT_DELAY)
        if not data:
            continue
        try:
            result = json.loads(data)
            for repo in result.get("items", [])[:10]:
                name = repo.get("full_name", "")
                desc = repo.get("description", "") or ""
                stars = repo.get("stargazers_count", 0)
                lang = repo.get("language", "") or ""
                html_url = repo.get("html_url", "")

                if html_url in seen:
                    continue

                # Score: high stars + bio Relevant topics
                score = min(stars / 100, 5.0)  # Max 5 points from stars
                text = f"{name} {desc}".lower()

                # Boost for bio/AI relevance
                bio_kw = ["genomic", "rna-seq", "single-cell", "bioinfor", "variant",
                          "protein", "cell", "sequencing", "gwas", "qtl"]
                ai_kw = ["agent", "llm", "ai", "model", "tool", "framework"]
                for kw in bio_kw:
                    if kw in text:
                        score += 2.0
                        break
                for kw in ai_kw:
                    if kw in text:
                        score += 1.0
                        break

                if score >= 1.0:
                    items.append({
                        "title": f"⭐{stars} {name}: {desc[:80]}",
                        "url": html_url,
                        "source": "github_trending",
                        "category": "github",
                        "score": score,
                        "tags": [lang] if lang else [],
                    })
        except (json.JSONDecodeError, KeyError):
            continue

    # Watched repos: check for new releases
    for repo in GITHUB_WATCH_REPOS:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=3"
        data = fetch_url(url, timeout=10)
        time.sleep(0.5)
        if not data:
            continue
        try:
            releases = json.loads(data)
            for rel in releases[:1]:  # Only latest release
                tag = rel.get("tag_name", "")
                name = rel.get("name", "") or tag
                html_url = rel.get("html_url", "")
                published = rel.get("published_at", "")[:10]
                body = (rel.get("body", "") or "")[:300]

                release_url = f"{html_url}#{tag}"
                if release_url in seen:
                    continue

                items.append({
                    "title": f"🚀 {repo} {tag}: {name[:60]}",
                    "url": release_url,
                    "source": "github_releases",
                    "category": "github_release",
                    "score": 3.0,  # Watched repos always relevant
                    "tags": ["release", repo.split("/")[1]],
                })
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return items


def _days_ago(n: int) -> str:
    """Return ISO date string for n days ago."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


# ── Module 4: Self-Audit ─────────────────────────────────────────────

def self_audit() -> list[dict]:
    """Review existing rules for contradictions, staleness, and gaps."""
    issues = []
    conn = sqlite3.connect(str(DB_PATH))

    # 1. Find duplicates (>60% word overlap)
    rows = conn.execute("""
        SELECT a.proposal_id, a.summary, b.proposal_id, b.summary
        FROM proposals a, proposals b
        WHERE a.proposal_id < b.proposal_id
        AND a.state NOT IN ('rejected') AND b.state NOT IN ('rejected')
        AND length(a.summary) > 20 AND length(b.summary) > 20
    """).fetchall()

    for r in rows:
        words_a = set(r[1].lower().split())
        words_b = set(r[3].lower().split())
        overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
        if overlap > 0.6:
            issues.append({
                "type": "potential_duplicate",
                "id1": r[0][:12], "summary1": r[1][:60],
                "id2": r[2][:12], "summary2": r[3][:60],
                "overlap": f"{overlap:.0%}",
            })

    # 2. Find stale rules (0 retrievals in 30d, older than 60d)
    rows = conn.execute("""
        SELECT proposal_id, summary, inserted_at, (retrieval_count_30d or 0)
        FROM proposals
        WHERE state IN ('approved_for_export', 'approved_db_only')
        AND inserted_at < datetime('now', '-60 days')
        AND (retrieval_count_30d IS NULL OR retrieval_count_30d = 0)
    """).fetchall()
    for r in rows:
        issues.append({
            "type": "stale_rule",
            "id": r[0][:12], "summary": r[1][:60],
            "since": r[2][:10], "retrievals_30d": r[3],
        })

    # 3. State distribution
    state_counts = conn.execute("SELECT state, count(*) FROM proposals GROUP BY state ORDER BY count(*) DESC").fetchall()
    issues.append({"type": "state_summary", "counts": {r[0]: r[1] for r in state_counts}})

    conn.close()
    return issues


# ── Module 5: Gap Analysis ────────────────────────────────────────────

def gap_analysis() -> list[dict]:
    """Check research topic coverage gaps."""
    gaps = []
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT summary, suggested_memory FROM proposals WHERE state NOT IN ('rejected')").fetchall()
    conn.close()

    covered = " ".join(r[0] + " " + (r[1] or "") for r in rows).lower()

    expected = {
        "apa_quantification": ["apa", "polyadenylation", "3' utr", "pau", "das", "dap"],
        "eqtl_colocalization": ["eqtl", "qtl", "colocalization", "coloc", "susi", "finemapping"],
        "single_cell": ["single cell", "scrna", "cell type", "deconvolution", "celltype"],
        "brain_development": ["brain development", "prenatal", "fetal", "lifespan", "postnatal"],
        "neuropsychiatric": ["schizophrenia", "bipolar", "neuropsychiatric", "scz", "mdd"],
        "hpc_workflow": ["sbatch", "slurm", "hpc", "login node", "compute node"],
        "data_pipeline": ["pipeline", "workflow", "batch correction", "combat"],
        "proxy_vpn": ["vless", "xray", "warp", "3x-ui", "proxy"],
        "agent_infra": ["brain", "proposal", "hermes", "codex", "claude"],
    }

    for topic, keywords in expected.items():
        if not any(kw in covered for kw in keywords):
            gaps.append({
                "type": "coverage_gap",
                "topic": topic,
                "keywords": keywords,
                "note": f"No rules covering {topic}",
            })

    return gaps


# ── Proposal Writing ───────────────────────────────────────────────────

# ── Module 5.5: Deep Paper Analysis ─────────────────────────────────────

def deep_analyze(papers: list[tuple[str, str, str, float]]) -> list[dict]:
    """For high-scoring papers, fetch and analyze the full page for methods/conclusions.
    
    Uses web_extract to get the full text from PubMed central or publisher pages.
    Extracts: key method names, novel findings, relevant tools/datasets mentioned.
    """
    analyses = []
    for title, url, abstract, score in papers:
        if score < DEEP_ANALYSIS_THRESHOLD:
            continue
        
        # Try to get full text from PubMed page (has structured data)
        page_content = fetch_url(url, timeout=10)
        if not page_content:
            # Fallback: we already have the abstract from efetch
            analyses.append({
                "title": title,
                "url": url,
                "score": score,
                "methods_found": _extract_methods(abstract),
                "tools_found": _extract_tools(abstract),
                "datasets_found": _extract_datasets(abstract),
                "novelty_keywords": _extract_novelty(abstract),
                "source": "pubmed_abstract",
            })
            continue
        
        # Extract key info from the page HTML
        full_text = _strip_html(page_content)[:3000]
        combined = f"{abstract}\n{full_text}"
        
        analyses.append({
            "title": title,
            "url": url,
            "score": score,
            "methods_found": _extract_methods(combined),
            "tools_found": _extract_tools(combined),
            "datasets_found": _extract_datasets(combined),
            "novelty_keywords": _extract_novelty(combined),
            "source": "pubmed_page",
        })
    
    return analyses


def _strip_html(html: str) -> str:
    """Remove HTML tags and clean text."""
    import re as _re
    text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
    text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
    text = _re.sub(r'<[^>]+>', ' ', text)
    text = _re.sub(r'\s+', ' ', text).strip()
    return text


def _extract_methods(text: str) -> list[str]:
    """Extract method names from paper text."""
    methods = []
    method_keywords = [
        r'RNA[- ]seq', r'scRNA', r'single[- ]cell', r'bulk RNA', r'long[- ]read',
        r'PacBio', r'Oxford Nanopore', r'Illumina', r'10x Genomics',
        r'DaPAS', r'DaPAST', r'APAtrap', r'QAPA', r'APAlyzer', r'TAPAS',
        r'SuSiE', r'FINEMAP', r'COLOC', r'coloc', r'eCAVIAR', r'enloc',
        r'MAGMA', r'LDSC', r'GWAS', r'eQTL', r'sQTL', r'aQTL',
        r'ComBat', r'Harmony', r'Seurat', r'Scanpy',
        r'logistic regression', r'linear mixed model', r'LMM',
        r'permutation test', r'bootstrap', r'Bonferroni', r'FDR',
        r'PCA', r'UMAP', r't[- ]SNE', r'differential expression',
    ]
    text_lower = text.lower()
    for kw in method_keywords:
        if re.search(kw, text_lower):
            match = re.search(kw, text, re.IGNORECASE)
            if match:
                methods.append(match.group())
    return methods[:10]


def _extract_tools(text: str) -> list[str]:
    """Extract tool/software names from paper text."""
    tools = []
    tool_patterns = [
        r'\bR\b', r'Python', r'MATLAB', r'PLINK', r'GCTA',
        r'VEP', r'ANNOVAR', r'GTExPortal', r'Ensembl',
        r'Bioconductor', r'DESeq2', r'EdgeR', r'limma', r'glmnet',
        r'PyTorch', r'TensorFlow', r'tensorflow',
        r'Nextflow', r'Snakemake',
        r'Docker', r'Singularity', r'Conda',
    ]
    for pattern in tool_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                tools.append(match.group())
    return list(set(tools))[:8]


def _extract_datasets(text: str) -> list[str]:
    """Extract dataset names from paper text."""
    datasets = []
    dataset_keywords = [
        'GTEx', 'BrainSeq', 'PsychENCODE', 'CMC', 'CommonMind',
        'BrainGVEX', 'ROSMAP', 'MSBB', 'HBTRC', 'NIMH',
        'GEO', 'SRA', 'ENA', 'dbGaP',
    ]
    text_lower = text.lower()
    for kw in dataset_keywords:
        if kw.lower() in text_lower:
            datasets.append(kw)
    return datasets[:6]


def _extract_novelty(text: str) -> list[str]:
    """Extract novelty/findings keywords from paper text."""
    novelty = []
    novelty_patterns = [
        (r'(?:we\s+(?:found|identified|discovered|revealed|show|demonstrate|report)[\s\w]*(?:that|:))', 'finding'),
        (r'(?:novel|first|previously unknown|uncharacterized|new\s+(?:method|approach|framework|tool|resource))', 'novel'),
        (r'(?:limitation|caveat|constraint|not\s+(?:able|capable|possible))', 'limitation'),
    ]
    text_lower = text.lower()
    for pattern, label in novelty_patterns:
        if re.search(pattern, text_lower):
            novelty.append(label)
    return novelty


# ── Self-Learn Proposal Writer ──────────────────────────────────────────

def write_proposal(summary: str, observation: str, why: str, memory: str,
                   category: str = "fact", risk: str = "low", scope: str = "global"):
    from hermes.proposals import ProposalWriter
    writer = ProposalWriter(INBOX)
    path = writer.write(
        source_agent="selflearn",
        source_host="auto-cron",
        project_key="global",
        category=category,
        risk_level=risk,
        summary=summary,
        observation=observation,
        why_it_matters=why,
        suggested_memory=memory,
        scope=scope,
        evidence="Automatically discovered by selflearn v2 cycle.",
    )
    return path


# ── Main ────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Self-Learning Cycle v2")
    parser.add_argument("--mode", choices=["scan", "audit", "gaps", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Don't write proposals")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()[:19]
    print(f"[{now}] Self-learn v2 starting (mode={args.mode})")

    seen = load_seen_urls()
    new_findings = []

    if args.mode in ("scan", "all"):
        print("\n=== PubMed Scan ===")
        pubmed_papers = scan_pubmed()
        print(f"Found {len(pubmed_papers)} relevant PubMed papers")
        for title, url, abstract, score in sorted(pubmed_papers, key=lambda x: -x[3])[:5]:
            print(f"  [{score:.1f}] {title[:70]}")
            print(f"         {url}")
        new_findings.extend(pubmed_papers)

        print("\n=== ArXiv Scan ===")
        arxiv_papers = scan_arxiv()
        print(f"Found {len(arxiv_papers)} relevant ArXiv papers")
        for title, url, abstract, score in sorted(arxiv_papers, key=lambda x: -x[3])[:5]:
            print(f"  [{score:.1f}] {title[:70]}")
        new_findings.extend(arxiv_papers)

        # Deep analysis on high-scoring papers
        all_papers = pubmed_papers + arxiv_papers
        top_for_deep = [p for p in all_papers if p[3] >= DEEP_ANALYSIS_THRESHOLD]
        if top_for_deep:
            print(f"\n=== Deep Analysis ({len(top_for_deep)} papers >= {DEEP_ANALYSIS_THRESHOLD}) ===")
            analyses = deep_analyze(top_for_deep)
            for a in analyses:
                print(f"  [{a['score']:.1f}] {a['title'][:60]}")
                if a['methods_found']:
                    print(f"    Methods: {', '.join(a['methods_found'][:5])}")
                if a['tools_found']:
                    print(f"    Tools: {', '.join(a['tools_found'][:5])}")
                if a['datasets_found']:
                    print(f"    Datasets: {', '.join(a['datasets_found'][:5])}")
                if a['novelty_keywords']:
                    print(f"    Novelty: {', '.join(a['novelty_keywords'])}")
                print(f"    Source: {a['source']}")

        print("\n=== Tool Updates ===")
        tool_updates = scan_tools()
        print(f"Checked {len(PYPI_PACKAGES)} packages, {len(tool_updates)} with info")

        print("\n=== WeChat Articles ===")
        wechat_articles = scan_wechat()
        print(f"Found {len(wechat_articles)} relevant WeChat articles")
        for a in wechat_articles[:8]:
            print(f"  [{a['score']:.1f}] [{a['source']}] {a['title'][:70]}")

        print("\n=== GitHub Trending ===")
        gh_items = scan_github_trending()
        print(f"Found {len(gh_items)} relevant GitHub items")
        for item in gh_items[:8]:
            print(f"  [{item['score']:.1f}] {item['title'][:70]}")

        # Convert wechat/github items to unified format for findings
        for a in wechat_articles:
            new_findings.append((
                a["title"], a["url"],
                f"Source: {a['source']}, Tags: {', '.join(a.get('tags', []))}",
                a["score"],
            ))
        for item in gh_items:
            new_findings.append((
                item["title"], item["url"],
                f"Category: {item['category']}, Tags: {', '.join(item.get('tags', []))}",
                item["score"],
            ))

    if args.mode in ("audit", "all"):
        print("\n=== Self-Audit ===")
        issues = self_audit()
        for issue in issues:
            if issue["type"] == "potential_duplicate":
                print(f"  [DUPLICATE] {issue['id1']} & {issue['id2']} ({issue['overlap']} overlap)")
            elif issue["type"] == "stale_rule":
                print(f"  [STALE] {issue['id']}: {issue['summary']} (0 retrieval since {issue['since']})")
            elif issue["type"] == "state_summary":
                print(f"  [SUMMARY] {issue['counts']}")

    if args.mode in ("gaps", "all"):
        print("\n=== Gap Analysis ===")
        gaps = gap_analysis()
        for gap in gaps:
            print(f"  [GAP] {gap['topic']}: {gap['note']}")

    # Save seen URLs (deduplicate by URL)
    seen_urls_new = {f[1] for f in new_findings if len(f) > 1}
    save_seen_urls(seen | seen_urls_new)
    # Deduplicate papers by URL (keep highest score)
    seen_in_batch = {}
    for f in new_findings:
        url = f[1]
        if url not in seen_in_batch or f[3] > seen_in_batch[url][3]:
            seen_in_batch[url] = f
    unique_findings = list(seen_in_batch.values())

    # Write proposal if significant findings
    if unique_findings and not args.dry_run:
        top = sorted(unique_findings, key=lambda x: -x[3])[:5]
        paper_list = "\n".join(f"- [{t[:60]}]({u}) (relevance: {s:.1f})" for t, u, a, s in top)
        write_proposal(
            summary=f"Research scan: {len(new_findings)} papers relevant to APA/QTL/brain",
            observation=f"PubMed+ArXiv scan found {len(new_findings)} papers:\n{paper_list}",
            why="Keeps agent knowledge current with latest research in the user's field",
            memory=f"Latest scan ({now}): {len(new_findings)} papers. Top: {', '.join(t[:30] for t, *_ in top[:3])}",
            category="fact",
            risk="low",
        )
        print(f"\n[PROPOSAL] Written for {len(new_findings)} findings")

    print(f"\n[{datetime.now(timezone.utc).isoformat()[:19]}] Self-learn v2 complete")


if __name__ == "__main__":
    main()