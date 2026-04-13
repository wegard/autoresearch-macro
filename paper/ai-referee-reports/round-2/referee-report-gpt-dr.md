# Referee report

### Summary

This manuscript studies whether an LLM-guided “agentic search” procedure can improve pseudo-real-time macroeconomic forecasts produced by a time-series foundation model in a small open economy setting. The application is monthly forecasting for the Norwegian macroeconomy, with four target variables (CPI inflation, industrial production, retail sales, unemployment) and horizons 1, 3, 6, and 12 months ahead. The backbone forecaster is Chronos-2 (120M parameters), accessed via an AutoGluon TimeSeries interface, and the agent (Claude Sonnet) iteratively proposes pipeline configurations spanning covariate selection (from 14 candidate macro covariates), covariate transformations, context length, and LoRA fine-tuning settings. Evaluation follows a rolling pseudo-real-time protocol that attempts to respect publication lags using latest-vintage data with “availability” restrictions. fileciteturn0file0

The central empirical finding is a clean overfitting pattern: the agent discovers an economically interpretable configuration (context length 96 months; covariates including oil prices, the policy rate, US inflation, and NOK/EUR) that improves validation-period performance (2006–2015) by 6.8% in average MASE relative to zero-shot Chronos-2. However, when the configuration is frozen and evaluated out-of-sample on 2016–2025 (including COVID and the post-2022 inflation surge), the agent-tuned pipeline fails to generalize; zero-shot Chronos-2 is more robust, and the random walk is a particularly strong benchmark in the test period. A step-by-step ablation shows that each “accepted” improvement on the validation window monotonically increases the validation-to-test gap, with the policy-rate covariate contributing the largest deterioration. fileciteturn0file0

### Major comments

1. **Pseudo-real-time design requires a much more explicit audit for information leakage and alignment errors (publication lags, aggregation, forward-filling, ragged edge).**  
   The paper’s claims hinge on the pseudo-real-time discipline and on correct timing of inputs. The current description (availability defined by month_end(m)+lag, daily-to-monthly averaging, and quarterly-to-monthly forward-fill) is not sufficient to verify that the information set at each forecast origin contains only genuinely available data. fileciteturn0file0  
   Required clarifications and checks:  
   - A precise definition of “forecast origin date” relative to month-end for each series class (monthly, daily aggregated to month, quarterly forward-filled). If the origin is at month-end, a “lag=1 day” series should not be available until the next day; if origins are effectively set after all month-end releases, that must be stated and justified. fileciteturn0file0  
   - A mechanical description (preferably with a timeline figure/table) of how the ragged edge is handled: what happens when some covariates are observed up to t while others only up to t−k due to lags (e.g., 90-day lag quarterly series). The manuscript does not specify whether missing values are left missing, truncated, imputed, or carried forward, and how this is handled consistently across Chronos-2 and classical baselines. fileciteturn0file0  
   - A specific leakage risk is quarterly forward-fill: forward-filling a quarterly value into months inside the quarter is only admissible after the quarterly value is released; otherwise it effectively injects future information. The paper must demonstrate that the forward-fill respects the lag rule (i.e., the value is missing until the release date, then carried forward thereafter). fileciteturn0file0  
   Without this audit, the comparative results (especially around crises and regime shifts) are not yet on a firm identification footing.

