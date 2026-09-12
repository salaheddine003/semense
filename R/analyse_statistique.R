# ============================================================
#  Analyse statistique R — Pôle R&D Semences
#  Utilise le fichier data/enriched/fact_table.csv
#  généré par le pipeline Python (02_etl.py)
# ============================================================

library(dplyr)
library(ggplot2)
library(tidyr)
library(readr)
library(scales)

if (.Platform$OS.type == "windows") Sys.setlocale("LC_CTYPE", ".UTF-8")

# ─────────────────────────────────────────────────────────────
# 0. CHARGEMENT
# ─────────────────────────────────────────────────────────────
cat("Chargement de la table de faits...\n")

script_arg <- grep("^--file=", commandArgs(), value = TRUE)
if (length(script_arg) > 0) {
  base_dir <- dirname(dirname(normalizePath(sub("^--file=", "", script_arg[[1]]))))
} else if (requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
  base_dir <- dirname(dirname(rstudioapi::getSourceEditorContext()$path))
} else {
  base_dir <- getwd()
}
csv_path <- file.path(base_dir, "data", "enriched", "fact_table.csv")

# Fallback si hors RStudio
if (!file.exists(csv_path)) {
  csv_path <- "data/enriched/fact_table.csv"
}

fact <- read_delim(csv_path, delim = ";", locale = locale(decimal_mark = ".", grouping_mark = ","),
                   show_col_types = FALSE)
cat(sprintf("  %s lignes chargées\n", format(nrow(fact), big.mark = ".")))

# ─────────────────────────────────────────────────────────────
# 1. STATISTIQUES DESCRIPTIVES PAR ESPÈCE × TRAIT
# ─────────────────────────────────────────────────────────────
cat("\n--- Stats descriptives par espèce × trait ---\n")

traits_rendement <- c("%MOIS", "YD15QH", "YD16QH", "YDQH", "YD")

stats_espece <- fact %>%
  filter(TRAIT %in% traits_rendement, !is.na(RESULT_NUM), !is.na(ESPECE_FR)) %>%
  group_by(ESPECE_FR, TRAIT) %>%
  summarise(
    N       = n(),
    Moyenne = round(mean(RESULT_NUM, na.rm = TRUE), 3),
    Mediane = round(median(RESULT_NUM, na.rm = TRUE), 3),
    EcartType = round(sd(RESULT_NUM, na.rm = TRUE), 3),
    Min     = round(min(RESULT_NUM, na.rm = TRUE), 3),
    Max     = round(max(RESULT_NUM, na.rm = TRUE), 3),
    .groups = "drop"
  ) %>%
  filter(N >= 10)

print(stats_espece)

# ─────────────────────────────────────────────────────────────
# 2. ANOVA — EFFET DE LA RÉGION SUR LE RENDEMENT
# ─────────────────────────────────────────────────────────────
cat("\n--- ANOVA : effet région sur le rendement ---\n")

anova_results <- list()

for (espece in unique(fact$ESPECE_FR)) {
  for (trait in traits_rendement) {
    sub <- fact %>%
      filter(ESPECE_FR == espece, TRAIT == trait,
             !is.na(RESULT_NUM), !is.na(REGION))
    groupes <- table(sub$REGION)
    groupes_valides <- names(groupes[groupes >= 5])
    sub <- sub %>% filter(REGION %in% groupes_valides)
    if (length(unique(sub$REGION)) >= 2 && nrow(sub) >= 20) {
      model <- aov(RESULT_NUM ~ REGION, data = sub)
      s <- summary(model)[[1]]
      f_stat <- s["REGION", "F value"]
      p_val  <- s["REGION", "Pr(>F)"]
      anova_results[[paste(espece, trait, sep = "_")]] <- data.frame(
        Espece = espece, Trait = trait,
        F_stat = round(f_stat, 3),
        p_value = round(p_val, 5),
        Significatif = p_val < 0.05
      )
    }
  }
}

