# Note: This script generates intermediate CSV outputs which are not versioned.
# Outputs are excluded intentionally and can be regenerated.
"""
mine_candidates.py
==================
Full-scale documentation mining script for architectural constraint analysis.
Processes a unified local dataset (gh_* + sf_* folders) and produces 4 CSV outputs.

Usage:
    python mine_candidates.py ^
        --dataset_root "D:\\Desktop\\thesis_dataset" ^
        --out_dir "D:\\Desktop\\thesis_dataset\\_outputs" ^
        --log_dir "D:\\Desktop\\thesis_dataset\\_logs"

Optional:
    --run_id          <string>  Custom run identifier (auto-generated if omitted)
    --max_repos       <int>     Limit number of repos processed (for testing; 0 = no limit)
    --gh_mapping_csv  <path>    Mapping CSV for GitHub repo_id -> repo_name
                                (deterministic schema: must have columns repo_id, repo_name)
                                If omitted, defaults to <dataset_root>/repos.csv if present.

Outputs (_outputs folder):
    candidates.csv          explicit constraint candidates
    arch_descriptions.csv   architectural description candidates
    excluded_normative.csv  normative passages that failed gating or were excluded
    annotation.csv          union of all above (for manual labeling)
"""

import os
import re
import csv
import sys
import uuid
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional


# ===============================
# KEYWORD CONFIGURATION (English-only)
# ===============================

NORMATIVE_STRONG = [
    "must not",
    "shall not",
    "may not",
    "cannot",
    "must",
    "shall",
    "required",
    "mandatory",
    "prohibited",
    "forbidden",
]

NORMATIVE_WEAK = [
    "should not",
    "should",
]

STYLE_PHRASES = [
    "layered architecture",
    "clean architecture",
    "plugin architecture",
    "hexagonal",
    "microservice",
    "monolith",
    "mvc",
]

STRUCTURAL_NOUNS = [
    "layer",
    "module",
    "component",
    "package",
    "service",
    "api",
    "interface",
    "boundary",
    "domain",
    "infrastructure",
    "application",
    "presentation",
]

RELATION_VERBS = [
    "depend on",
    "communicate with",
    "import",
    "use",
    "call",
    "invoke",
    "access",
]

EXCLUSION_TOPICS = [
    "install",
    "installation",
    "setup",
    "quickstart",
    "build",
    "compile",
    "run",
    "execute",
    "usage",
    "how to",
    "example",
    "configuration",
    "config",
    "environment variable",
    "docker",
    "kubernetes",
    "pip",
    "npm",
    "maven",
    "gradle",
    "cargo",
    "contributing",
    "pull request",
    "issue",
    "code review",
    "branch",
    "commit",
    "merge",
    "ci",
    "pipeline",
    "test",
    "lint",
    "format",
    "formatter",
    "license",
    "security policy",

    # shell / cli
    "ls -la",
    "chmod",
    "chown",
    "sudo",
    "export ",
    "kubectl",
    "helm",
    "docker-compose",
    "dockerfile",

    # DevOps phrases
    "env var",
    ".env",
    "deployment",
    "deploy",
    "render",
    "container",

    # file permission phrases
    "chmod 644",
    "chmod 755",
    "mode 644",
    "mode 755",
    "permission",
    "permissions",
    "readable",
    "writable",
    "executable",
    "uid",
    "gid",
    "umask",

    # Launch/JVM config noise
    "localhost",
    "jvm options",
    "jvm option",
    "classpath",
    "classloader",
    "-dserver",
    "modprobe",
    "mknod",
]

OVERRIDE_KEYWORDS = [
    "architecture",
    "architectural",
    "design",
    "dependency rule",
    "layering",
    "constraints",
    "restriction",
    "cyclic dependency",
    "no dependency",
    "no direct access",
    "must not depend",
    "should not import",
]

EXCLUSION_PATH_SEGMENTS = [
    os.sep + ".github" + os.sep,
    os.sep + "deploy" + os.sep,
    os.sep + "deployment" + os.sep,
    os.sep + "docker" + os.sep,
    os.sep + ".circleci" + os.sep,
    os.sep + ".gitlab" + os.sep,
    os.sep + ".azure-pipelines" + os.sep,
]

