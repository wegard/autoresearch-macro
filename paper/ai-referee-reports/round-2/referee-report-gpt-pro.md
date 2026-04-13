### Summary

This manuscript studies whether an LLM-guided outer-loop search can improve pseudo-real-time forecasts of Norwegian macroeconomic variables when the underlying forecasting model is Chronos-2. The authors define a constrained search over covariate inclusion, covariate transformations, context length, grouping, and LoRA fine-tuning, and they evaluate candidate configurations on a validation period from 2006–2015 with 120 monthly forecast origins. The targets are CPI inflation, industrial production, retail sales, and unemployment, at horizons 1, 3, 6, and 12 months. The central empirical finding is that the search identifies an economically sensible configuration—Brent crude, the policy rate, US CPI, and NOK/EUR with a 96-month context—that improves validation MASE by 6.8 percent relative to the zero-shot baseline. 

The held-out test results are the main contribution of the paper. The validation gain does not generalize to 2016–2025. The agent-tuned configuration underperforms the zero-shot Chronos-2 specification, and the deterioration is especially severe in the post-2022 period. The paper interprets this as evidence that agentic search overfits validation-era covariate relationships, whereas zero-shot foundation models may be more robust under regime change.

The question is timely and relevant for IJF. The pseudo-real-time discipline, the emphasis on a small open economy, and the willingness to report a negative result are all strengths. The current version, however, is not yet methodologically strong enough for publication. The main weaknesses are the use of non-comparable aggregate RMSE across different target variables, an incomplete and partly unfair benchmark set, weak identification of what the LLM search adds beyond simpler procedures, underdeveloped statistical inference, and limited reproducibility detail. The paper is promising, but it needs a substantial revision.

### Major comments

1. **The headline aggregate metric is not interpretable, and the MASE definition is inconsistent.**

   Tables 2, 4, and 5 report “average RMSE across targets.” That is not a meaningful cross-series aggregate when the targets are in different units and scales: CPI inflation, industrial production, retail sales, and unemployment are not commensurable. Averages of RMSE across such variables can change rankings in arbitrary ways. The paper should use only scale-free aggregate losses for headline comparisons across variables, such as MASE, RMSSE, or relative MAE/RMSE. RMSE can still be reported, but only at the individual-series level.

   There is a second problem here. Section 4.3 states that MASE is the MAE divided by the MAE of the random walk forecast. Under that definition, the random walk should equal 1 by construction for a given series and horizon. In Table 9 it does not. Either the definition is incorrect, or the table is mislabeled, or a different denominator is being used. This is not cosmetic: the 6.8 percent validation improvement and the ablation results rely on this metric. The exact formula must be stated clearly.

2. **The benchmark set is too weak for IJF, and some comparators are not independently specified.**

   The paper compares Chronos-2 mainly against random walk, ARIMA, ETS, a VAR, and a simple factor model. For a macro forecasting paper in IJF, this is not enough. At a minimum, I would expect a serious shrinkage-based multivariate benchmark such as a Minnesota BVAR or related Bayesian shrinkage model, and a more standard dynamic factor/diffusion-index specification. If the paper invokes the machine-learning forecasting literature, then at least one regularized regression or tree-based benchmark should also be considered.

   The current VAR baseline is also problematic because it uses the four covariates selected by the agent. That imports the LLM’s potentially overfit covariate choice into the classical comparator. The VAR should be tuned independently, or replaced by a shrinkage model using the full information set. More generally, the benchmark suite should not depend on the LLM-selected specification.

   Finally, the baseline reporting is inconsistent. Seasonal naive is listed but never shown in the key tables. ETS appears in Table 2 but disappears in Table 4. The ARIMA benchmark appears nonseasonal only. The benchmark design needs to be expanded and reported consistently.

