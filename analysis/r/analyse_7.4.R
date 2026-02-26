library(grid)
library(gridExtra)
library(stringr)

out_dir <- "D:/Desktop/analysis/figures"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
out_file <- file.path(out_dir, "table3_confirmed_constraints.png")

wrap_text <- function(x, width = 40) {
  sapply(x, function(s) paste(strwrap(s, width = width), collapse = "\n"))
}

table3 <- data.frame(
  `#` = 1:4,
  `Source Artifact` = wrap_text(c(
    "docs/architecture/.../UC003_Confirmation_of_Payee_HLD.md",
    "docs/architecture/PMD_HEXAGONAL_BIAN_REVIEW.md",
    "docs/enterprisearchitecture/.../SERVICE_API_CONTRACTS_INDEX.md",
    "docs/enterprisearchitecture/.../SERVICE_DATA_OWNERSHIP_MATRIX.md"
  ), width = 55),
  `Constraint Types (atomic)` = wrap_text(c(
    "Layering / Structural (x1)\nDependency / Coupling (x1)",
    "Dependency / Coupling (x2)\nModularization / Component Boundary (x3)",
    "Interface / Contract (x1)",
    "Dependency / Coupling (x1)\nInterface / Contract (x1)"
  ), width = 55),
  check.names = FALSE
)

# Theme: giảm padding để table “nở”
thm <- ttheme_minimal(
  base_size = 7,
  padding   = unit(c(1.5, 2), "mm"),
  core = list(
    fg_params = list(hjust = 0, x = 0.02),
    bg_params = list(fill = c("white", "#f7f7f7"))
  ),
  colhead = list(
    fg_params = list(fontface = "bold", hjust = 0, x = 0.02),
    bg_params = list(fill = "#e0e0e0")
  )
)

tg <- tableGrob(table3, rows = NULL, theme = thm)

# PNG size nên vừa phải (đừng quá rộng)
png(filename = out_file, width = 1800, height = 650, res = 300)

grid.newpage()

# Ép tableGrob fill gần hết trang (top=2% margin, bottom=2%, left/right=2%)
grid.draw(arrangeGrob(
  tg,
  padding = unit(0.02, "npc")
))

dev.off()
cat("Saved:", out_file, "\n")