if (length(anova_results) > 0) {
  anova_df <- bind_rows(anova_results)
  print(anova_df)
  cat(sprintf("  %d/%d tests significatifs (p < 0.05)\n",
              sum(anova_df$Significatif, na.rm = TRUE), nrow(anova_df)))
} else {
  cat("  Aucune donnée suffisante pour ANOVA.\n")
}

# ─────────────────────────────────────────────────────────────
# 3. TEST DE TUKEY (comparaison multivariée des régions)
# ─────────────────────────────────────────────────────────────
cat("\n--- Test de Tukey HSD (Blé tendre, rendt) ---\n")

tukey_sub <- fact %>%
  filter(ESPECE_FR == "Blé tendre", TRAIT %in% traits_rendement,
         !is.na(RESULT_NUM), !is.na(REGION)) %>%
  group_by(REGION) %>%
  filter(n() >= 5) %>%
  ungroup()

if (nrow(tukey_sub) >= 20 && length(unique(tukey_sub$REGION)) >= 2) {
  tukey_model <- aov(RESULT_NUM ~ REGION, data = tukey_sub)
  tukey_test <- TukeyHSD(tukey_model)
  tukey_df <- as.data.frame(tukey_test$REGION)
  tukey_df$Paire <- rownames(tukey_df)
  sig <- tukey_df[tukey_df$`p adj` < 0.05, ]
  cat(sprintf("  %d paires de régions significativement différentes\n", nrow(sig)))
  if (nrow(sig) > 0) print(head(sig[, c("Paire", "diff", "p adj")], 10))
} else {
  cat("  Données insuffisantes pour le test de Tukey.\n")
}

# ─────────────────────────────────────────────────────────────
# 4. RÉGRESSION LINÉAIRE RENDEMENT ~ ANNÉE
# ─────────────────────────────────────────────────────────────
cat("\n--- Régression rendement ~ année (par espèce) ---\n")

regression_data <- fact %>%
  filter(TRAIT %in% traits_rendement, !is.na(RESULT_NUM),
         !is.na(YEAR), !is.na(ESPECE_FR)) %>%
  filter(YEAR >= 2010, YEAR <= 2025) %>%
  mutate(YEAR = as.numeric(as.character(YEAR)))

especes_ok <- regression_data %>%
  group_by(ESPECE_FR) %>%
  summarise(n_annees = n_distinct(YEAR), n_obs = n(), .groups = "drop") %>%
  filter(n_annees >= 3, n_obs >= 30)

for (esp in especes_ok$ESPECE_FR) {
  sub_r <- regression_data %>% filter(ESPECE_FR == esp)
  mod <- lm(RESULT_NUM ~ YEAR, data = sub_r)
  s <- summary(mod)
  cat(sprintf("  %-20s  pente=%.4f  p=%.4f  R²=%.3f\n",
              esp,
              coef(mod)["YEAR"],
              coef(summary(mod))["YEAR", "Pr(>|t|)"],
              s$r.squared))
}

# ─────────────────────────────────────────────────────────────
# 5. GRAPHIQUES ggplot2
# ─────────────────────────────────────────────────────────────
cat("\n--- Génération des graphiques R ---\n")
reports_dir <- file.path(dirname(dirname(rstudioapi::getSourceEditorContext()$path)),
                         "reports", "images")
if (!dir.exists(reports_dir)) dir.create(reports_dir, recursive = TRUE)

palette_especes <- c(
  "Maïs"         = "#F5A623",
  "Tournesol"    = "#E8C32E",
  "Blé tendre"   = "#7ED321",
  "Triticale"    = "#4A90E2",
  "Colza"        = "#9B59B6",
  "Blé dur/Orge" = "#95A5A6"
)

# 5a. Boxplot rendement par espèce
plot_data <- fact %>%
  filter(TRAIT %in% traits_rendement, !is.na(RESULT_NUM), !is.na(ESPECE_FR)) %>%
  group_by(ESPECE_FR) %>%
  filter(n() >= 30) %>%
  ungroup() %>%
  filter(RESULT_NUM >= quantile(RESULT_NUM, 0.01),
         RESULT_NUM <= quantile(RESULT_NUM, 0.99))