3. **The paper does not cleanly identify what the LLM search is adding.**

   The selected pipeline differs from the baseline along several dimensions at once: context truncation, covariate inclusion, and fine-tuning. Table 6 is helpful, but it is still a sequential path-dependent ablation, not a clean decomposition. The paper needs additional controls to isolate the source of gains and losses.

   In particular, the revision should include: zero-shot Chronos-2 with the selected covariates and 96-month context but no LoRA; LoRA without covariates; an expert-specified covariate set based on standard small-open-economy priors; and a domain-blind prompt. Without these controls, the current result could simply be that fragile covariates hurt under regime change, not that “agentic search” is the operative mechanism.

   I would also add at least one non-LLM search baseline tailored to this structured search space, such as greedy forward selection or Bayesian optimization. Table 7 does not establish a robust LLM advantage: random search achieves a slightly better validation score, and it finds that score immediately. The current comparison is too thin to support claims about search efficiency.

4. **The search evaluation is too fragile to support broad conclusions about agentic search.**

   The paper’s main scientific message is that selection on one validation window can overfit badly. That is plausible. But the same critique applies to the search experiment itself. The evidence is based on one 50-iteration LLM run, one 50-iteration random-search run, and one validation era. That is not enough to characterize the behavior of the method.

   The authors should report repeated LLM runs with different seeds or prompt initializations, repeated random-search runs, and preferably at least one stronger search comparator. They should also clarify whether the 20-origin quick screen is fixed or re-sampled across iterations, because this affects selection risk. A more convincing design would use multiple pre-test validation windows or a rolling validation objective rather than a single 2006–2015 block.

5. **The statistical inference is under-reported, especially given the paper’s emphasis on structural breaks.**

   “DM tests not tabulated for brevity” is not adequate for a paper built around relative forecasting performance. The revision should report the full Diebold-Mariano evidence by variable and horizon, state the exact loss differential used, and clarify whether any small-sample correction is applied. With overlapping multi-step errors and a modest effective sample, these details matter.

   The paper would also benefit from a more formal instability analysis. The subperiod tables are useful descriptively, but the central claim is about regime dependence. That claim would be stronger with rolling relative-loss plots and uncertainty bands, block-bootstrap intervals for the subperiod differences, or a formal conditional predictive ability/stability analysis.

   The interpretation that the “policy rate” is the largest source of overfitting also needs more caution. Table 6 is sequential. The marginal contribution of one covariate depends on what has already been added. A leave-one-out or alternative decomposition would be more convincing.

6. **The pseudo-real-time protocol and replication details are not yet sufficient.**

   Table 8 is useful, but the implementation details are still too compressed for replication. The paper should specify the exact forecast date within each month, how the information set is constructed when the current month’s target is not yet released, how missing early histories are handled, and how daily and quarterly data are aligned relative to the monthly forecast origin.

   There is also an unresolved sample-start issue. Table 8 reports unemployment as available from 2006-01, which is also the start of the validation period. That raises a basic question: how are the earliest forecast origins estimated for models that require historical lags? This needs to be spelled out.

   On the software side, the paper should provide the full prompt, Anthropic model version, temperature, seed policy, the exact AutoGluon/Chronos versions, the quick-screen origin set, and a pinned repository and commit hash. Because the search agent is proprietary and mutable over time, these details are essential.

7. **The paper’s interpretation of “zero-shot robustness” is too strong relative to the evidence.**

   The paper is strongest when read as a cautionary result: validation-era gains from searched multivariate pipelines do not survive out of sample. That is useful. The stronger claim—that zero-shot foundation models are robust winners under structural breaks—is not yet established. On the full test period, the random walk is best overall, and ARIMA remains very competitive. The evidence shows that zero-shot Chronos-2 is more robust than the searched configuration and some multivariate baselines, not that it is the dominant practical method.

   The discussion should also be more precise about the regime story. The validation era is not a tranquil benchmark period; it includes the global financial crisis and the 2014–2015 oil-price episode. The failure may therefore be specific to the post-pandemic inflation/monetary regime rather than a generic “normal times versus crises” contrast.

   A related issue is that Chronos-2 is a probabilistic model, yet the evaluation is entirely point-forecast based. If the paper wants to make a practical case for foundation models, density forecast evidence should be included, or the claims should be narrowed to point forecasting only.

