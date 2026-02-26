"""
GitHub Documentation Downloader v0.3.0
=====================================
- Reads an Excel file containing a column named 'url' with GitHub repo URLs
- Deduplicates repos by URL
- Downloads README + documentation directories (recursive) via GitHub Contents API
- Stores artifacts locally under: OUTPUT_ROOT\<repo_id>\
- Writes repos.csv with retrieval + artifact metadata

Requirements:
  pip install pandas requests openpyxl

Notes:
- GITHUB_TOKEN can be left empty (anonymous). Rate limits will be stricter.
- Set OUTPUT_ROOT to your desired folder (Windows path supported).
"""

import os
import re
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests
import pandas as pd

# ─── CONFIG ───────────────────────────────────────────────────────────────────

EXCEL_PATH   = "filtered_github_repos_java.csv"   # must contain a 'url' column
OUTPUT_ROOT  = Path(r"D:\Desktop\github_filter\github_document")   # <- your target folder
REPOS_CSV    = OUTPUT_ROOT / "repos.csv"

SCRIPT_VERSION = "v0.3.0"
RUN_ID         = hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
TS_UTC         = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Leave empty if you want anonymous access
GITHUB_TOKEN = "" 

API_BASE = "https://api.github.com"

API_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "thesis-doc-downloader/0.3.0",
}
if GITHUB_TOKEN.strip():
    API_HEADERS["Authorization"] = f"token {GITHUB_TOKEN.strip()}"

RAW_HEADERS = {"User-Agent": "thesis-doc-downloader/0.3.0"}

# candidate doc directory names (we collect ALL that exist, not only the first)
DOCS_DIR_CANDIDATES = ["docs", "doc", "documentation"]

# file extensions to download from docs directories
DOCS_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".html"}

# optional: also download these well-known top-level doc files if present
TOPLEVEL_DOC_FILENAMES = {
    "ARCHITECTURE.md", "ARCHITECTURE.MD",
    "DESIGN.md", "DESIGN.MD",
    "DESIGN_DOC.md", "HLD.md", "OVERVIEW.md",
}

# polite delay between API calls (seconds)
API_DELAY = 0.35

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def parse_owner_repo(url: str):
    url = (url or "").strip().rstrip("/")
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if not m:
        return None, None
    return m.group(1), m.group(2)

def safe_request_get(url: str):
    """
    GET request with basic rate-limit handling.
    If rate-limited, waits until reset (if provided) or 60s fallback.
    """
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=20)
    except requests.RequestException as e:
        return None, f"request_error: {e}"

    # Handle rate limit
    if r.status_code in (403, 429):
        reset = r.headers.get("X-RateLimit-Reset")
        remaining = r.headers.get("X-RateLimit-Remaining")
        # If GitHub tells us when it resets, wait until then (+2s)
        if reset and (remaining == "0" or remaining is None):
            try:
                reset_ts = int(reset)
                now_ts = int(time.time())
                wait_s = max(0, reset_ts - now_ts) + 2
                print(f"  [RATE LIMIT] sleeping {wait_s}s until reset...")
                time.sleep(wait_s)
                r = requests.get(url, headers=API_HEADERS, timeout=20)
            except Exception:
                print("  [RATE LIMIT] sleeping 60s (fallback)...")
                time.sleep(60)
                r = requests.get(url, headers=API_HEADERS, timeout=20)
        else:
            print("  [RATE LIMIT] sleeping 60s (fallback)...")
            time.sleep(60)
            r = requests.get(url, headers=API_HEADERS, timeout=20)

    return r, None

def download_raw_file(raw_url: str, save_path: Path) -> bool:
    try:
        r = requests.get(raw_url, headers=RAW_HEADERS, timeout=30)
        if r.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(r.content)
            return True
    except requests.RequestException:
        pass
    return False

def list_dir_recursive(owner: str, repo: str, path: str):
    """
    Recursively list files under a directory using GitHub Contents API.
    Returns list of dicts for files.
    """
    url = f"{API_BASE}/repos/{owner}/{repo}/contents/{path}"
    r, err = safe_request_get(url)
    time.sleep(API_DELAY)

    if not r or r.status_code != 200:
        return []

    data = r.json()
    if not isinstance(data, list):
        return []

    out = []
    for item in data:
        t = item.get("type")
        if t == "file":
            out.append(item)
        elif t == "dir":
            subpath = item.get("path", "")
            if subpath:
                out.extend(list_dir_recursive(owner, repo, subpath))
    return out

