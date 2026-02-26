import requests
import pandas as pd
from datetime import datetime, timedelta

# ==============================
# CONFIGURATION
# ==============================

GITHUB_TOKEN = "..................."

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Java-only search
SEARCH_QUERY = "architecture OR design OR layer in:readme language:Java"
SEARCH_URL = "https://api.github.com/search/repositories"

ONE_YEAR_AGO = datetime.utcnow() - timedelta(days=365)

# ==============================
# DATA COLLECTION
# ==============================

results = []
page = 1
MAX_PAGES = 7

print("Starting GitHub Java-only repository filtering...")
print("-----------------------------------------------")

while page <= MAX_PAGES:
    print(f"Processing page {page}...")

    params = {
        "q": SEARCH_QUERY,
        "sort": "updated",
        "order": "desc",
        "per_page": 30,
        "page": page
    }

    response = requests.get(SEARCH_URL, headers=HEADERS, params=params)

    if response.status_code != 200:
        print("GitHub API error:", response.status_code)
        break

    items = response.json().get("items", [])
    print(f"  Repositories fetched: {len(items)}")

    for repo in items:

        # Skip forks
        if repo.get("fork", True):
            continue

        # Ensure primary language is Java
        if repo.get("language") != "Java":
            continue

        # Skip old repositories
        updated_at = datetime.strptime(repo["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
        if updated_at < ONE_YEAR_AGO:
            continue

        # Check contributors (at least 2)
        contributors_url = f"https://api.github.com/repos/{repo['full_name']}/contributors?per_page=2"
        contributors_resp = requests.get(contributors_url, headers=HEADERS)

        if contributors_resp.status_code != 200:
            continue

        contributors = contributors_resp.json()
        if len(contributors) < 2:
            continue

        # Check README
        readme_url = f"https://api.github.com/repos/{repo['full_name']}/readme"
        readme_resp = requests.get(readme_url, headers=HEADERS)
        has_readme = readme_resp.status_code == 200

        # Check Wiki
        has_wiki = repo.get("has_wiki", False)

        if not (has_readme or has_wiki):
            continue

        # Keep repository
        results.append({
            "repository": repo["full_name"],
            "url": repo["html_url"],
            "last_update": repo["updated_at"],
            "language": repo.get("language"),
            "contributors_min_2": True,
            "has_readme": has_readme,
            "has_wiki": has_wiki
        })

        print(f"    ✔ Kept: {repo['full_name']}")

    page += 1

print("-----------------------------------------------")
print("Filtering finished.")

# ==============================
# OUTPUT
# ==============================

df = pd.DataFrame(results)
df.to_csv("filtered_github_repos_java.csv", index=False)

print("DONE.")
print("Java repositories found:", len(df))
print("Output file: filtered_github_repos_java.csv")
