library(readr)
library(dplyr)
library(ggplot2)
library(RColorBrewer)

in_csv  <- "D:/Desktop/analysis/tables/routing_breakdown_source_x_type.csv"
out_png <- "D:/Desktop/analysis/figures/fig_routing_breakdown_by_source.png"

df <- read_csv(in_csv, show_col_types = FALSE) %>%
  mutate(
    candidate_type = factor(
      candidate_type,
      levels = c(
        "explicit_candidate",
        "arch_description",
        "excluded_normative",
        "non_english",
        "non_natural_language"
      ),
      labels = c(
        "Explicit candidates",
        "Architectural descriptions",
        "Excluded normative",
        "Non-English",
        "Non-natural language"
      )
    ),
    source = factor(source, levels = c("github", "sf100"), labels = c("GitHub", "SF100")),
    pct_plot = pct * 100
  )

p <- ggplot(df, aes(x = source, y = pct_plot, fill = candidate_type)) +
  geom_col(color = "black", width = 0.6) +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 20),
    labels = function(x) paste0(x, "%")
  ) +
  scale_fill_brewer(palette = "Blues") +
  labs(
    x = "Source",
    y = "Routed/Gated paragraphs (share within source)",
    fill = "Category"
  )

ggsave(out_png, plot = p, width = 7, height = 5, dpi = 300)