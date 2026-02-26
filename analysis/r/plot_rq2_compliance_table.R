library(tibble)
library(gridExtra)
library(grid)

out_png <- "D:/Desktop/analysis/figures/7_6_constraint_level_compliance.png"

df_disp <- tibble(
  `Constraint ID` = c("C1","C10","C2","C3","C4","C5","C6","C7","C8","C9"),
  Constraint = c(
    "Stateless API layer: audit persistence separated from runtime",
    "Cross-context access via explicit OpenAPI contracts and event topics",
    "Fuzzy matching index isolated from transactional systems",
    "Domain layer must be framework/infrastructure independent",
    "Application layer depends on domain ports, not infrastructure adapters",
    "Infrastructure adapters explicitly named and isolated",
    "Domain events use explicit event naming (Event suffix)",
    "Banking service naming bounded-context aligned (BIAN suffixes)",
    "Each bounded context service must publish an OpenAPI contract",
    "Shared libraries remain code-level only (no shared persistence)"
  ),
  Method = c(
    "Package separation check (UC03 audit vs cache packages)",
    "Import scan: direct cross-context imports (non-port) flagged as violations",
    "Import scan: UC03 matching package must not import persistence",
    "Import scan: forbidden imports in *.domain.* packages",
    "Import scan: *.infrastructure.* forbidden in *.application.* packages",
    "Naming check: classes in *.infrastructure.adapter.* must use allowed suffixes",
    "Naming check: classes in *.domain.event(s).* must end with 'Event'",
    "Naming check: classes in service packages must use BIAN suffixes",
    "File existence check: api/openapi/<context>.yaml",
    "Import scan: persistence imports forbidden in shared-kernel/common-domain"
  ),
  Compliant = c("yes","yes","yes","no","no","yes","yes","yes","yes","yes"),
  Detail = c(
    "audit_pkg=True, cache_pkg=True",
    "0 violation(s) found",
    "0 violation(s) found",
    "75 violation(s) found",
    "3 violation(s) found",
    "0 violation(s) found",
    "0 violation(s) found",
    "0 violation(s) found",
    "13 files found; 0 missing",
    "0 violation(s) found"
  )
)

# ---- THESIS STYLE TABLE THEME ----
thesis_theme <- ttheme_default(
  core = list(
    fg_params = list(fontsize = 6),
    bg_params = list(fill = "white", col = "black", lwd = 0.8),
    padding = unit(c(3, 3), "mm")
  ),
  colhead = list(
    fg_params = list(fontsize = 8, fontface = "bold"),
    bg_params = list(fill = "#E6E6E6", col = "black", lwd = 1)
  )
)

tbl <- tableGrob(
  df_disp,
  rows = NULL,
  theme = thesis_theme
)

png(filename = out_png, width = 2600, height = 700, res = 300)
grid.newpage()
grid.draw(tbl)
dev.off()

cat("Saved:", out_png, "\n")