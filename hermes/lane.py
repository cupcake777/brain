"""Scene labels for Brain knowledge.

The user-facing split is a free-form `domain` slug.  Two values are
recommended because they match how the knowledge is actually used:

- tech: VPS / agent ops pitfalls
- science: HPC analysis notes

Anything else (writing, teaching, a project name) is stored as-is.
Old labels such as devops/study/global are aliases or unlabeled leftovers.
"""
from __future__ import annotations

import re

RECOMMENDED = ("tech", "science")

# Historical domain/project_key values that should become tech or science.
ALIASES: dict[str, str] = {
    "tech": "tech",
    "ops": "tech",
    "vps": "tech",
    "devops": "tech",
    "network": "tech",
    "security": "tech",
    "infra": "tech",
    "science": "science",
    "study": "science",
    "hpc": "science",
    "bio": "science",
    "apa": "science",
    "genomics": "science",
}

# These were used as "no real scene".  Fall through to text classification.
UNLABELED = {"", "global", "general", "project", "hermes", "brain"}

_SCIENCE_TERMS = (
    "slurm", "sbatch", "salloc", "srun", "squeue", "partition",
    "hpc", "furong", "gwas", "qtl", "snp", "gene", "genes",
    "clusterprofiler", "enricher", "term2gene", "annotationdbi",
    "bioconductor", "rscript", "seurat", "scanpy", "rna-seq", "scrna",
    "ggplot", "matplotlib", "scientific", "smr", "coloc", "eqtl",
    "gtex", "cytosignal", "manuscript", "data.table", "limma", "deseq",
    "bedtools", "samtools", "bcftools", "fasta", "bam", "vcf",
    "notify-hpc", "org.hs.eg.db", "prediXcan", "glmnet", "pptx",
    "powerpoint", "main figure", "plot.subtitle", "figure panel",
    "scientific ppt", "scientific article", "cu partition",
)

_TECH_TERMS = (
    "vps", "nginx", "systemd", "sqlite", "docker", "telegram",
    "cloudflare", "ufw", "caddy", "certbot", "syncthing", "gradio",
    "huggingface", "journalctl", "fail2ban", "xray", "mihomo", "clash",
    "brain.bioinfo", "embed.bioinfo", "sslcertverification",
    "uptime kuma", "n8n", "brain-query", "skill manager", "skillctl",
    "hermes-sync", "proposal inbox", "proxy-sub", "sub2api",
    "token", "api gateway", "tmux",
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._-]*", re.IGNORECASE)


def slug(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace(" ", "-")
    text = re.sub(r"[^a-z0-9._-]+", "", text)
    return text[:40]


def canonical(value: object) -> str:
    """Map a label to a recommended scene, or keep a custom slug."""
    raw = slug(value)
    if raw in ALIASES:
        return ALIASES[raw]
    return raw


def classify(text: str) -> str:
    """Guess tech vs science from free text.  Always returns one of RECOMMENDED."""
    blob = f" {str(text or '').lower()} "
    science = sum(1 for term in _SCIENCE_TERMS if term in blob)
    tech = sum(1 for term in _TECH_TERMS if term in blob)
    # Bare `cu` is the HPC partition name, but only count it next to job words.
    if re.search(r"\bcu\b", blob) and any(w in blob for w in ("partition", "salloc", "srun", "slurm", "sbatch")):
        science += 2
    if science > tech:
        return "science"
    if tech > science:
        return "tech"
    if science:
        return "science"
    return "tech"


def assign_lane(*, hinted: object = "", project_key: object = "", text: str = "") -> str:
    """Resolve the scene for a proposal or knowledge node.

    Custom slugs are preserved.  Legacy unlabeled values fall back to
    keyword classification, which only ever returns tech or science.
    """
    for candidate in (hinted, project_key):
        resolved = canonical(candidate)
        if resolved and resolved not in UNLABELED:
            return resolved
    return classify(text)


def lane_text(*parts: object) -> str:
    return "\n".join(str(part or "") for part in parts)