EXCLUSION_FILENAMES_PREFIX = [
    "contributing",
    "code_of_conduct",
    "security",
    "license",
    "changelog",
    "dockerfile",
    "docker-compose",
    "compose",
    "deployment",
]

TEXT_EXTS = {".md", ".markdown", ".rst", ".txt", ".adoc"}

HARD_EXCLUDE_DIRS = {
    ".git", "node_modules", "target", "build", "dist",
    "vendor", ".idea", ".vscode",
}

MAX_FILE_BYTES = 2_000_000  # 2 MB


# ===============================
# CSV SCHEMA
# ===============================

CSV_COLUMNS = [
    "run_id",
    "timestamp_utc",
    "repo_id",
    "source",
    "repo_origin_name",
    "artifact_path",
    "paragraph_index",
    "lang",
    "candidate_type",
    "arch_hit",
    "has_style_phrase",
    "has_structural_noun",
    "has_relation_verb",
    "norm_hit",
    "norm_strength",
    "excluded",
    "norm_hits",
    "arch_hits",
    "excl_hits",
    "override_hits",
    "text",
]

ANNOTATION_EXTRA = [
    "label",
    "constraint_type",
    "norm_strength_review",
    "notes",
    "verified",
]

ANNOTATION_COLUMNS = CSV_COLUMNS + ANNOTATION_EXTRA


# ===============================
# UTILITIES
# ===============================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def sanitize_for_csv_cell(s: str) -> str:
    """
    Ensure one logical paragraph stays one physical CSV row when opened in Excel.
    Removes exotic control characters that Excel may treat as row breaks.
    """
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ").replace("\t", " ")

    # Strip ASCII control chars incl. vertical tab \x0b and form feed \x0c
    s = re.sub(r"[\x00-\x1F\x7F]", " ", s)

    # Unicode line separators
    s = s.replace("\u2028", " ").replace("\u2029", " ")

    return re.sub(r"\s{2,}", " ", s).strip()


def compile_phrase_patterns(phrases: List[str]) -> List[Tuple[str, re.Pattern]]:
    out = []
    for p in phrases:
        p_norm = p.strip().lower()
        if " " in p_norm:
            parts = [re.escape(x) for x in p_norm.split()]
            rx = r"\b" + r"\s+".join(parts) + r"\b"
        else:
            rx = r"\b" + re.escape(p_norm) + r"\b"
        out.append((p_norm, re.compile(rx, flags=re.IGNORECASE)))
    return out


NORM_STRONG_PATTERNS = compile_phrase_patterns(NORMATIVE_STRONG)
NORM_WEAK_PATTERNS   = compile_phrase_patterns(NORMATIVE_WEAK)
STYLE_PATTERNS       = compile_phrase_patterns(STYLE_PHRASES)
NOUN_PATTERNS        = compile_phrase_patterns(STRUCTURAL_NOUNS)
REL_PATTERNS         = compile_phrase_patterns(RELATION_VERBS)
EXCL_PATTERNS        = compile_phrase_patterns(EXCLUSION_TOPICS)
OVERRIDE_PATTERNS    = compile_phrase_patterns(OVERRIDE_KEYWORDS)


def find_hits(text: str, compiled: List[Tuple[str, re.Pattern]]) -> List[str]:
    return [label for label, rx in compiled if rx.search(text)]


def looks_like_excluded_artifact(rel_path: str) -> List[str]:
    hits = []
    low = rel_path.lower().replace("/", os.sep).replace("\\", os.sep)

    for seg in EXCLUSION_PATH_SEGMENTS:
        if seg in low:
            hits.append(seg.strip(os.sep))

    base_noext = os.path.splitext(os.path.basename(low))[0]
    for pref in EXCLUSION_FILENAMES_PREFIX:
        if base_noext.startswith(pref):
            hits.append(pref)

    return hits


# ===============================
# CODE/CONFIG DETECTION
# ===============================