2. **Chronos-2 covariate usage and multivariate handling must be specified in operational terms to rule out implicit “forecasting of covariates” and unintended conditioning on unavailable future paths.**  
   Chronos-2’s group attention allows using covariates “in context,” but the practical interface can implement covariates in materially different ways (past covariates only; known future covariates; joint forecasting of targets+covariates in a multivariate group). The manuscript states that Chronos-2 “natively integrates both past covariates and known future covariates,” but it does not state which type is actually used for each variable class here, nor how the future portion of covariate series is represented at inference time. fileciteturn0file0  
   Required details:  
   - For each covariate, whether the model receives values only up to t (past-only), or also values at t+h (known-future). For macro covariates like the policy rate and US CPI, “known future” is not available at the origin; the implementation must not inadvertently provide it. fileciteturn0file0  
   - If covariates are included as separate series in a multivariate group, clarify whether Chronos-2 jointly forecasts covariates forward and then uses those internal forecasts to condition target forecasts. That is a different forecasting problem than “forecast y given observed x up to t,” and it can also change the appropriate baselines. fileciteturn0file0  
   - Report results for the “Grouping: univariate vs all targets” dimension explicitly. This is listed in the search space but is not transparently reported as a baseline, an ablation, or an accepted/rejected agent step, despite being central to what Chronos-2 is designed to exploit. fileciteturn0file0  
   As written, a reader cannot tell whether the agent’s “covariate gains” are gains from conditioning on lagged predictors, gains from internally forecasting predictors, or artifacts of data handling.

3. **The agentic search constitutes adaptive model selection over many tries; the evaluation needs to treat it as such (data-snooping control, nested validation, and stability criteria).**  
   The manuscript’s main narrative is that agentic search improves validation MASE and fails to generalize; that is plausible and interesting. However, the current experimental design still needs to acknowledge formally that 50 adaptive iterations—each using validation feedback—creates data-snooping bias in the reported validation improvement and complicates inference on whether the agent improves over a naive hyperparameter search. fileciteturn0file0  
   Required upgrades:  
   - Report uncertainty around the validation improvement (e.g., distribution of loss differentials across forecast origins, block bootstrap confidence intervals, or formal tests comparing the final selected configuration to the baseline). A simple “−6.8% MASE” is not interpretable without uncertainty, especially under adaptive selection. fileciteturn0file0  
   - Introduce a genuinely nested procedure: e.g., split 2006–2015 into an inner window for search and an outer validation window for selection, or run rolling-origin cross-validation where the agent is re-run on multiple historical segments and evaluated on subsequent segments. The current single validation block makes it too easy for any search method to latch onto period-specific relationships. fileciteturn0file0  
   - If the paper’s intended contribution is precisely “search overfits under regime change,” formalize that claim by defining a robustness objective (e.g., minimize worst-subperiod loss or penalize instability) and showing that standard objectives (mean validation loss) select fragile configurations. This connects directly to the broader literature on forecast evaluation under instabilities. citeturn4search3turn4search7

4. **Baseline set is not yet at the IJF standard for macroeconomic forecasting in data-rich (or even moderately data-rich) environments, and the factor/VAR baselines are currently too weak to support broad claims.**  
   The manuscript includes random walk, seasonal naive, AR, ARIMA, ETS, a VAR (using the agent-selected covariates), and a principal-component “factor model.” fileciteturn0file0  
   Several issues must be addressed:  
   - Tables emphasize only a subset of the stated baselines (e.g., seasonal naive and AR are described but not shown in key summary tables). IJF readers will expect the full baseline set to be reported consistently. fileciteturn0file0  
   - The “factor model” uses PCs from only 14 covariates. That is not a meaningful proxy for the large-panel factor model literature; it is closer to a small-data regression on a few PCs. If the goal is to benchmark against diffusion-index forecasting, the paper needs either a larger macro panel or a more defensible statement about why this reduced panel is the relevant information set. fileciteturn0file0  
   - A macro forecasting paper in IJF typically requires at least one shrinkage multivariate benchmark (e.g., Bayesian VAR with Minnesota-type priors) because unrestricted VARs are known to underperform when dimensionality grows. citeturn3search2turn3search10  
   - Given the paper’s emphasis on regime change and structural breaks, time-varying parameter methods (or model averaging) are particularly relevant baselines. citeturn3search3turn3search7  
   - The manuscript’s narrative about “robustness” would be stronger with at least one modern ML benchmark that has documented crisis-period advantages in macro forecasting (e.g., random forests or boosting with time-series-appropriate tuning). citeturn3search17turn3search5  
   Without these baselines, the claims risk being read as “Chronos-2 vs ARIMA vs random walk,” which is too narrow for general macro-forecasting conclusions.

