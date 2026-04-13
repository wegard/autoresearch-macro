*Referee report on “Can Agentic Search Improve Foundation Model Forecasts for Small Open Economies?”* 

### Summary

This paper studies a relevant and timely question for the forecasting literature: whether an LLM-guided “agentic” search procedure can improve pseudo-real-time macroeconomic forecasts produced by a time-series foundation model. The empirical application is Norway, with monthly forecasts for CPI inflation, industrial production, retail sales, and unemployment at 1, 3, 6, and 12 month horizons. The modeling backbone is Chronos-2, and the agent is allowed to search over covariate inclusion, covariate transformations, context length, grouping, and LoRA fine-tuning settings. The validation period is 2006-2015 and the held-out test period is 2016-2025.

The main empirical result is interesting. The agent finds an economically plausible configuration on the validation sample: a 96-month context window plus Brent oil, the policy rate, US CPI, and NOK/EUR as covariates, with very light fine-tuning. That configuration improves validation MASE relative to the zero-shot baseline. However, the improvement does not generalize to the held-out test period, especially during the COVID and post-2022 episodes. In the test sample, zero-shot Chronos-2 appears more robust than the agent-tuned version, while the random walk is the strongest benchmark overall in the most turbulent periods.

The paper’s best contribution is therefore not a positive AutoML result, but a cautionary one: in macroeconomic environments with structural breaks, an automated search procedure can find interpretable and apparently successful configurations that overfit the validation regime. That is potentially publishable in IJF. The problem is that the current draft does not yet meet the journal’s empirical standard. The benchmark set is too weak and not apples-to-apples, the statistical evaluation is incomplete, the reporting of results is not sufficient to support the interpretation, and the manuscript is explicitly unfinished.

### Major comments

1. **The paper needs to be reframed around its actual contribution.**
   The central result is not that agentic search improves macro forecasts, but that it improves validation performance and then fails out of sample. That is a meaningful result, but it requires a different framing in the title, abstract, introduction, and conclusion. At present, the paper oscillates between a positive “agent discovers a better pipeline” message and a negative “the improvement does not generalize” message. For IJF, the latter is the stronger contribution. The revised paper should make the main claim sharper: under structural change, fixed-window agentic search over a forecasting pipeline is fragile and can overfit even when the selected covariates are economically sensible.

2. **The benchmark set is not adequate for IJF and is not a fair comparison.**
   This is the most important empirical weakness. The paper compares Chronos-2 with random walk, seasonal naive, AR, ARIMA, and ETS. That is not enough for a macro forecasting paper, especially one positioned against the Stock-Watson tradition and modern data-rich forecasting. At minimum, the revision should add strong macro baselines such as diffusion-index/factor models, a dynamic factor model if feasible, and a BVAR or BVARX. A fairer set would also include factor-augmented AR models, regularized ARX/ADL models, and forecast combinations. The comparison is also not apples-to-apples because the tuned Chronos model uses exogenous covariates, whereas the classical baselines appear to be largely univariate. If the foundation model is allowed oil prices, exchange rates, US CPI, and the policy rate, then classical competitors should also be allowed comparable information sets.

3. **The paper does not establish that the “agentic” part adds value relative to standard hyperparameter search.**
   The search space is constrained and not enormous: subsets of 14 covariates, a few transformation classes, a few context lengths, and a small fine-tuning grid. Without a direct comparison to ordinary search procedures under the same computational budget, it is impossible to know whether the LLM agent contributes anything beyond repeated trial-and-error. This comparison is essential because the paper’s novelty is agent-guided search, not merely hyperparameter tuning. The revision should compare the agent to random search, grid search where feasible, or Bayesian optimization over the same space and with the same evaluation budget.

4. **Forecast evaluation lacks formal statistical inference.**
   The paper reports average RMSE and one validation MASE trajectory, but no formal tests of predictive accuracy differences. That is not sufficient for IJF. The revision should include Diebold-Mariano-style comparisons with appropriate HAC treatment for overlapping multi-step forecast errors. Where nested linear competitors are compared, Clark-West or related nested-model tests may be relevant. Confidence intervals or bootstrap uncertainty bands around relative performance would also help. Several reported differences are small in magnitude and may not be statistically meaningful.

5. **The metric design and results reporting need substantial work.**
   The search objective is average MASE across all variables and all horizons, but the main results tables report average RMSE across targets. That mismatch makes the evaluation hard to interpret. The paper needs full reporting of the objective that was actually optimized, on both validation and test samples. It also needs per-variable and per-horizon results; the appendix explicitly says those tables are missing, and they are necessary for assessing the claims. Right now, grand averages across very different targets and horizons hide too much heterogeneity. In addition, the definition of MASE needs to be made precise. The text currently reads more like a relative MAE to the random walk than the conventional Hyndman-Koehler MASE scaling. The exact formula must be stated.

6. **The interpretation that the tuned model fails because of overfit covariate relationships is plausible but not yet demonstrated.**
   The paper attributes the out-of-sample failure to validation-era covariate relationships breaking down under structural change. That may be correct, but the evidence is only indirect. The revision needs ablation results that isolate which accepted change is causing the deterioration: 96-month truncation, individual covariates, the full covariate bundle, grouping choice, or fine-tuning. Table 3 is especially suggestive here because the final LoRA step appears to deliver no gain at the reported precision. The paper should test the post-selection performance of each accepted modification separately.