def looks_like_code_or_config(paragraph: str) -> bool:
    s = paragraph.strip()
    if not s:
        return False

    lines = s.splitlines()
    if len(lines) >= 2:
        colon_lines = sum(1 for l in lines if re.match(r"^\s*[-\w.]+\s*:\s*\S*", l))
        if colon_lines >= 2:
            return True

        prompt_lines = sum(1 for l in lines if re.match(r"^\s*[$>#]\s+\S+", l))
        if prompt_lines >= 2:
            return True

        flag_lines = sum(1 for l in lines if re.search(r"\s--\w+", l))
        if flag_lines >= 2:
            return True

    st = s.lstrip()
    if st.startswith("{") and ":" in st and ("}" in st or "\n" in st):
        return True

    if st.startswith("<") and ">" in st and re.search(r"</?\w+", st):
        return True

    special = sum(1 for c in s if c in "{}[]<>:=/\\|`~")
    if special / max(1, len(s)) > 0.10:
        return True

    alpha = sum(1 for c in s if c.isalpha())
    if len(s) >= 60 and (alpha / len(s)) < 0.45:
        return True

    return False


# ===============================
# MAPPING LOADERS
# ===============================

def load_sf100_mapping(mapping_csv_path: str) -> Dict[str, str]:
    if not os.path.isfile(mapping_csv_path):
        raise FileNotFoundError(f"sf100_mapping.csv not found at: {mapping_csv_path}")

    with open(mapping_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]

        id_col, name_col = None, None
        for h in headers:
            hl = h.lower()
            if id_col is None and (hl in {"sf", "sf_id", "repo_id", "folder"} or "sf_" in hl):
                id_col = h
            if name_col is None and (any(x in hl for x in ("original", "name", "project")) or hl == "repo"):
                name_col = h

        if id_col is None or name_col is None:
            raise ValueError(
                f"Cannot infer columns in mapping CSV. Headers={headers}. "
                "Need one id col (sf_xxx) and one name col (original repo name)."
            )

        mapping: Dict[str, str] = {}
        for row in reader:
            repo_id = (row.get(id_col) or "").strip().lower()
            origin  = (row.get(name_col) or "").strip()
            if repo_id and origin:
                mapping[repo_id] = origin
    return mapping


def load_gh_mapping(path: Optional[str]) -> Dict[str, str]:
    """
    Deterministic GitHub mapping loader:
      - Requires headers exactly: repo_id, repo_name
      - Maps: lower(repo_id) -> repo_name
    """
    if not path:
        return {}
    if not os.path.isfile(path):
        raise FileNotFoundError(f"GitHub mapping CSV not found at: {path}")

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        if not headers:
            raise ValueError(f"Empty header row in GitHub mapping CSV: {path}")

        header_lc = {h.lower(): h for h in headers}
        required = {"repo_id", "repo_name"}
        if not required.issubset(set(header_lc.keys())):
            raise ValueError(
                f"GitHub mapping CSV must contain headers {sorted(required)}. "
                f"Found headers={headers} in {path}"
            )

        id_col = header_lc["repo_id"]
        name_col = header_lc["repo_name"]

        mapping: Dict[str, str] = {}
        for row in reader:
            rid = (row.get(id_col) or "").strip().lower()
            nm  = (row.get(name_col) or "").strip()
            if rid and nm:
                mapping[rid] = nm
        return mapping


# ===============================
# REPO SCAN
# ===============================

def scan_repos(dataset_root: str, sf_mapping: Dict[str, str], gh_mapping: Dict[str, str]) -> List[Dict[str, str]]:
    repos = []
    for name in os.listdir(dataset_root):
        full = os.path.join(dataset_root, name)
        if not os.path.isdir(full):
            continue

        if re.fullmatch(r"gh_\d{3}", name, flags=re.IGNORECASE):
            rid = name.strip().lower()
            repos.append({
                "repo_id": rid,
                "source": "github",
                "repo_root": full,
                "repo_origin_name": gh_mapping.get(rid, ""),
            })
        elif re.fullmatch(r"sf_\d{3}", name, flags=re.IGNORECASE):
            rid = name.strip().lower()
            repos.append({
                "repo_id": rid,
                "source": "sf100",
                "repo_root": full,
                "repo_origin_name": sf_mapping.get(rid, ""),
            })

    repos.sort(key=lambda e: (e["repo_id"].split("_")[0].lower(), int(e["repo_id"].split("_")[1])))
    return repos


# ===============================
# DOCUMENTATION FILE COLLECTION
# ===============================

def is_text_doc(path: str) -> bool:
    base = os.path.basename(path)
    ext  = os.path.splitext(base)[1].lower()
    if base.lower().startswith("readme"):
        return True
    return ext in TEXT_EXTS