5. **Forecast accuracy metrics, aggregation across series/horizons, and statistical testing need tightening (definitions, weighting, and correct test choice for nested comparisons).**  
   The paper uses RMSE, MAE, and MASE, and it uses MASE as the primary search objective, averaged across targets and horizons. fileciteturn0file0  
   Required revisions:  
   - Provide the exact mathematical definition of MASE as implemented. The text says MASE divides MAE by the MAE of the random walk forecast, but the canonical MASE scales by the in-sample mean absolute one-step naive error (which enables scale-free comparisons across series). citeturn4search13turn4search1  
   - Clarify how cross-target aggregation is done for RMSE. “Average RMSE across targets” is not meaningful unless targets are standardized or otherwise brought to comparable units; the manuscript should state whether each series is scaled (and how) before computing RMSE averages. fileciteturn0file0  
   - When comparing nested models, the vanilla Diebold–Mariano framework can be invalid, and the paper should state which comparisons are nested and how inference is handled for them (e.g., Clark–West type corrections for nested predictive accuracy). citeturn4search10turn0search3turn0search11  
   - For limited samples (here ~111 test origins), small-sample modifications to DM-type tests are often recommended; at minimum, the paper should report whether such corrections were considered and whether conclusions change. citeturn4search0turn4search10  
   - Replace the statement “DM tests not tabulated for brevity” with actual reporting. A credible IJF submission needs the full set of pairwise comparisons (or a structured alternative such as a Model Confidence Set), especially when concluding that “almost no method significantly outperforms” a benchmark. citeturn3search8turn2search0 fileciteturn0file0

6. **Probabilistic evaluation is currently inconsistent with the modeling choice and with the manuscript’s own positioning.**  
   Chronos is a probabilistic forecasting framework, and the manuscript signals interest in quantiles and pinball loss, yet the reported results are essentially point-forecast metrics (RMSE/MAE/MASE). fileciteturn0file0  
   Required additions:  
   - Report proper scoring rules for density/quantile forecasts (CRPS and/or multi-quantile pinball loss), plus coverage/calibration diagnostics for predictive intervals. These are central to IJF’s forecasting-practice relevance, and they matter especially in crisis periods where point errors can be dominated by tail events. fileciteturn0file0  
   - Align the search objective with the probabilistic outputs if the end use is probabilistic forecasting; otherwise, justify why a probabilistic model is evaluated and tuned exclusively for a point metric.

7. **Reproducibility package is not yet adequate, especially given dependence on a proprietary LLM agent and adaptive search.**  
   The paper references an “experiment log” in a project repository and describes a ratchet-style loop with quick and full evaluations. fileciteturn0file0  
   IJF expectations for reproducibility require:  
   - A complete public configuration of the forecasting pipeline (data acquisition scripts, release-lag table used in code, aggregation rules, missing-data handling, evaluation code for rolling origins/horizons). Table 8 is helpful but not enough on its own. fileciteturn0file0  
   - Exact software versions (Chronos-2 checkpoint identifier, AutoGluon version, inference settings such as number of samples, quantile extraction method, random seeds). fileciteturn0file0  
   - Full disclosure of the agent prompt (program.md), constraints, temperature/top-p (if any), and the complete list of proposed configurations (not only accepted steps). The agent’s behavior is part of the method, and without these artifacts the study cannot be replicated. fileciteturn0file0  
   - An explicit discussion of what is and is not replicable due to API drift in proprietary LLMs, and a “replay mode” that reproduces all reported results from fixed stored configurations even if the agent cannot be re-run. fileciteturn0file0  
   - Consider adding a sensitivity check using an open-weights LLM agent (even if weaker) to show that conclusions are not dependent on a single vendor model.

### Minor comments

1. The manuscript labels itself “Preliminary and incomplete.” That is not compatible with journal submission format; remove or move to a non-submission draft stage. fileciteturn0file0

2. Key tables should consistently include all declared baselines (seasonal naive and AR are described but not shown in the main validation/test summary tables). fileciteturn0file0

