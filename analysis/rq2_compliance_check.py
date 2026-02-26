"""
rq2_compliance_check.py
=======================
Compliance analysis script for RQ2.
Checks 10 atomic architectural constraints from gh_031 against source code.

Constraints checked:
  C1  [Layering]    Stateless API layer: audit persistence separated from runtime
  C2  [Dependency]  Fuzzy matching index isolated from transactional systems
  C3  [Dependency]  Domain layer must be framework/infrastructure independent
  C4  [Dependency]  Application layer depends on domain ports, not infrastructure adapters
  C5  [Modular]     Infrastructure adapters explicitly named and isolated
  C6  [Modular]     Domain events use explicit event naming (Event suffix)
  C7  [Modular]     Banking service naming bounded-context aligned (BIAN suffixes)
  C8  [Interface]   Each bounded context service must publish an OpenAPI contract
  C9  [Dependency]  Shared libraries remain code-level only (no shared persistence)
  C10 [Interface]   Cross-context access via explicit OpenAPI contracts and event topics

Usage:
    python rq2_compliance_check.py --repo_root "D:\\Desktop\\analysis\\rq2"
    
Output:
    D:\\Desktop\\analysis\\rq2_compliance_results.csv
    D:\\Desktop\\analysis\\rq2_violations_detail.csv
"""

import os
import re
import csv
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


# =========================
# CONFIG
# =========================

# C3: Forbidden imports in domain packages
DOMAIN_FORBIDDEN_IMPORTS = [
    r"jakarta\.persistence\.",
    r"javax\.persistence\.",
    r"org\.springframework\.",
    r"org\.hibernate\.",
    r"java\.sql\.",
    r"\.infrastructure\.",
]

# C4: Forbidden imports in application packages
APP_FORBIDDEN_IMPORTS = [
    r"\.infrastructure\.",
]

# C5: Required suffixes for adapter classes
ADAPTER_SUFFIXES = [
    "Adapter", "Controller", "Repository", "Client",
    "Publisher", "Listener", "Mapper", "Config"
]

# C5: Exclusions for DTO-like types that may live under adapter packages
DTO_LIKE_SUFFIXES = [
    "Dto", "DTO", "Request", "Response", "Command", "Query", "Payload"
]

# C7: Exclusions for non-service types that may live under *service* packages
C7_EXCLUDED_SUFFIXES = [
    "Policy", "Validator", "Exception", "Test", "IT", "Spec"
]

# C7: Scope control — by default, only enforce suffixes in application service packages
C7_ENFORCE_ONLY_APPLICATION_SERVICES = True

# C6: Domain event classes must end with "Event"
# checked in *.domain.event.* or *.domain.events.* packages

# C7: Service classes must end with BIAN-style suffixes
SERVICE_SUFFIXES = ["Service", "ServiceDomain", "Saga", "Orchestrator"]

# C8: Expected OpenAPI files per bounded context
EXPECTED_OPENAPI_FILES = [
    "open-finance-context.yaml",
    "payment-context.yaml",
    "loan-context.yaml",
    "risk-context.yaml",
    "customer-context.yaml",
    "compliance-context.yaml",
]

# C9: Forbidden persistence imports in shared-kernel / common-domain
SHARED_KERNEL_FORBIDDEN = [
    r"jakarta\.persistence\.",
    r"javax\.persistence\.",
    r"org\.springframework\.data\.",
    r"org\.hibernate\.",
    r"java\.sql\.",
]

# C10: Cross-context direct class imports (heuristic)
# Flag if a bounded context imports another bounded context's non-port package
BOUNDED_CONTEXT_PACKAGES = [
    "openfinance", "payment", "loan", "risk", "customer", "compliance"
]


# =========================
# HELPERS
# =========================

def find_java_files(root: str) -> List[Path]:
    return list(Path(root).rglob("*.java"))