def collect_doc_files(repo_root: str) -> List[str]:
    result = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in HARD_EXCLUDE_DIRS]

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            if not is_text_doc(full):
                continue

            rel      = os.path.relpath(full, repo_root)
            rel_low  = rel.lower().replace("\\", "/")
            base_low = os.path.basename(rel_low)

            in_docs     = rel_low.startswith("docs/") or "/docs/" in rel_low
            is_readme   = base_low.startswith("readme")
            name_signal = any(base_low.startswith(x) for x in [
                "architecture", "arch", "design", "overview",
                "structure", "documentation",
            ])

            if is_readme or in_docs or name_signal:
                result.append(full)

    result.sort(key=lambda p: os.path.relpath(p, repo_root).lower())
    return result


# ===============================
# FILE READING + PARAGRAPH SPLITTING
# ===============================

def read_text_file(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, OSError):
            continue
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def split_paragraphs(text: str) -> List[str]:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p.strip() for p in re.split(r"\n\s*\n", t) if len(p.strip()) >= 20]


# ===============================
# LANGUAGE GATE
# ===============================

EN_STOPWORDS = {"the", "and", "is", "to", "of", "in", "for", "with", "on", "as", "are", "be"}


def detect_language(paragraph: str) -> str:
    """
    Returns 'en' or 'non_en'.

    Patched heuristic for technical English:
      - ASCII ratio >= 0.80
      - at least 3 alphabetic tokens
      - English if:
          (stopword hit >= 1) OR (alphabetic ratio >= 0.55)
    """
    s = paragraph.strip()
    if not s:
        return "non_en"

    ascii_chars = sum(1 for ch in s if ord(ch) < 128)
    if ascii_chars / max(1, len(s)) < 0.80:
        return "non_en"

    tokens = re.findall(r"[a-zA-Z']+", s.lower())
    if len(tokens) < 3:
        return "non_en"

    stop_hit = sum(1 for t in tokens if t in EN_STOPWORDS)
    alpha_ratio = sum(c.isalpha() for c in s) / max(1, len(s))

    if stop_hit >= 1 or alpha_ratio >= 0.55:
        return "en"

    return "non_en"


# ===============================
# RULE ENGINE
# ===============================

def compute_rule_fields(text: str, rel_path: str) -> Dict[str, object]:
    tnorm = norm_text(text)

    style_hits = find_hits(tnorm, STYLE_PATTERNS)
    noun_hits  = find_hits(tnorm, NOUN_PATTERNS)
    rel_hits   = find_hits(tnorm, REL_PATTERNS)

    has_style = 1 if style_hits else 0
    has_noun  = 1 if noun_hits  else 0
    has_rel   = 1 if rel_hits   else 0

    arch_hit = 1 if (has_style or has_noun or (has_rel and has_noun)) else 0

    arch_hits_parts = []
    if style_hits: arch_hits_parts.append("style:" + "|".join(style_hits))
    if noun_hits:  arch_hits_parts.append("noun:"  + "|".join(noun_hits))
    if rel_hits:   arch_hits_parts.append("rel:"   + "|".join(rel_hits))
    arch_hits_str = "; ".join(arch_hits_parts)

    strong_hits = find_hits(tnorm, NORM_STRONG_PATTERNS)
    weak_hits   = find_hits(tnorm, NORM_WEAK_PATTERNS)
    norm_hit    = 1 if (strong_hits or weak_hits) else 0

    norm_strength = ""
    if weak_hits:
        norm_strength = "weak"
    if strong_hits:
        norm_strength = "strong"

    norm_hits_str = "|".join(strong_hits + weak_hits)

    excl_topic_hits  = find_hits(tnorm, EXCL_PATTERNS)
    excl_path_hits   = looks_like_excluded_artifact(rel_path)
    excl_hits_all    = excl_topic_hits + excl_path_hits
    exclusion_hit    = 1 if excl_hits_all else 0
    excl_hits_str    = "|".join(excl_hits_all)

    override_hits     = find_hits(tnorm, OVERRIDE_PATTERNS)
    override_hit      = 1 if override_hits else 0
    override_hits_str = "|".join(override_hits)

    excluded = 1 if (exclusion_hit and not override_hit) else 0

    return {
        "arch_hit":            arch_hit,
        "has_style_phrase":    has_style,
        "has_structural_noun": has_noun,
        "has_relation_verb":   has_rel,
        "norm_hit":            norm_hit,
        "norm_strength":       norm_strength,
        "excluded":            excluded,
        "norm_hits":           norm_hits_str,
        "arch_hits":           arch_hits_str,
        "excl_hits":           excl_hits_str,
        "override_hits":       override_hits_str,
    }