3. Provide explicit notation for the forecast target (levels vs growth rates) and clarify whether industrial production and retail sales are modeled in levels or log-levels. Targets are stated as “never transformed,” but the implications for comparability vs ARIMA differ across series. fileciteturn0file0

4. Clarify the definition of “unlimited context” given the model’s maximum context length and the fact that series have different start dates; state whether the context is truncated to the last K observations or padded, and how early origins are handled when history is short (notably unemployment starts in 2006). fileciteturn0file0

5. Report computational environment for the search (hardware, runtime per evaluation, parallelization, and whether forecasts are deterministic given a fixed configuration). The paper gives approximate runtimes but not the environment. fileciteturn0file0

6. The Diebold–Mariano citation appears as a 2002 JBES entry in the references; ensure the bibliographic entry matches the intended source and that the testing procedure used aligns with the cited paper. fileciteturn0file0 citeturn4search10

7. Table 7’s “random search” comparison would benefit from specifying the sampling distribution over covariate subsets (uniform over subsets vs uniform over subset size vs independent Bernoulli inclusion). “Uniformly from the same search space” is ambiguous and can materially change expected performance. fileciteturn0file0

8. Figures 1, 3, and 4 communicate the core message effectively, but axis labels and captions should state whether metrics are averaged across variables and horizons, and exactly how. fileciteturn0file0

9. The discussion notes that latest-vintage data are used and revisions are left for future work. Add a short, concrete paragraph on how sensitive conclusions might be to revisions, citing standard real-time vintage concerns in macro forecast evaluation. citeturn2search10turn2search6

### Questions for the authors

1. Provide an explicit timing diagram for each data class (monthly, daily aggregated to monthly, quarterly forward-filled) showing when each observation becomes available relative to the forecast origin, and confirm that the implementation enforces this without leakage. fileciteturn0file0

2. Document precisely how Chronos-2 is provided covariates at inference time: past-only vs known-future vs joint multivariate grouping, and how missingness at the ragged edge is represented. fileciteturn0file0

3. State the exact MASE formula implemented (including denominator definition and whether scaling is per-series, per-horizon, or global), and reconcile the implementation with standard MASE definitions. citeturn4search13turn4search1 fileciteturn0file0

4. Report full forecast comparison inference results, either as complete DM/modified-DM tables (with small-sample corrections where appropriate) or via a structured alternative (e.g., Model Confidence Set), and specify which model comparisons are nested and how that is handled. citeturn4search0turn0search11turn3search8 fileciteturn0file0

5. Add at least one shrinkage multivariate macro baseline (e.g., Bayesian VAR) and one instability-adaptive baseline (e.g., time-varying parameter approach or model averaging), and report whether the “zero-shot robustness” claim remains. citeturn3search2turn3search7turn4search3

6. Include proper probabilistic forecast evaluation (CRPS and/or quantile scores plus calibration), consistent with the use of a probabilistic foundation model. fileciteturn0file0

7. Provide a reproducibility supplement containing: data acquisition scripts (or a fully specified extraction protocol), full prompts and agent configuration, search logs for all iterations, and a deterministic replay path that reproduces every reported table/figure from stored configurations. fileciteturn0file0

### Overall assessment

**Recommendation: major revision.**

The topic is timely and relevant for IJF: foundation models and automated pipeline optimization are increasingly used by practitioners, and the paper’s main negative result—agentic search can identify economically plausible predictors yet still overfit badly under regime change—is potentially a valuable contribution. The manuscript also has strengths in transparency of the search trajectory and in the ablation analysis that isolates where generalization fails. fileciteturn0file0

At present, publication is blocked by (i) insufficiently audited pseudo-real-time data handling and Chronos-2 covariate treatment (risk of leakage or mis-specified information sets), (ii) an incomplete and not-yet-credible macro baseline set for IJF standards, (iii) underdeveloped and partially inconsistent evaluation (metric definitions, aggregation, and incomplete inference reporting), and (iv) a reproducibility package that is not yet adequate for an adaptive, proprietary-agent procedure. Addressing the major comments would substantially strengthen both credibility and practitioner relevance. fileciteturn0file0