def get_repo_accessible(owner: str, repo: str):
    r, err = safe_request_get(f"{API_BASE}/repos/{owner}/{repo}")
    time.sleep(API_DELAY)
    if not r:
        return False, err or "unknown_error", None
    if r.status_code != 200:
        return False, f"http_{r.status_code}", None
    try:
        return True, None, r.json()
    except Exception:
        return True, None, None

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Output root:      {OUTPUT_ROOT}")
    print(f"Run ID:           {RUN_ID}")
    print(f"Timestamp (UTC):  {TS_UTC}")
    print(f"Script version:   {SCRIPT_VERSION}")
    print()

    print(f"Loading CSV: {EXCEL_PATH}")

    # Read CSV robustly (auto-detect separator)
    df = pd.read_csv(EXCEL_PATH, sep=None, engine="python")

    # Normalize column names
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    if "url" not in df.columns:
        raise ValueError(f"CSV must contain a column named 'url'. Found columns: {list(df.columns)}")

    before = len(df)
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    print(f"Deduplicated: {before} → {len(df)} unique repos\n")

    df["repo_id"] = [f"gh_{str(i+1).zfill(3)}" for i in range(len(df))]

    rows = []

    for i, row in df.iterrows():
        url = str(row["url"]).strip()
        owner, repo = parse_owner_repo(url)
        repo_id = row["repo_id"]

        print(f"[{i+1}/{len(df)}] {repo_id} — {owner}/{repo}" if owner else f"[{i+1}/{len(df)}] {repo_id} — (bad url)")

        record = {
            "repo_id": repo_id,
            "source": "github",
            "repo_url": url,
            "repo_name": f"{owner}/{repo}" if owner else "",
            "local_root": str((OUTPUT_ROOT / repo_id).resolve()),
            "retrieval_ok": 0,
            "docs_found": 0,
            "readme_found": 0,
            "readme_paths": "",
            "docs_dir_found": 0,
            "doc_paths": "",
            "doc_artifact_count": 0,
            "run_id": RUN_ID,
            "processing_timestamp_utc": TS_UTC,
            "script_version": SCRIPT_VERSION,
            "retrieval_error": "",
        }

        if not owner:
            record["retrieval_error"] = "unparseable_url"
            rows.append(record)
            print("  [SKIP] Could not parse GitHub URL\n")
            continue

        ok, err, repo_meta = get_repo_accessible(owner, repo)
        if not ok:
            record["retrieval_error"] = err or "repo_not_accessible"
            rows.append(record)
            print(f"  [FAIL] Repo not accessible: {record['retrieval_error']}\n")
            continue

        record["retrieval_ok"] = 1
        repo_dir = OUTPUT_ROOT / repo_id

        readme_paths = []
        doc_paths = []

        # A) README
        r, _ = safe_request_get(f"{API_BASE}/repos/{owner}/{repo}/readme")
        time.sleep(API_DELAY)
        if r and r.status_code == 200:
            data = r.json()
            raw_url = data.get("download_url", "")
            fname = data.get("name", "README.md")
            save_path = repo_dir / fname
            if raw_url and download_raw_file(raw_url, save_path):
                record["readme_found"] = 1
                readme_paths.append(str(save_path))
                print(f"  ✓ README: {fname}")
        else:
            print("  ✗ No README found")

        # B) Top-level architecture/design docs
        root_listing, _ = safe_request_get(f"{API_BASE}/repos/{owner}/{repo}/contents/")
        time.sleep(API_DELAY)
        if root_listing and root_listing.status_code == 200:
            try:
                items = root_listing.json()
                if isinstance(items, list):
                    by_name = {it.get("name"): it for it in items if it.get("type") == "file"}
                    for name in TOPLEVEL_DOC_FILENAMES:
                        it = by_name.get(name)
                        if it and it.get("download_url"):
                            save_path = repo_dir / name
                            if download_raw_file(it["download_url"], save_path):
                                doc_paths.append(str(save_path))
                                print(f"  ✓ Top-level doc: {name}")
            except Exception:
                pass

                # C) Docs directories
        found_any_docs_dir = False
        MAX_DOC_FILES = 500

        for d in DOCS_DIR_CANDIDATES:
            files = list_dir_recursive(owner, repo, d)

            if not files:
                continue

            if len(files) > MAX_DOC_FILES:
                print(f"  ⚠ Skipping /{d} (too large: {len(files)} files)")
                record["retrieval_error"] = f"docs_dir_too_large_{len(files)}"
                continue

            found_any_docs_dir = True
            print(f"  ✓ /{d} — {len(files)} files (recursive)")

            for f in files:
                fname = f.get("name", "")
                raw_url = f.get("download_url", "")
                if not raw_url:
                    continue

                ext = Path(fname).suffix.lower()
                if ext not in DOCS_EXTENSIONS:
                    continue

                rel_path = f.get("path", fname)
                save_path = repo_dir / rel_path

                if download_raw_file(raw_url, save_path):
                    doc_paths.append(str(save_path))

        

        if found_any_docs_dir:
            record["docs_dir_found"] = 1

        # Finalize
        record["readme_paths"] = ";".join(readme_paths)
        record["doc_paths"] = ";".join(doc_paths)
        record["doc_artifact_count"] = len(readme_paths) + len(doc_paths)
        record["docs_found"] = 1 if record["doc_artifact_count"] > 0 else 0

        print(f"  → docs_found={record['docs_found']}, artifacts={record['doc_artifact_count']}\n")
        rows.append(record)

    out = pd.DataFrame(rows)
    out.to_csv(REPOS_CSV, index=False, encoding="utf-8")

    print(f"✓ Saved: {REPOS_CSV} ({len(out)} rows)")
    print("\n── Summary ─────────────────────────────")
    print(f"Total repos processed : {len(out)}")
    print(f"retrieval_ok = 1      : {int(out['retrieval_ok'].sum())}")
    print(f"docs_found = 1        : {int(out['docs_found'].sum())}")
    print(f"readme_found = 1      : {int(out['readme_found'].sum())}")
    print(f"docs_dir_found = 1    : {int(out['docs_dir_found'].sum())}")
    print(f"\nRun ID: {RUN_ID} | {TS_UTC} | {SCRIPT_VERSION}")

if __name__ == "__main__":
    main()