def read_file(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def get_package(content: str) -> str:
    m = re.search(r"^\s*package\s+([\w.]+)\s*;", content, re.MULTILINE)
    return m.group(1) if m else ""


def get_imports(content: str) -> List[str]:
    return re.findall(r"^\s*import\s+([\w.*]+)\s*;", content, re.MULTILINE)


def get_classname(path: Path) -> str:
    return path.stem


def path_contains(path: Path, segment: str) -> bool:
    parts = [p.lower() for p in path.parts]
    return segment.lower() in parts


def is_domain_package(pkg: str) -> bool:
    return ".domain." in pkg or pkg.endswith(".domain")


def is_application_package(pkg: str) -> bool:
    return ".application." in pkg or pkg.endswith(".application")


def is_adapter_package(pkg: str) -> bool:
    return ".infrastructure.adapter." in pkg or ".infrastructure.adapter" in pkg



def is_test_path(path: Path) -> bool:
    p = str(path).lower().replace("\\", "/")
    return "/src/test/" in p or p.endswith("test.java") or "/test/" in p


def is_dto_package(pkg: str) -> bool:
    return ".dto." in pkg or pkg.endswith(".dto") or ".model." in pkg or pkg.endswith(".model")


def is_dto_like_classname(classname: str) -> bool:
    return any(classname.endswith(s) for s in DTO_LIKE_SUFFIXES)


def is_excluded_c7_classname(classname: str) -> bool:
    return any(classname.endswith(s) for s in C7_EXCLUDED_SUFFIXES)


def is_application_service_package(pkg: str) -> bool:
    return ".application.service" in pkg or pkg.endswith(".application.service")

def is_domain_event_package(pkg: str) -> bool:
    return ".domain.event." in pkg or ".domain.event" in pkg \
        or ".domain.events." in pkg or ".domain.events" in pkg


def is_service_package(pkg: str) -> bool:
    return ((".application.service" in pkg) or
            (".domain.service" in pkg) or
            pkg.endswith(".service"))


def is_shared_kernel(path: Path) -> bool:
    p = str(path).lower().replace("\\", "/")
    return "shared-kernel" in p or "shared_kernel" in p or \
           "common-domain" in p or "common_domain" in p


def is_uc03_infrastructure(path: Path) -> bool:
    p = str(path).lower().replace("\\", "/")
    return "uc03" in p and "infrastructure" in p


def is_uc03_domain_or_app(path: Path) -> bool:
    p = str(path).lower().replace("\\", "/")
    return "uc03" in p and ("domain" in p or "application" in p)


# =========================
# CONSTRAINT CHECKS
# =========================

def check_c1_c2(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C1: Stateless API layer — audit persistence separated from runtime.
        Check: UC03 infrastructure has separate audit and matching packages.
    C2: Fuzzy matching index isolated from transactional systems.
        Check: UC03 matching package does not import persistence packages.
    """
    results = {}
    violations = []

    uc03_infra = Path(repo_root) / "open-finance-context" / "open-finance-infrastructure" / \
                 "src" / "main" / "java"

    # C1: Check audit and cache/matching are in separate packages
    audit_pkg = False
    cache_pkg = False
    matching_pkg = False

    for d in uc03_infra.rglob("*"):
        if not d.is_dir():
            continue
        name = d.name.lower()
        parts = [p.lower() for p in d.parts]
        if "uc03" in parts:
            if name == "audit":
                audit_pkg = True
            if name == "cache":
                cache_pkg = True
            if name == "matching":
                matching_pkg = True

    c1_compliant = audit_pkg and cache_pkg
    results["C1"] = {
        "constraint": "Stateless API layer: audit persistence separated from runtime",
        "method": "Package separation check (UC03 audit vs cache packages)",
        "compliant": c1_compliant,
        "detail": f"audit_pkg={audit_pkg}, cache_pkg={cache_pkg}"
    }
    if not c1_compliant:
        violations.append({
            "constraint_id": "C1",
            "file": "open-finance-context/open-finance-infrastructure/.../uc03",
            "issue": "Expected separate audit and cache packages under UC03 infrastructure"
        })

    # C2: Fuzzy matching (uc03/infrastructure/matching) should not import persistence
    c2_violations = []
    for jf in find_java_files(repo_root):
        p = str(jf).lower().replace("\\", "/")
        if "uc03" not in p or "matching" not in p:
            continue
        content = read_file(jf)
        imports = get_imports(content)
        for imp in imports:
            if re.search(r"(persistence|jpa|hibernate|jdbc|sql)", imp.lower()):
                c2_violations.append({
                    "constraint_id": "C2",
                    "file": str(jf),
                    "issue": f"Matching package imports persistence: {imp}"
                })

    results["C2"] = {
        "constraint": "Fuzzy matching index isolated from transactional systems",
        "method": "Import scan: UC03 matching package must not import persistence",
        "compliant": len(c2_violations) == 0,
        "detail": f"{len(c2_violations)} violation(s) found"
    }
    violations.extend(c2_violations)
    return results, violations


def check_c3(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C3: Domain layer must be framework/infrastructure independent.
        Check: No forbidden imports in *.domain.* packages.
    """
    violations = []
    patterns = [re.compile(p) for p in DOMAIN_FORBIDDEN_IMPORTS]

    for jf in find_java_files(repo_root):
        content = read_file(jf)
        pkg = get_package(content)
        if not is_domain_package(pkg):
            continue
        imports = get_imports(content)
        for imp in imports:
            for pat in patterns:
                if pat.search(imp):
                    violations.append({
                        "constraint_id": "C3",
                        "file": str(jf),
                        "issue": f"Domain imports forbidden dependency: {imp}"
                    })
                    break

    return {
        "C3": {
            "constraint": "Domain layer must be framework/infrastructure independent",
            "method": "Import scan: forbidden imports in *.domain.* packages",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c4(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C4: Application layer depends on domain ports, not infrastructure adapters.
        Check: No *.infrastructure.* imports in *.application.* packages.
    """
    violations = []
    patterns = [re.compile(p) for p in APP_FORBIDDEN_IMPORTS]

    for jf in find_java_files(repo_root):
        content = read_file(jf)
        pkg = get_package(content)
        if not is_application_package(pkg):
            continue
        imports = get_imports(content)
        for imp in imports:
            for pat in patterns:
                if pat.search(imp):
                    violations.append({
                        "constraint_id": "C4",
                        "file": str(jf),
                        "issue": f"Application imports infrastructure: {imp}"
                    })
                    break

    return {
        "C4": {
            "constraint": "Application layer depends on domain ports, not infrastructure adapters",
            "method": "Import scan: *.infrastructure.* forbidden in *.application.* packages",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c5(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C5: Infrastructure adapters explicitly named and isolated.
        Check: Classes under *.infrastructure.adapter.* must end with allowed suffixes.
    """
    violations = []

    for jf in find_java_files(repo_root):
        # Ignore tests
        if is_test_path(jf):
            continue

        content = read_file(jf)
        pkg = get_package(content)
        if not is_adapter_package(pkg):
            continue

        classname = get_classname(jf)

        # DTOs / payload types are often placed under adapter modules but are not adapter implementations.
        # Treat these as non-violations to avoid over-enforcement.
        if is_dto_package(pkg) or is_dto_like_classname(classname):
            continue

        if not any(classname.endswith(s) for s in ADAPTER_SUFFIXES):
            violations.append({
                "constraint_id": "C5",
                "file": str(jf),
                "issue": f"Adapter class '{classname}' does not end with required suffix"
            })

    return {
        "C5": {
            "constraint": "Infrastructure adapters explicitly named and isolated",
            "method": "Naming check: classes in *.infrastructure.adapter.* must use allowed suffixes",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c6(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C6: Domain events use explicit event naming (Event suffix).
        Check: Classes under *.domain.event(s).* must end with 'Event'.
    """
    violations = []

    for jf in find_java_files(repo_root):
        content = read_file(jf)
        pkg = get_package(content)
        if not is_domain_event_package(pkg):
            continue
        classname = get_classname(jf)
        if not classname.endswith("Event"):
            violations.append({
                "constraint_id": "C6",
                "file": str(jf),
                "issue": f"Domain event class '{classname}' does not end with 'Event'"
            })

    return {
        "C6": {
            "constraint": "Domain events use explicit event naming (Event suffix)",
            "method": "Naming check: classes in *.domain.event(s).* must end with 'Event'",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c7(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C7: Banking service naming bounded-context aligned (BIAN suffixes).
        Check: Classes in service packages must end with allowed BIAN suffixes.
    """
    violations = []

    for jf in find_java_files(repo_root):
        # Ignore tests
        if is_test_path(jf):
            continue

        content = read_file(jf)
        pkg = get_package(content)

        # Scope control: in most hexagonal setups, naming conventions for *services* apply to the
        # application service layer, not to domain policies/validators/exceptions.
        if C7_ENFORCE_ONLY_APPLICATION_SERVICES:
            if not is_application_service_package(pkg):
                continue
        else:
            if not is_service_package(pkg):
                continue

        classname = get_classname(jf)

        # Exclude non-service concepts that may live in *service* packages (common false positives)
        if is_excluded_c7_classname(classname):
            continue

        if not any(classname.endswith(s) for s in SERVICE_SUFFIXES):
            violations.append({
                "constraint_id": "C7",
                "file": str(jf),
                "issue": f"Service class '{classname}' does not end with BIAN suffix"
            })

    return {
        "C7": {
            "constraint": "Banking service naming bounded-context aligned (BIAN suffixes)",
            "method": "Naming check: classes in service packages must use BIAN suffixes",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c8(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C8: Each bounded context service must publish an OpenAPI contract.
        Check: Expected YAML files exist in api/openapi/.
    """
    violations = []
    openapi_dir = Path(repo_root) / "api" / "openapi"

    existing = {f.name for f in openapi_dir.glob("*.yaml")} if openapi_dir.exists() else set()

    for expected in EXPECTED_OPENAPI_FILES:
        if expected not in existing:
            violations.append({
                "constraint_id": "C8",
                "file": str(openapi_dir / expected),
                "issue": f"Missing OpenAPI contract file: {expected}"
            })

    return {
        "C8": {
            "constraint": "Each bounded context service must publish an OpenAPI contract",
            "method": "File existence check: api/openapi/<context>.yaml",
            "compliant": len(violations) == 0,
            "detail": f"{len(existing)} files found; {len(violations)} missing"
        }
    }, violations


def check_c9(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C9: Shared libraries remain code-level only (no shared persistence).
        Check: No persistence imports in shared-kernel or common-domain.
    """
    violations = []
    patterns = [re.compile(p) for p in SHARED_KERNEL_FORBIDDEN]

    for jf in find_java_files(repo_root):
        if not is_shared_kernel(jf):
            continue
        content = read_file(jf)
        imports = get_imports(content)
        for imp in imports:
            for pat in patterns:
                if pat.search(imp):
                    violations.append({
                        "constraint_id": "C9",
                        "file": str(jf),
                        "issue": f"Shared kernel imports persistence: {imp}"
                    })
                    break

    return {
        "C9": {
            "constraint": "Shared libraries remain code-level only (no shared persistence)",
            "method": "Import scan: persistence imports forbidden in shared-kernel/common-domain",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


def check_c10(repo_root: str) -> Tuple[Dict, List[Dict]]:
    """
    C10: Cross-context access via explicit OpenAPI contracts and event topics.
         Heuristic: Flag direct imports of another bounded context's non-port package.
    """
    violations = []

    ctx_map = {
        "openfinance": ["com.enterprise.openfinance", "com.bank.openfinance"],
        "payment":     ["com.bank.payment"],
        "loan":        ["com.bank.loan"],
        "risk":        ["com.amanahfi.risk", "com.bank.risk"],
        "customer":    ["com.bank.customer"],
        "compliance":  ["com.amanahfi.compliance", "com.bank.compliance"],
    }

    for jf in find_java_files(repo_root):
        content = read_file(jf)
        pkg = get_package(content)
        if not pkg:
            continue

        # Determine which context this file belongs to
        own_ctx = None
        for ctx, prefixes in ctx_map.items():
            if any(pkg.startswith(p) for p in prefixes):
                own_ctx = ctx
                break
        if own_ctx is None:
            continue

        imports = get_imports(content)
        for imp in imports:
            for ctx, prefixes in ctx_map.items():
                if ctx == own_ctx:
                    continue
                for prefix in prefixes:
                    if imp.startswith(prefix):
                        # Allow port imports (cross-context via port is OK)
                        if ".port." in imp or ".api." in imp:
                            continue
                        violations.append({
                            "constraint_id": "C10",
                            "file": str(jf),
                            "issue": f"Direct cross-context import from '{ctx}': {imp}"
                        })

    return {
        "C10": {
            "constraint": "Cross-context access via explicit OpenAPI contracts and event topics",
            "method": "Import scan: direct cross-context imports (non-port) flagged as violations",
            "compliant": len(violations) == 0,
            "detail": f"{len(violations)} violation(s) found"
        }
    }, violations


# =========================
# MAIN
# =========================

def main():
    parser = argparse.ArgumentParser(description="RQ2 Compliance Analysis")
    parser.add_argument("--repo_root", required=True,
                        help="Root of the cloned repository")
    args = parser.parse_args()

    repo_root = args.repo_root
    out_dir = os.path.dirname(repo_root)
    summary_path = os.path.join(out_dir, "rq2_compliance_results.csv")
    detail_path  = os.path.join(out_dir, "rq2_violations_detail.csv")

    print(f"Repo root : {repo_root}")
    print(f"Scanning {len(find_java_files(repo_root))} Java files...\n")

    all_results = {}
    all_violations = []

    # Run all checks
    for check_fn in [check_c1_c2, check_c3, check_c4, check_c5,
                     check_c6, check_c7, check_c8, check_c9, check_c10]:
        res, viols = check_fn(repo_root)
        all_results.update(res)
        all_violations.extend(viols)

    # Print summary
    print("=" * 60)
    print(f"{'ID':<5} {'Compliant':<10} {'Detail'}")
    print("=" * 60)
    for cid in sorted(all_results.keys()):
        r = all_results[cid]
        status = "YES" if r["compliant"] else "NO"
        print(f"{cid:<5} {status:<10} {r['detail']}")
    print("=" * 60)
    compliant_count = sum(1 for r in all_results.values() if r["compliant"])
    print(f"Compliant: {compliant_count}/{len(all_results)}")
    print(f"Total violations: {len(all_violations)}")

    # Write summary CSV
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("sep=,\n")
        writer = csv.DictWriter(f, fieldnames=[
            "constraint_id", "constraint", "method", "compliant", "detail"
        ], quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for cid in sorted(all_results.keys()):
            r = all_results[cid]
            writer.writerow({
                "constraint_id": cid,
                "constraint": r["constraint"],
                "method": r["method"],
                "compliant": "yes" if r["compliant"] else "no",
                "detail": r["detail"]
            })

    # Write violations CSV
    with open(detail_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("sep=,\n")
        writer = csv.DictWriter(f, fieldnames=[
            "constraint_id", "file", "issue"
        ], quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for v in all_violations:
            writer.writerow(v)

    print(f"\nSummary  -> {summary_path}")
    print(f"Violations -> {detail_path}")


if __name__ == "__main__":
    main()