8. **The external validity is too limited for the current framing.**

   One country, four targets, and one foundation model is a narrow empirical base. That does not make the paper uninteresting, but it does limit what can be concluded. As currently written, the title and abstract imply broader evidence on “small open economies” and “foundation model forecasts” than the design can support.

   There are two ways forward. Either expand the empirical scope by adding at least one additional small open economy or one additional TSFM, or narrow the framing throughout and present the paper as a Norway case study with a specific lesson about validation overfitting in agent-guided multivariate search. In its present form, the framing is broader than the evidence.

### Minor comments

1. The manuscript is labeled “Preliminary and incomplete.” That is not appropriate for a review-stage submission.

2. Section 4.4 lists seven baselines, but the key result tables do not report them consistently. Seasonal naive is absent from the main tables, and ETS disappears in the test table.

3. Table 1 and Appendix B do not list the transformation options consistently. Harmonize the search-space description.

4. Clarify whether “agent, annual retune” means rerunning the full agentic search each year or only refitting the selected Chronos-2/LoRA specification.

5. Clarify forecast-generation comparability across methods. Are AR, ARIMA, VAR, and factor-model forecasts direct or iterated at each horizon? How does that compare with Chronos-2’s multi-horizon output?

6. Algorithm 1 implies strict ratchet acceptance, but Table 3 shows iteration 45 accepted with the same rounded MASE as iteration 39. Either ties were allowed or the improvement is hidden by rounding.

7. Section 2.1 states that the paper uses pinball loss and quantile forecasts, but the reported evaluation is entirely point-forecast based. This should be corrected.

8. The claim that Norwegian macro data are unlikely to appear in the pretraining corpus is plausible but speculative. Tone it down unless the pretraining corpus is documented.

9. Table 7 includes a “Best config interpretable? Yes/No” column. That is subjective. Either define a criterion or remove it.

10. Figure 3’s labeling should be cleaned up. “Pre-COVID (2016 19)” is not presentation-ready.

11. Table 9 is more informative than some aggregate tables and should probably be moved into the main text.

12. The paper should cite the original Diebold-Mariano reference and state clearly whether a Harvey-Leybourne-Newbold type adjustment is used.

13. The title should be narrowed unless the empirical scope is broadened.

14. The paper should provide the replication repository URL and commit hash in the manuscript itself.

15. The notation for horizons, information sets, and publication lags should be standardized more tightly across Sections 3 and 4.

### Questions for the authors

1. What is the exact MASE formula used in Tables 6 and 9? Is the denominator the in-sample one-step naive error, a horizon-specific naive error, or the evaluation-sample random-walk MAE?

2. How does zero-shot Chronos-2 perform when given the selected covariates and the 96-month context window, but without LoRA fine-tuning?

3. How does the selected LLM configuration compare with a hand-specified small-open-economy covariate set chosen by a macroeconomist ex ante?

4. How sensitive are the selected configuration and its test performance to prompt wording, the Claude model version, temperature, and the specific 20-origin screening subset?

5. Would the main conclusion survive if the search objective used multiple pre-2016 validation windows or a rolling validation design rather than a single 2006–2015 block?

6. How do independently tuned BVAR, dynamic factor, and regularized ML benchmarks perform on the same pseudo-real-time protocol?

7. Did you run a domain-blind prompt? If not, how much of the eventual covariate set is really “discovered” rather than supplied by the prompt’s domain knowledge?

8. How are the first validation origins handled for unemployment and any other series with short initial histories relative to the start of the evaluation?

9. Does probabilistic evaluation using CRPS or pinball loss change the ranking of zero-shot Chronos-2 versus the classical baselines?

### Overall assessment

**Recommendation: major revision.**

The paper asks a relevant question and contains a potentially valuable negative result: an LLM-guided search can find an economically coherent validation-winning configuration that fails badly under later regime change. That is publishable territory for IJF in principle. The current version is not there yet. The aggregate evaluation metric is flawed, the benchmark set is too weak and partly endogenous to the LLM-selected covariates, the evidence for LLM search value over simpler procedures is not convincing, the inference is under-reported, and the reproducibility details are incomplete. If the authors fix the metric issues, strengthen and independently tune the baselines, document the search protocol fully, and narrow the claims to what the evidence actually shows, the paper could become a useful contribution.
