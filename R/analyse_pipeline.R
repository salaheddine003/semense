args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args) >= 1) args[[1]] else "data/enriched/fact_table.csv"
output_dir <- if (length(args) >= 2) args[[2]] else "reports/r"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

fact <- read.csv(input, sep = ";", fileEncoding = "UTF-8-BOM",
                 stringsAsFactors = FALSE, check.names = FALSE)
fact$RESULT_NUM <- as.numeric(fact$RESULT_NUM)
fact$YEAR <- as.numeric(fact$YEAR)
yield <- fact[fact$TRAIT == "YD15QH" & !is.na(fact$RESULT_NUM), ]

stats <- aggregate(RESULT_NUM ~ ESPECE_FR, yield, function(x) {
  c(n = length(x), mean = mean(x), median = median(x), sd = sd(x),
    min = min(x), max = max(x))
})
stats_out <- data.frame(ESPECE_FR = stats$ESPECE_FR, stats$RESULT_NUM)
write.csv(stats_out, file.path(output_dir, "stats_r.csv"),
          row.names = FALSE, fileEncoding = "UTF-8")

anova_data <- yield[!is.na(yield$REGION) & yield$REGION != "", ]
anova_summary <- data.frame()
if (nrow(anova_data) >= 20 && length(unique(anova_data$REGION)) >= 2) {
  model <- aov(RESULT_NUM ~ REGION, data = anova_data)
  table <- summary(model)[[1]]
  anova_summary <- data.frame(
    factor = rownames(table), df = table[, "Df"],
    sum_sq = table[, "Sum Sq"], mean_sq = table[, "Mean Sq"],
    f_value = table[, "F value"], p_value = table[, "Pr(>F)"]
  )
  write.csv(anova_summary, file.path(output_dir, "anova_r.csv"),
            row.names = FALSE, fileEncoding = "UTF-8")
}

png(file.path(output_dir, "rendement_espece_r.png"), width = 1400, height = 800)
par(mar = c(11, 5, 4, 2) + 0.1)
boxplot(RESULT_NUM ~ ESPECE_FR, data = yield, las = 2, cex.axis = 0.8,
        main = "Rendement YD15QH par espèce", ylab = "Rendement")
dev.off()

cat(sprintf("R_OK rows=%d species=%d anova_rows=%d\n",
            nrow(yield), length(unique(yield$ESPECE_FR)), nrow(anova_summary)))
