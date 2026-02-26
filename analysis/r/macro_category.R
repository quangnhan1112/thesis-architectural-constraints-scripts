library(readr)
library(dplyr)
library(ggplot2)

tables_dir  <- "D:/Desktop/analysis/tables"
figures_dir <- "D:/Desktop/analysis/figures"

dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)

# 1) Read the table you already have
df <- read_csv(
  file.path(tables_dir, "7_4_5_top_categories_per_source.csv"),
  show_col_types = FALSE
)

# 2) Build plot_df in the format your ggplot expects
plot_df <- df %>%
  rename(macro_category = `Constraint category`) %>%
  group_by(Source) %>%
  mutate(share = `Count (n)` / sum(`Count (n)`) * 100) %>%
  ungroup()

# 3) Plot
p <- ggplot(plot_df, aes(x = reorder(macro_category, share), y = share)) +
  geom_col() +
  geom_text(aes(label = sprintf("%.1f%%", share)), hjust = -0.1, size = 3.5) +
  coord_flip() +
  facet_wrap(~ Source, scales = "free_y") +
  labs(
    title = "Top-10 constraint categories by source (share within top-10)",
    x = NULL,
    y = "Share (%)"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold"),
    axis.text = element_text(size = 11)
  ) +
  expand_limits(y = max(plot_df$share) * 1.15)

# 4) Save
out_png <- file.path(figures_dir, "7_4_5_top_categories_share_within_top10.png")
ggsave(out_png, plot = p, width = 10, height = 6, dpi = 300)

cat("Plot saved to:", normalizePath(out_png, winslash = "/", mustWork = FALSE), "\n")
print(p)