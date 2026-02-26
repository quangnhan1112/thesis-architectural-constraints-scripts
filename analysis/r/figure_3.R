library(ggplot2)
library(readr)
library(dplyr)

df <- read_csv("D:/Desktop/analysis/tables/repos_docs_summary.csv") %>%
  mutate(docs_pct = repos_with_docs / total_repos * 100)

p_docs <- ggplot(df, aes(x = source, y = docs_pct)) +
  geom_col(fill = "white", color = "black", width = 0.6) +
  geom_text(
    aes(label = paste0(round(docs_pct, 1), "%")),
    vjust = -0.6,
    size = 4
  ) +
  scale_y_continuous(
    limits = c(0, 100),
    expand = expansion(mult = c(0, 0.05))
  ) +
  labs(
    x = "Source",
    y = "Repositories with analyzable documentation (%)"
  )
# Không thêm theme_* => giữ y chang theme_grey default

ggsave(
  "D:/Desktop/analysis/figures/fig_docs_presence.png",
  plot = p_docs,
  width = 7,
  height = 5,
  dpi = 300
)