7. **The fine-tuning protocol is weak and may mechanically disadvantage adaptation.**
   Fine-tuning is performed once at the first forecast origin and then frozen for the entire evaluation. That is a strong design choice and likely not the one a practitioner would use. It also risks conflating “fine-tuning is fragile” with “one-shot fine-tuning on a short early sample is fragile.” Meanwhile, classical baselines are re-estimated at each origin. This asymmetry weakens the conclusion that zero-shot is intrinsically more robust than adaptation. A revision should include at least one rolling or periodic re-fine-tuning design, or else narrow the claim to this specific one-shot adaptation protocol.

8. **The pseudo-real-time setup needs tighter documentation and, ideally, stronger real-time discipline.**
   Using latest-vintage data with release lags is acceptable as pseudo-real-time, but the limitation is more than a footnote in a macro forecasting paper. Revisions matter for several macro series, and the paper should either use real-time vintages where feasible or provide more evidence that the conclusions are not driven by ignoring revisions. More detail is also needed on release calendar implementation, mixed-frequency alignment, and handling of leading missing values. A specific concern is the start date: unemployment appears to begin exactly when the validation period begins, so the first forecast origins may be estimated with almost no target history. The paper should state the minimum estimation window and how early origins are handled for each target.

9. **The broader claims about foundation models are too strong for the current evidence base.**
   The evidence is from one foundation model, one country, four targets, and one validation/test split. That is enough for an interesting case study, but not enough to support broader claims about “zero-shot foundation model robustness” in macro forecasting. The current results do not show uniform dominance even within the case study: random walk is strongest overall in difficult periods, and ARIMA is competitive or better in some cells. The revision should either add at least one additional time-series foundation model or narrow the claims substantially.

10. **Reproducibility is not yet at a publishable standard.**
    The paper references a repository and a search log, but the manuscript does not yet provide enough detail to guarantee replication. A revision should include a full replication package: raw data pulls or exact retrieval scripts, transformation code, publication-lag logic, seeds, package versions, hardware details, the exact `program.md` prompt/specification, accepted and rejected configurations, and code to reproduce every table. Given that the contribution is partly methodological, the agent prompt and search log are core scientific objects and must be available.

### Minor comments

1. The draft is not submission-ready in its current form. There are multiple visible TODOs, a placeholder author email, an empty Appendix C, and unresolved notes in the main text.

2. Table 3 and Algorithm 1 appear inconsistent. The algorithm states that a new configuration is accepted only when the full score is strictly better than the current best, but iteration 45 has the same rounded MASE as iteration 39. Clarify whether the unrounded values differ or whether the acceptance rule is actually weak inequality.

3. The paper should state exactly how point forecasts are extracted from Chronos-2. Mean, median, or another functional of the predictive distribution?

4. The manuscript mentions probabilistic forecasting and pinball loss in the literature discussion, but no density results are reported. Either add density evaluation or simplify the related discussion.

5. Clarify whether the final preferred configuration is univariate or grouped across all targets. Grouping is in the search space but never clearly reported in the results.

6. In several places the manuscript refers to NOK/EUR as if it were trade-weighted. It is a bilateral exchange rate, not a trade-weighted index, unless it is being used as a proxy. The wording should be corrected.

7. Table captions should say explicitly whether the averages are across targets, horizons, origins, or all three.

8. The discussion uses strong causal language such as “implicit regularization” and “oil price relationships actively mislead the model.” Those are reasonable hypotheses, but the wording should be softened unless supported by additional diagnostics.

9. The references lean heavily on recent arXiv and GitHub sources in the agentic-search section. That is understandable for a new topic, but the paper should keep the center of gravity on the established forecasting literature.

10. A figure showing rolling relative loss over time would communicate the pre-COVID, COVID, and post-COVID pattern much better than the current period averages alone.

### Questions for the authors

1. How does the LLM-guided search compare to random search or Bayesian optimization over the same search space and with the same budget?

2. Which component of the accepted pipeline is actually responsible for the poor test performance: covariates, context truncation, grouping, or fine-tuning?

3. Why is fine-tuning performed only once at the first origin rather than periodically or recursively? What happens if the tuned model is refreshed over time?

4. What is the exact formula used for MASE, especially at multi-step horizons and when averaging across variables?

5. How much target history is available at the first validation origin for each series, especially unemployment, and what minimum sample restrictions are imposed?

6. Would the main conclusion survive under alternative validation/test splits or a rolling validation design?

7. Are the selected covariates also useful in classical multivariate benchmarks such as ARX, factor-augmented regressions, or BVARX models?

8. To what extent might Chronos-2 pretraining data overlap with publicly available macroeconomic series similar to those used here, and how should that affect interpretation of the zero-shot results?

### Overall assessment

**Recommendation: Major revision**

The paper asks a worthwhile forecasting question and the negative result is potentially important for IJF: an automated search procedure can find an interpretable configuration that improves validation performance yet fails under structural break. That is a useful message for practitioners and researchers. However, the current manuscript is not ready for publication. The benchmark set is too weak and not comparable to the tuned foundation-model setup, there is no formal forecast-comparison inference, the reporting is incomplete, the role of the agent relative to standard search is not identified, and the manuscript remains explicitly unfinished. A substantially revised version could become publishable, but the current draft falls well short of IJF standards on methodology, evidence, and reproducibility.