p1 <- ggplot(plot_data, aes(x = reorder(ESPECE_FR, RESULT_NUM, median),
                             y = RESULT_NUM, fill = ESPECE_FR)) +
  geom_boxplot(outlier.alpha = 0.2, outlier.size = 0.8) +
  scale_fill_manual(values = palette_especes, na.value = "#888") +
  labs(
    title = "Distribution des valeurs de rendement/humidité par espèce",
    subtitle = "Médiane, IQR et outliers",
    x = "Espèce", y = "Valeur mesurée"
  ) +
  theme_minimal(base_size = 12) +
  theme(legend.position = "none", axis.text.x = element_text(angle = 20, hjust = 1))

ggsave(file.path(reports_dir, "R_01_boxplot.png"), p1, width = 10, height = 5, dpi = 150)
cat("  Sauvegardé : R_01_boxplot.png\n")

# 5b. Évolution annuelle par espèce
evol_data <- fact %>%
  filter(TRAIT %in% traits_rendement, !is.na(RESULT_NUM), !is.na(YEAR), !is.na(ESPECE_FR)) %>%
  mutate(YEAR = as.numeric(as.character(YEAR))) %>%
  filter(YEAR >= 2010, YEAR <= 2025) %>%
  group_by(YEAR, ESPECE_FR) %>%
  summarise(mean_val = mean(RESULT_NUM, na.rm = TRUE),
            se = sd(RESULT_NUM, na.rm = TRUE) / sqrt(n()), .groups = "drop")

esp_ok <- evol_data %>% group_by(ESPECE_FR) %>% filter(n() >= 3) %>% pull(ESPECE_FR) %>% unique()
evol_data <- evol_data %>% filter(ESPECE_FR %in% esp_ok)

p2 <- ggplot(evol_data, aes(x = YEAR, y = mean_val, color = ESPECE_FR, group = ESPECE_FR)) +
  geom_ribbon(aes(ymin = mean_val - se, ymax = mean_val + se, fill = ESPECE_FR),
              alpha = 0.1, color = NA) +
  geom_line(size = 1.2) +
  geom_point(size = 2.5) +
  scale_color_manual(values = palette_especes, na.value = "#888") +
  scale_fill_manual(values = palette_especes, na.value = "#888") +
  scale_x_continuous(breaks = scales::pretty_breaks()) +
  labs(title = "Évolution annuelle des valeurs moyennes par espèce",
       subtitle = "Ruban = ±1 écart-type de la moyenne",
       x = "Année", y = "Valeur moyenne", color = "Espèce", fill = "Espèce") +
  theme_minimal(base_size = 12)

ggsave(file.path(reports_dir, "R_02_evolution.png"), p2, width = 11, height = 5, dpi = 150)
cat("  Sauvegardé : R_02_evolution.png\n")

# 5c. Top 15 régions
regions_data <- fact %>%
  distinct(LK_EXPERIMENT_EXPERIMENT_ID, REGION, ESPECE_FR) %>%
  filter(!is.na(REGION)) %>%
  count(REGION, ESPECE_FR) %>%
  group_by(REGION) %>%
  mutate(total = sum(n)) %>%
  ungroup() %>%
  filter(dense_rank(desc(total)) <= 15)

p3 <- ggplot(regions_data, aes(x = reorder(REGION, total), y = n, fill = ESPECE_FR)) +
  geom_col() +
  scale_fill_manual(values = palette_especes, na.value = "#888") +
  coord_flip() +
  labs(title = "Nombre d'essais par région (top 15)",
       x = NULL, y = "Nombre d'essais", fill = "Espèce") +
  theme_minimal(base_size = 11)

ggsave(file.path(reports_dir, "R_03_regions.png"), p3, width = 10, height = 6, dpi = 150)
cat("  Sauvegardé : R_03_regions.png\n")

cat("\n  Analyse R terminée avec succès.\n")
