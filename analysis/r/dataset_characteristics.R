library(readr)
library(dplyr)
library(ggplot2)
library(gridExtra)
library(grid)
library(stringr)

# =========================
# PATHS
# =========================
ann_path <- "D:/Desktop/thesis_dataset/_outputs_test/annotation.csv"

out_table <- "D:/Desktop/analysis/figures/table_explicit_candidates_per_repo.png"
out_fig   <- "D:/Desktop/analysis/figures/fig_explicit_candidates_per_repo_boxplot.png"

# =========================
# COLUMN SCHEMA (match header)
# =========================
cols <- c(
  "run_id","timestamp_utc","repo_id","source","repo_origin_name",
  "artifact_path","paragraph_index","lang","candidate_type",
  "arch_hit","has_style_phrase","has_structural_noun","has_relation_verb",
  "norm_hit","norm_strength","excluded","norm_hits","arch_hits","excl_hits",
  "override_hits","text",
  "label","constraint_type","norm_strength_review","notes","verified"
)

# =========================
# READ FILE (comma, skip sep=,)
# =========================
df <- read_delim(
  ann_path,
  delim = ",",
  skip = 1,
  col_names = cols,
  show_col_types = FALSE
) %>%
  filter(!(run_id == "run_id")) %>%
  mutate(
    repo_id = as.character(repo_id),
    source = tolower(as.character(source)),
    candidate_type = tolower(coalesce(as.character(candidate_type), ""))
  )

# Normalize source naming
df <- df %>%
  mutate(
    source = case_when(
      str_detect(source, "git") ~ "github",
      str_detect(source, "sf")  ~ "sf100",
      TRUE ~ source
    )
  )

# =========================
# REPO UNIVERSE
# =========================
repo_universe <- df %>%
  distinct(repo_id, source)

# =========================
# COUNT EXPLICIT PER REPO
# =========================
explicit_by_repo <- df %>%
  filter(candidate_type == "explicit_candidate") %>%
  count(repo_id, name = "n_explicit")

repo_level <- repo_universe %>%
  left_join(explicit_by_repo, by = "repo_id") %>%
  mutate(n_explicit = ifelse(is.na(n_explicit), 0L, n_explicit))

# =========================
# SUMMARY STATS
# =========================
summary_by_source <- repo_level %>%
  group_by(source) %>%
  summarise(
    repos_with_docs = n(),
    mean_explicit = mean(n_explicit),
    median_explicit = median(n_explicit),
    repos_ge_1 = sum(n_explicit >= 1),
    pct_repos_ge_1 = repos_ge_1 / repos_with_docs * 100,
    .groups = "drop"
  )

summary_overall <- repo_level %>%
  summarise(
    source = "overall",
    repos_with_docs = n(),
    mean_explicit = mean(n_explicit),
    median_explicit = median(n_explicit),
    repos_ge_1 = sum(n_explicit >= 1),
    pct_repos_ge_1 = repos_ge_1 / repos_with_docs * 100
  )

summary_tbl <- bind_rows(summary_by_source, summary_overall) %>%
  mutate(
    source = case_when(
      source == "github" ~ "GitHub",
      source == "sf100"  ~ "SF100",
      source == "overall" ~ "Overall",
      TRUE ~ source
    ),
    mean_explicit = round(mean_explicit, 2),
    median_explicit = round(median_explicit, 0),
    pct_repos_ge_1 = round(pct_repos_ge_1, 1)
  ) %>%
  select(
    Source = source,
    `Repos with docs (N)` = repos_with_docs,
    `Mean explicit candidates per repo` = mean_explicit,
    `Median explicit candidates per repo` = median_explicit,
    `Repos with ≥1 explicit candidate (n)` = repos_ge_1,
    `Repos with ≥1 explicit candidate (%)` = pct_repos_ge_1
  )

# =========================
# EXPORT TABLE
# =========================
png(filename = out_table, width = 2400, height = 800, res = 300)
grid.newpage()
grid.draw(tableGrob(summary_tbl, rows = NULL))
dev.off()

# =========================
# BOXPLOT
# =========================
repo_level_plot <- repo_level %>%
  mutate(
    Source = case_when(
      source == "github" ~ "GitHub",
      source == "sf100"  ~ "SF100",
      TRUE ~ source
    ),
    log1p_explicit = log10(1 + n_explicit)
  )

p <- ggplot(repo_level_plot, aes(x = Source, y = log1p_explicit)) +
  geom_boxplot() +
  labs(
    x = "Source",
    y = "Explicit candidates per repository (log10(1 + count))"
  )

ggsave(out_fig, plot = p, width = 7, height = 5, dpi = 300)

cat("DONE (7.3.3):\n")
print(summary_tbl)