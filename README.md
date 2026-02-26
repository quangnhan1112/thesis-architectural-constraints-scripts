<<<<<<< HEAD
# Thesis Analysis Scripts
## Explicit Architectural Constraints in Open-Source Software

**Author:** Quang Nhan Le  
**Repository:** Analysis scripts for thesis on architectural constraint detection and compliance in open-source software projects.

---

## Repository Structure

```
thesis-architectural-constraints-scripts/
├── analysis/
│   ├── rq2_compliance_check.py       # RQ2 constraint-level compliance analysis
│   └── r/
│       ├── analyse_7.4.R             # Section 7.4 analysis
│       ├── dataset_characteristics.R # Dataset summary statistics
│       ├── figure_3.R                # Figure 3 generation
│       ├── figure_4.R                # Figure 4 generation
│       ├── figure_5_and_table_2.R    # Figure 5 and Table 2 generation
│       ├── macro_category.R          # Macro-category distribution
│       ├── plot_rq2_compliance_table.R # RQ2 compliance table visualization
│       └── table_1.R                 # Table 1 generation
├── thesis_data/
│   └── _scripts/
│       └── mine_candidates_3.py      # Candidate extraction pipeline (final version)
├── SF100/
│   └── repos_list.txt                # SF100 repository list
└── README.md
```

---

## Scripts

### `thesis_data/_scripts/mine_candidates_3.py`
Candidate extraction pipeline for identifying architectural constraint candidates in documentation artifacts. Applies rule-based extraction with lexical triggers and routes passages to annotation categories.

**Input:** Local documentation artifacts (downloaded via GitHub API)  
**Output:** Structured candidate dataset (CSV)  
**Dependencies:** `pandas`, `re`, `pathlib`

---

### `analysis/rq2_compliance_check.py`
Performs constraint-level compliance analysis for RQ2. Checks 10 atomic architectural constraints against Java source code using import scanning, naming convention checks, and file existence checks.

**Input:** `--repo_root` path to cloned repository  
**Output:** `rq2_compliance_results.csv`, `rq2_violations_detail.csv`  
**Dependencies:** Python 3.x standard library only

```bash
python rq2_compliance_check.py --repo_root "path/to/repo"
```

---

### `analysis/r/*.R`
R scripts for generating figures and tables reported in the thesis. Each script corresponds to a specific figure or table as indicated by the filename.

**Dependencies:** `tidyverse`, `stringr`, `grid`, `gridExtra`

---

### `SF100/repos_list.txt`
List of SF100 repositories included in the dataset.

---

### GitHub Documentation Retrieval
The script used to download documentation artifacts from GitHub repositories (`download_github_docs.py`) is available from the author upon request, as it contains API credentials that have been revoked.

---

## Dependencies

### Python
```
pandas
requests
openpyxl
```

### R
```r
install.packages(c("tidyverse", "stringr", "grid", "gridExtra"))
```

---

## Notes

- Data files (annotation CSVs, downloaded documentation, repository contents) are not included in this repository and are available from the author upon request.
- Scripts were developed and tested on Windows 11 with Python 3.11 and R 4.3.
- `mine_candidates.py` and `mine_candidates_2.py` are earlier development versions and are not included. Only the final version (`mine_candidates_3.py`) is provided.
=======
# thesis-architectural-constraints-scripts
>>>>>>> f322076 (Initial commit)