def route_candidate_type(arch_hit: int, norm_hit: int, excluded: int) -> Optional[str]:
    if norm_hit == 1 and excluded == 1:
        return "excluded_normative"
    if norm_hit == 1 and arch_hit == 1 and excluded == 0:
        return "explicit_candidate"
    if norm_hit == 0 and arch_hit == 1:
        return "arch_description"
    if norm_hit == 1 and arch_hit == 0 and excluded == 0:
        return "excluded_normative"
    return None


# ===============================
# CSV HELPERS
# ===============================

def open_csv_writer(path: str, columns: List[str]) -> Tuple[csv.DictWriter, object]:
    f = open(path, "w", encoding="utf-8-sig", newline="")
    f.write("sep=,\n")
    writer = csv.DictWriter(
        f,
        fieldnames=columns,
        delimiter=",",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    return writer, f


def make_base_row(run_id: str, timestamp: str, repo: Dict,
                  rel_path: str, idx: int, para: str, lang: str) -> Dict:
    return {
        "run_id":              run_id,
        "timestamp_utc":       timestamp,
        "repo_id":             repo["repo_id"],
        "source":              repo["source"],
        "repo_origin_name":    repo["repo_origin_name"],
        "artifact_path":       rel_path,
        "paragraph_index":     idx,
        "lang":                lang,
        "candidate_type":      "",
        "arch_hit":            "",
        "has_style_phrase":    "",
        "has_structural_noun": "",
        "has_relation_verb":   "",
        "norm_hit":            "",
        "norm_strength":       "",
        "excluded":            "",
        "norm_hits":           "",
        "arch_hits":           "",
        "excl_hits":           "",
        "override_hits":       "",
        "text":                sanitize_for_csv_cell(para),
    }


def make_annotation_row(base_row: Dict) -> Dict:
    row = dict(base_row)
    for col in ANNOTATION_EXTRA:
        row[col] = ""
    return row


# ===============================
# MAIN
# ===============================

def main():
    parser = argparse.ArgumentParser(
        description="Mine architectural constraint candidates from local OSS dataset."
    )
    parser.add_argument("--dataset_root", required=True,
                        help="Root folder containing gh_* and sf_* repo folders.")
    parser.add_argument("--out_dir",      required=True,
                        help="Output folder for CSV files.")
    parser.add_argument("--log_dir",      required=True,
                        help="Folder for run logs.")
    parser.add_argument("--run_id",       required=False,
                        help="Optional run identifier (UUID auto-generated if omitted).")
    parser.add_argument("--max_repos",    type=int, default=0,
                        help="Process only first N repos (0 = all). Useful for testing.")
    parser.add_argument("--gh_mapping_csv", required=False,
                        help="Mapping CSV for GitHub repo_id (gh_XXX) -> repo_name (e.g., owner/repo). "
                             "Deterministic schema: columns repo_id, repo_name. "
                             "If omitted, uses <dataset_root>/repos.csv if present.")
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    ensure_dir(args.log_dir)

    run_id    = args.run_id or str(uuid.uuid4())
    timestamp = utc_now_iso()

    print(f"Run ID:       {run_id}")
    print(f"Timestamp:    {timestamp}")
    print(f"Dataset root: {args.dataset_root}")

    # Load mappings
    mapping_path = os.path.join(args.dataset_root, "sf100_mapping.csv")
    sf_mapping   = load_sf100_mapping(mapping_path)

    gh_path = args.gh_mapping_csv
    if not gh_path:
        default_repos_csv = os.path.join(args.dataset_root, "repos.csv")
        if os.path.isfile(default_repos_csv):
            gh_path = default_repos_csv
            print(f"[info] Using default GitHub mapping: {gh_path}")
        else:
            print("[warn] No --gh_mapping_csv provided and repos.csv not found; GitHub repo_origin_name will be empty.",
                  file=sys.stderr)
            gh_path = None

    gh_mapping = load_gh_mapping(gh_path) if gh_path else {}

    repos = scan_repos(args.dataset_root, sf_mapping, gh_mapping)

    if args.max_repos > 0:
        repos = repos[:args.max_repos]

    n_gh = sum(1 for r in repos if r["source"] == "github")
    n_sf = sum(1 for r in repos if r["source"] == "sf100")
    print(f"Repos found:  {len(repos)} (GitHub={n_gh}, SF100={n_sf})")

    # Open output CSVs
    cand_writer, cand_f = open_csv_writer(os.path.join(args.out_dir, "candidates.csv"), CSV_COLUMNS)
    arch_writer, arch_f = open_csv_writer(os.path.join(args.out_dir, "arch_descriptions.csv"), CSV_COLUMNS)
    excl_writer, excl_f = open_csv_writer(os.path.join(args.out_dir, "excluded_normative.csv"), CSV_COLUMNS)
    ann_writer,  ann_f  = open_csv_writer(os.path.join(args.out_dir, "annotation.csv"), ANNOTATION_COLUMNS)

    # Write run log
    runlog_path = os.path.join(args.log_dir, f"run_{run_id}.log")
    with open(runlog_path, "w", encoding="utf-8") as lf:
        lf.write(
            f"run_id={run_id}\n"
            f"timestamp_utc={timestamp}\n"
            f"dataset_root={args.dataset_root}\n"
            f"out_dir={args.out_dir}\n"
            f"log_dir={args.log_dir}\n"
            f"gh_mapping_csv={(gh_path or '')}\n"
            f"repos={len(repos)}\n"
        )

    stats = {k: 0 for k in [
        "explicit_candidate", "arch_description", "excluded_normative",
        "non_english", "non_natural_language",
        "skipped_other", "files_scanned", "paragraphs_seen",
    ]}

    try:
        for repo in repos:
            doc_files = collect_doc_files(repo["repo_root"])
            stats["files_scanned"] += len(doc_files)

            for fp in doc_files:
                rel_path = os.path.relpath(fp, repo["repo_root"])
                raw      = read_text_file(fp)
                if not raw:
                    continue

                for idx, para in enumerate(split_paragraphs(raw)):
                    stats["paragraphs_seen"] += 1

                    # 1) Detect code/config FIRST to avoid inflating non_english
                    if looks_like_code_or_config(para):
                        base_row = make_base_row(run_id, timestamp, repo, rel_path, idx, para, lang="n/a")
                        base_row["candidate_type"] = "non_natural_language"
                        ann_writer.writerow(make_annotation_row(base_row))
                        stats["non_natural_language"] += 1
                        continue

                    # 2) Then language gate
                    lang = detect_language(para)
                    base_row = make_base_row(run_id, timestamp, repo, rel_path, idx, para, lang)

                    if lang != "en":
                        base_row["candidate_type"] = "non_english"
                        ann_writer.writerow(make_annotation_row(base_row))
                        stats["non_english"] += 1
                        continue

                    fields = compute_rule_fields(para, rel_path)
                    base_row.update(fields)

                    ctype = route_candidate_type(
                        arch_hit=int(fields["arch_hit"]),
                        norm_hit=int(fields["norm_hit"]),
                        excluded=int(fields["excluded"]),
                    )

                    if ctype is None:
                        stats["skipped_other"] += 1
                        continue

                    base_row["candidate_type"] = ctype
                    ann_writer.writerow(make_annotation_row(base_row))

                    if ctype == "explicit_candidate":
                        cand_writer.writerow(base_row)
                        stats["explicit_candidate"] += 1
                    elif ctype == "arch_description":
                        arch_writer.writerow(base_row)
                        stats["arch_description"] += 1
                    elif ctype == "excluded_normative":
                        excl_writer.writerow(base_row)
                        stats["excluded_normative"] += 1

        print("\nDone.")
        print("─" * 42)
        for k, v in stats.items():
            print(f"  {k:<26} {v}")

        with open(runlog_path, "a", encoding="utf-8") as lf:
            for k, v in stats.items():
                lf.write(f"{k}={v}\n")

    finally:
        for f in (cand_f, arch_f, excl_f, ann_f):
            f.close()


if __name__ == "__main__":
    main()