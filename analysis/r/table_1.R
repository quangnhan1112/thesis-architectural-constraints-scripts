library(readr)
library(dplyr)
library(gridExtra)
library(grid)

in_csv  <- "D:/Desktop/analysis/tables/routing_overall.csv"
out_png <- "D:/Desktop/analysis/figures/table_routing_overall.png"

df <- read_csv(in_csv)

total <- df$total_rows_paragraphs[1]  # = 11200

tbl <- tibble::tibble(
  Category = c(
    "Explicit candidates",
    "Architectural descriptions",
    "Excluded normative",
    "Non-English",
    "Non-natural language",
    "Total routed/gated paragraphs"
  ),
  Count = c(
    df$explicit_candidate_rows[1],
    df$arch_description_rows[1],
    df$excluded_normative_rows[1],
    df$non_english_rows[1],
    df$non_natural_language_rows[1],
    total
  )
) %>%
  mutate(Percentage = round(Count / total * 100, 2))

png(filename = out_png, width = 1800, height = 900, res = 300)
grid.newpage()

tableGrob_obj <- tableGrob(tbl, rows = NULL)
grid.draw(tableGrob_obj)

dev.off()