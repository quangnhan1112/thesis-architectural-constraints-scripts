library(readr)
library(dplyr)
library(stringr)
library(gridExtra)
library(grid)

ann_path <- "D:/Desktop/thesis_dataset/_outputs_test/annotation.csv"
out_png  <- "D:/Desktop/analysis/figures/table_explicit_candidates_per_repo.png"

cols <- c(
  "run_id","timestamp_utc","repo_id","source","repo_origin_name",
  "artifact_path","paragraph_index","lang","candidate_type",
  "arch_hit","has_style_phrase","has_structural_noun","has_relation_verb",
  "norm_hit","norm_strength","excluded","norm_hits","arch_hits","excl_hits",
  "override_hits","text",
  "label","constraint_type","norm_strength_review","notes","verified"
)

# READ: comma-delimited, skip the first line "sep=,"
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
  ) %>%
  mutate(
    source = case_when(
      str_detect(source, "git") ~ "github",
      str_detect(source, "sf")  ~ "sf100",
      TRUE ~ source
    )
  )

# Universe of repos with docs
repo_universe <- df %>% distinct(repo_id, source)

# Explicit candidates per repo
explicit_by_repo <- df %>%
  filter(candidate_type == "explicit_candidate") %>%
  count(repo_id, name = "n_explicit")

repo_level <- repo_universe %>%
  left_join(explicit_by_repo, by = "repo_id") %>%
  mutate(n_explicit = ifelse(is.na(n_explicit), 0L, n_explicit))

# Summary per source + overall
summary_by_source <- repo_level %>%
  group_by(source) %>%
  summarise(
    N = n(),
    Mean = mean(n_explicit),
    Median = median(n_explicit),
    pct_ge_1 = sum(n_explicit >= 1) / N * 100,
    .groups = "drop"
  )

summary_overall <- repo_level %>%
  summarise(
    source = "overall",
    N = n(),
    Mean = mean(n_explicit),
    Median = median(n_explicit),
    pct_ge_1 = sum(n_explicit >= 1) / N * 100
  )

table2 <- bind_rows(summary_by_source, summary_overall) %>%
  mutate(
    Source = case_when(
      source == "github" ~ "GitHub",
      source == "sf100"  ~ "SF100",
      source == "overall" ~ "Overall",
      TRUE ~ source
    ),
    Mean = round(Mean, 2),
    Median = round(Median, 0),
    `Repos >=1 (%)` = round(pct_ge_1, 1)
  ) %>%
  select(Source, N, Mean, Median, `Repos >=1 (%)`)

png(filename = out_png, width = 1800, height = 650, res = 300)
grid.newpage()
grid.draw(tableGrob(table2, rows = NULL))
dev.off()

print(table2)