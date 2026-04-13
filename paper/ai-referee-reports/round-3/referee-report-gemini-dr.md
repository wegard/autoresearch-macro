# Editorial Review Report: Manuscript IJF-26-XXXX

### Overall impression

The manuscript "Can Agentic Search Improve Foundation Model Forecasts for Small Open Economies?" presents a highly relevant, methodologically sound, and rigorously evaluated study on the application of large language model (LLM)-guided agentic search for macroeconomic forecasting. The core empirical contribution—demonstrating that agent-tuned foundation models tend to overfit to pre-crisis covariate relationships and subsequently fail to generalize during structural breaks, whereas zero-shot models remain surprisingly robust—is compelling and represents a strong fit for the *International Journal of Forecasting*.[1, 2] The pseudo-real-time evaluation protocol, the deliberate choice of a small open economy to test global generalization, and the clever implementation of Karpathy's autoresearch framework are all excellent methodological choices that have been adequately settled in previous review rounds.[1] 

However, the current draft suffers from structural verbosity, redundant exposition of standard econometric concepts, and repetitive reporting of quantitative results across the text, tables, and discussion sections. Academic writing in top-tier applied econometrics journals demands precision and high information density.[3, 4] The manuscript currently reads closer to a working paper or a dissertation chapter than a streamlined journal article. There is a pervasive tendency to narrate data that is already clearly visible in the tables, to preview detailed results in the introduction only to repeat them later, and to provide textbook-level background on foundational models that the readership already understands.[5, 6] By implementing the targeted cuts, structural consolidations, and sentence-level tightening outlined in this report, the manuscript can be reduced by 15–20%—easily bringing it under standard word limits—while significantly amplifying the clarity and impact of its central findings.[7, 8]

### Specific cuts (ordered by impact)

The following actionable cuts target passages where the manuscript loses its momentum through unnecessary exposition or structural redundancy. Implementing these cuts will yield the highest volume of word savings without altering the scientific substance of the paper.

1. **Location:** Section 2.1 (Macroeconomic forecasting), Paragraphs 1-2 (Factor models, high-dimensional data, and machine learning).
   **Issue:** Unnecessary exposition of foundational econometric history. The readership of the *International Journal of Forecasting* does not require a textbook summary of Dynamic Factor Models by Stock and Watson (2002), Bayesian VARs with Minnesota priors by Bańbura et al. (2010), or the basics of Random Forests.[1, 2, 9] Providing a syllabus of macroeconomic forecasting dilutes the manuscript's focus. The primary objective of a literature review in a specialized journal is to contextualize the specific novelties of the current research—in this case, agentic search and foundation models—not to review the entire history of the discipline.[5]
   **Suggested action:** Delete the paragraphs titled "Factor models and high-dimensional data" and "Machine learning for macro forecasting" entirely. Retain only a single introductory sentence stating that the study benchmarks against established multivariate factor and VAR methods, and immediately transition into the subsection "Mixed-frequency data, publication lags, and nowcasting," which is directly relevant to the pseudo-real-time protocol.[1]
   **Estimated savings:** ~250 words.

2. **Location:** Section 1 (Introduction), Paragraphs 4-5.
   **Issue:** Premature and excessively detailed reporting of results. The introduction currently summarizes the specific covariates discovered (oil prices, policy rate, US inflation, NOK/EUR exchange rate), the exact performance gain (6.8%), and the subsequent failure in the test period.[1] This completely duplicates the content of Section 5.2, Section 5.3, and the Abstract. While introductions should preview main findings, listing highly specific numerical outcomes and variable lists creates a redundancy that bogs down the opening pages.[5, 6]
   **Suggested action:** Condense the findings preview into a single, high-level paragraph. Remove the specific list of covariates and the exact percentage improvements from the Introduction. State broadly that the agentic search improves validation performance through interpretable covariate discovery but fails to generalize out-of-sample due to regime changes. Let the Results section do the heavy lifting for the specific numbers.[5]
   **Estimated savings:** ~150 words.

3. **Location:** Section 2.3 (Automated machine learning and feature engineering), Paragraph 1.
   **Issue:** Superfluous background on traditional AutoML frameworks. Detailing Auto-sklearn, successive halving, and Neural Architecture Search (NAS) drifts significantly from the paper's core focus, which is exclusively on LLM-guided agentic search.[1] The evolution of traditional AutoML is tangential to the experiment conducted.
   **Suggested action:** Cut the entire "Traditional AutoML" paragraph. Merge the citation for AutoGluon-TimeSeries directly into Section 3.1, where the Chronos-2 implementation is discussed. Begin Section 2.3 directly with the subsection "LLM-guided agentic search," which provides the immediate theoretical foundation for the study.[1, 8]
   **Estimated savings:** ~130 words.

4. **Location:** Section 2.2 (Foundation models for time series), Paragraph 3.
   **Issue:** Over-reviewing alternative architectures that are not utilized in the study. Providing intricate architectural details for TimesFM, Lag-Llama, MOIRAI, Time-LLM, and PromptCast dilutes the focus.[1] While it is important to acknowledge the broader ecosystem of time series foundation models, explaining patch-level tokenization or LLaMA-based decoders when the paper exclusively utilizes Chronos-2 is unnecessary padding.
   **Suggested action:** Reduce this extensive paragraph to a single sentence noting that Chronos-2 belongs to a broader class of emerging time series foundation models, citing the others in a single consolidated bracket (e.g., ""). Remove all detailed explanations of their internal architectures.
   **Estimated savings:** ~120 words.

5. **Location:** Section 5.3 (Test-era evaluation) and Section 5.4 (Subperiod analysis).
   **Issue:** Redundant prose repeating data already clearly visible in Tables 4 and 5. Academic writing must highlight trends, meaning, and anomalies, not recite table contents line-by-line.[6, 10] Phrasing such as "with MASE reaching 1.205 at h=12" or "average RMSE of 3.011 at h=12" is entirely redundant when the reader can simply look at the adjacent table.[1, 6]
   **Suggested action:** Remove sentences that simply restate MASE or RMSE values from the text. Instead, use the narrative strictly to interpret the *meaning* of the tables—specifically analyzing the collapse of the agent-tuned configuration post-COVID and the relative stability of the zero-shot baseline.[6, 11]
   **Estimated savings:** ~180 words.

6. **Location:** Section 6 (Discussion), Paragraphs 1-4.
   **Issue:** Severe overlap with the Results section. The discussion section currently restates the empirical findings (e.g., "The ablation analysis quantifies this precisely: the zero-shot baseline has a validation-to-test gap of only -0.3%") before moving to interpret them.[1] The standard scientific paper format mandates a strict boundary: the Results section handles the "What" (the data and findings), while the Discussion section handles the "So What" (the implications).[10, 11] Mixing them creates circular reading.
   **Suggested action:** Remove all numerical restatements and references to specific MASE gaps from the Discussion. Assume the reader remembers the results presented one page prior. Focus the Discussion entirely on the economic and operational implications of foundation model regularization versus task-specific overfitting.
   **Estimated savings:** ~200 words.

7. **Location:** Section 1 (Introduction), Paragraph 7.
   **Issue:** The standard "roadmap" paragraph ("The remainder of the paper is organized as follows. Section 2 reviews related work...") is increasingly considered obsolete filler in modern, concise econometric writing.[5, 8, 12] 
   **Suggested action:** Delete the final paragraph of the introduction entirely. Clear section headings naturally provide the roadmap for the reader.[8]
   **Estimated savings:** ~45 words.

8. **Location:** Section 7 (Conclusion), Paragraph 2.
   **Issue:** The conclusion currently restates the specific findings (the exact covariates found, the 6.8% MASE reduction, the +14.1% overfitting gap) which were already covered in the Abstract, the Introduction, and the Results.[1] A conclusion should synthesize the broader takeaways, not summarize the abstract.
   **Suggested action:** Delete the second paragraph of the conclusion. Begin the conclusion directly with the implications drawn from the study (currently the third paragraph, starting with "These findings carry four implications...").[6]
   **Estimated savings:** ~110 words.

### Abstract tightness

The current abstract is 185 words. While this is under the standard 200-word limit [13], it can be significantly tightened to deliver a more powerful punch by removing procedural details and focusing directly on the economic tension between validation success and out-of-sample failure.[14]

**Original Abstract:**
"We study whether an LLM-guided search procedure can improve pseudo-real-time forecasts of the Norwegian macroeconomy by selecting covariates, data transformations, and fine-tuning settings for a time series foundation model. Using Chronos-2 (120M parameters) as the backbone, we let an LLM agent iteratively propose pipeline configurations, evaluated on a rolling validation window spanning 2006-2015 with 120 monthly forecast origins. The search discovers an economically interpretable configuration—oil prices, the policy rate, US inflation, and the NOK/EUR exchange rate as covariates, with a 96-month context window—that reduces the mean absolute scaled error by 6.8% relative to the zero-shot baseline. However, when evaluated on the held-out test period (2016-2025), which includes the COVID pandemic and the post-2022 inflation surge, the agent-tuned configuration does not generalize: zero-shot Chronos-2 proves more robust to these structural breaks than both the agent-tuned model and classical baselines. We decompose these results by subperiod and variable, finding that the search overfits to validation-era covariate relationships that break down under regime change. Our findings highlight both the promise and the limitations of automated pipeline optimization for macroeconomic forecasting." [1]

**Suggested Rewrite:**
"This study evaluates whether large language model (LLM)-guided search can optimize foundation model forecasting pipelines for small open economies. Using Chronos-2 to forecast the Norwegian macroeconomy, an LLM agent iteratively explores covariates, transformations, and fine-tuning configurations within a pseudo-real-time rolling validation protocol. The agent successfully discovers an economically interpretable configuration—leveraging oil prices, policy rates, US inflation, and exchange rates—that improves validation-era accuracy by 6.8% over the zero-shot baseline. However, this optimized pipeline fails to generalize during the 2016–2025 test period, which encompasses severe structural breaks including the COVID-19 pandemic and subsequent inflation surges. Subperiod analysis reveals the agent severely overfits to pre-crisis covariate relationships that destabilize under regime change. Conversely, the zero-shot foundation model demonstrates superior robustness to these structural breaks compared to both the agent-tuned pipeline and classical econometric baselines. These findings expose a fundamental tension in automated macroeconomic forecasting: the configurations that maximize performance during stable regimes are inherently fragile during macroeconomic crises."

**Editorial Rationale:**
The rewrite saves approximately 25 words while elevating the academic tone. It removes procedural filler like "(120M parameters)" and "120 monthly forecast origins"—details better left for the methodology section. It replaces passive constructions with active phrasing and strengthens the concluding sentence to emphasize the theoretical contribution (the tension between optimization and robustness) rather than a generic summary.[8, 12, 15]

### Sentences to tighten

The manuscript contains numerous instances of nominalization, passive voice, expletive constructions (e.g., "There is..."), and wordy introductory clauses.[6, 15, 16] The following specific sentences must be rewritten to conform to the precision expected in top econometrics journals.

1. **Original:** "We study whether an LLM-guided search procedure can improve pseudo-real-time forecasts of the Norwegian macroeconomy by selecting covariates, data transformations, and fine-tuning settings for a time series foundation model." [1]
   **Rewrite:** "This study evaluates whether LLM-guided search improves pseudo-real-time Norwegian macroeconomic forecasts by optimizing foundation model covariates, transformations, and fine-tuning."
   **Editorial Rationale:** Eliminates the wordy "We study whether... can improve" and compresses the prepositional phrases. Removing "settings for a time series foundation model" streamlines the sentence without losing meaning.[12, 16]

2. **Original:** "Time series foundation models—large neural networks pretrained on billions of observations from diverse domains—have rapidly entered the forecaster's toolkit." [1]
   **Rewrite:** "Time series foundation models, pretrained on billions of diverse observations, have rapidly entered the forecasting toolkit."
   **Editorial Rationale:** Removes unnecessary em-dashes and redundant terminology ("large neural networks," "forecaster's").

3. **Original:** "Crucially, the choice of a small open economy rather than the United States is deliberate." [1]
   **Rewrite:** "Evaluating a small open economy is deliberate."
   **Editorial Rationale:** The contrast with the US is established in the very next sentence; telegraphing it here is redundant.[6]

4. **Original:** "Most economies in the world are small and open; results from the US—a large, relatively closed economy with stable internal dynamics—would not generalize to them." [1]
   **Rewrite:** "Because most economies are small and open, results from the United States—a large, relatively closed economy—rarely generalize globally."
   **Editorial Rationale:** Combines two distinct clauses into a tighter cause-and-effect structure, eliminating the clunky semicolon.[16]

5. **Original:** "Beyond simply evaluating foundation model performance, we ask whether an automated search procedure can improve the forecasting pipeline." [1]
   **Rewrite:** "We further investigate whether automated search procedures optimize the forecasting pipeline."
   **Editorial Rationale:** Cuts the conversational "Beyond simply evaluating..." and replaces the weak verb "ask" with "investigate".[12, 15]

6. **Original:** "The central challenge in macroeconomic forecasting has been balancing the desire to exploit large information sets against the statistical curse of dimensionality." [1]
   **Rewrite:** "Macroeconomic forecasting inherently balances large information sets against the curse of dimensionality."
   **Editorial Rationale:** Removes the passive "has been balancing the desire to exploit" in favor of a direct, active verb.[16]

7. **Original:** "More recently, machine learning methods have entered macroeconomics as a way to capture non-linearities and complex interactions." [1]
   **Rewrite:** "Machine learning methods increasingly capture non-linearities and complex interactions in macroeconomics."
   **Editorial Rationale:** Eliminates the filler phrase "have entered... as a way to".[15, 16]

8. **Original:** "Rigorous pseudo-out-of-sample evaluation with expanding or rolling windows is the accepted standard for validating macro forecasting models (Clark and McCracken, 2013)." [1]
   **Rewrite:** "Pseudo-out-of-sample evaluation remains the standard for validating macroeconomic forecasts (Clark and McCracken, 2013)."
   **Editorial Rationale:** "Rigorous" is an assumed adjective in academic work. "With expanding or rolling windows" is redundant as this defines out-of-sample evaluation.[12]

9. **Original:** "The tension between zero-shot inference and task-specific fine-tuning is central to applied TSFM work. While zero-shot capabilities are increasingly impressive, fine-tuning on domain-specific data often yields superior results for mission-critical applications (Rasul et al., 2023)." [1]
   **Rewrite:** "While zero-shot foundation models perform well, domain-specific fine-tuning often proves superior for critical applications (Rasul et al., 2023)."
   **Editorial Rationale:** Combines two sentences into one, removing the meta-commentary about what is "central to applied TSFM work".[6]

10. **Original:** "The most directly relevant precedent for our approach is Karpathy's "autoresearch" framework (Karpathy, 2026). It enforces a strict ratchet loop governed by three components..." [1]
    **Rewrite:** "Karpathy's (2026) 'autoresearch' framework provides the precedent for this approach, enforcing a ratchet loop via three components..."
    **Editorial Rationale:** Merges two sentences, turning the second clause into an active participle phrase, saving words and improving flow.[16]

11. **Original:** "In our implementation, all macroeconomic covariates are provided as past covariates only: the model receives historical values up to the forecast origin but no future values. This is critical for pseudo-real-time validity—future values of oil prices, exchange rates, and inflation are not known at the forecast origin." [1]
    **Rewrite:** "To ensure pseudo-real-time validity, the model receives all macroeconomic covariates strictly as past values, reflecting the exact information available at the forecast origin."
    **Editorial Rationale:** Condenses 42 words down to 24 by eliminating the conversational explanation of what a past covariate is.[8, 17]

12. **Original:** "Table 2 reports average MASE across all four target variables on the validation era (2006-2015, 120 origins). MASE values below 1 indicate improvement over the random walk baseline; the random walk equals 1.000 by construction." [1]
    **Rewrite:** "Table 2 reports validation-era average MASE across all targets; values below 1.000 indicate improvement over the random walk."
    **Editorial Rationale:** Consolidates table instructions. The reader knows the validation era dates from the methodology section, and explaining that a random walk equals 1.000 by construction is redundant to anyone familiar with MASE.[6]

13. **Original:** "ARIMA is the strongest classical baseline at h=1 (MASE 0.930), though its advantage narrows at longer horizons and vanishes at h=12." [1]
    **Rewrite:** "ARIMA performs best among classical baselines at h=1 (MASE 0.930), but this advantage vanishes by h=12."
    **Editorial Rationale:** Removes wordy transitional phrases ("though its advantage narrows at longer horizons").[16]

14. **Original:** "Figure 1 visualizes the search trajectory, and Figure 2 shows the covariate discovery timeline. The search converged by approximately iteration 45. The remaining iterations proposed configurations that either matched or worsened the best score." [1]
    **Rewrite:** "The search trajectory (Figure 1) and covariate discovery timeline (Figure 2) converge near iteration 45, after which proposals failed to improve the score."
    **Editorial Rationale:** Merges three choppy sentences into one cohesive thought, placing the figure references efficiently in parentheses.[17]

15. **Original:** "Zero-shot Chronos-2 is the best method on the test era at all horizons, with MASE below 1 at h=1, h=3, and h=6 meaning it beats the random walk. Critically, the agent-tuned configuration is above 1 at all horizons, with MASE reaching 1.205 at h=12." [1]
    **Rewrite:** "Zero-shot Chronos-2 consistently outperforms the random walk at short-to-medium horizons (MASE < 1), whereas the agent-tuned configuration underperforms across all horizons."
    **Editorial Rationale:** Removes the conversational "meaning it beats the random walk" and relies on the reader's understanding of the metric.[12]

16. **Original:** "To understand where the overfitting occurs, we decompose the test era into three subperiods. Table 5 reports average RMSE across targets." [1]
    **Rewrite:** "Table 5 decomposes the test era into three subperiods to isolate the overfitting."
    **Editorial Rationale:** Merges the methodology intent with the table callout, a standard technique for reducing word count in results sections.[17]

17. **Original:** "To understand which component of the search-discovered pipeline drives the test-era deterioration, we trace the search trajectory step by step on the test era. Table 6 reports average MASE for each incremental configuration change." [1]
    **Rewrite:** "Table 6 traces the search trajectory incrementally through the test era to isolate the source of performance deterioration."
    **Editorial Rationale:** Identical logic to the previous example. Do not write "We did X. Table Y shows X." Just write "Table Y shows X".[6, 17]

18. **Original:** "The domain-blind agent converges on a partially overlapping but distinct set: the policy rate and US CPI are re-discovered independently, confirming these as robust macro channels that do not require domain-specific prompting." [1]
    **Rewrite:** "The domain-blind agent independently rediscovers the policy rate and US CPI, confirming them as robust macroeconomic channels."
    **Editorial Rationale:** Removes the clunky setup clause ("converges on a partially overlapping but distinct set") and gets straight to the point.[16]

19. **Original:** "Both agents learned what not to do: transforms on covariates consistently hurt (the model works best with raw levels), additional covariates beyond three or four degraded performance (the curse of dimensionality re-emerges), and aggressive fine-tuning overfits (only conservative LORA with very low learning rates were accepted)." [1]
    **Rewrite:** "Both agents demonstrated that covariate transformations degrade performance, exceeding four covariates introduces dimensionality issues, and aggressive fine-tuning causes overfitting."
    **Editorial Rationale:** Eliminates the conversational framing ("learned what not to do") and the parenthetical asides, formatting the findings as a direct, parallel list.[8, 15]

20. **Original:** "Our most striking finding is that zero-shot Chronos-2 is more robust to structural breaks than both the agent-tuned model and classical ARIMA." [1]
    **Rewrite:** "Zero-shot Chronos-2 exhibits superior robustness to structural breaks compared to both the agent-tuned model and classical ARIMA."
    **Editorial Rationale:** Removes the subjective filler "Our most striking finding is that".[8]

21. **Original:** "This is not a failure of the agent's reasoning (the covariates are sensible) but a fundamental limitation of fixed-window validation in macroeconomics." [1]
    **Rewrite:** "This reflects a fundamental limitation of fixed-window macroeconomic validation rather than flawed agentic reasoning."
    **Editorial Rationale:** Uses an active verb ("reflects") and eliminates the parentheses to create a stronger, more academic sentence structure.[15, 16]

22. **Original:** "The multivariate baselines (VAR, factor model) also underperform. Diebold-Mariano tests (Table 10 in Appendix C) confirm that zero-shot Chronos-2 does not significantly differ from the random walk on the test era." [1]
    **Rewrite:** "Multivariate baselines underperform, while Diebold-Mariano tests indicate zero-shot Chronos-2 does not significantly outperform the random walk out-of-sample (Appendix C, Table 10)."
    **Editorial Rationale:** Smoothly integrates the table callout into the sentence flow and tightens the phrasing.[17]

23. **Original:** "Periodic retuning does not help. Table 4 includes a variant where the agent-tuned model is re-fitted annually (every 12 origins) using the expanding data window. The results are virtually identical to the static fit-once protocol..." [1]
    **Rewrite:** "Periodic annual retuning of the agent-tuned model (Table 4) yields results virtually identical to the static fit-once protocol..."
    **Editorial Rationale:** Consolidates three choppy, conversational sentences into one highly efficient statement.[12]

24. **Original:** "The configuration is economically interpretable: Oil prices, monetary policy, global inflation, and the trade-weighted exchange rate are precisely the variables a macroeconomist would expect to matter for a small open oil-exporting economy." [1]
    **Rewrite:** "The discovered configuration is economically interpretable, selecting exactly the variables expected to drive a small, open, oil-exporting economy: oil prices, monetary policy, global inflation, and exchange rates."
    **Editorial Rationale:** Reorders the sentence to put the main point first, followed by the specific list, improving logical flow.[16]

25. **Original:** "The search successfully identifies interpretable configurations—a task that would be tedious for a human researcher to perform exhaustively—but the discovered pipeline overfits when evaluated across regime changes." [1]
    **Rewrite:** "While the search efficiently identifies interpretable configurations, the resulting pipeline overfits across regime changes."
    **Editorial Rationale:** Removes the conversational aside ("a task that would be tedious...") which adds no scientific value to the conclusion.[8]

### Structural suggestions

Beyond sentence-level edits and direct cuts, the manuscript requires macro-level structural reorganization to optimize space and improve the logical flow of data. The following recommendations address how data is visualized and how sections are delineated.

#### 1. Combine Tables 2 and 4 (Validation vs. Test Era MASE)
Currently, Table 2 (Validation era) and Table 4 (Test era) consume redundant vertical space by listing the exact same methodologies and baselines twice.[1] This forces the reader to flip back and forth between pages to assess the generalization gap. 

These should be merged into a single comprehensive table titled "Validation vs. Test Era Performance (Average MASE)." Use grouped columns: one main column group for "Validation Era (2006-2015)" with sub-columns for h=1, 3, 6, 12, and an adjacent main column group for "Test Era (2016-2025)" with identical sub-columns.[17, 18] This allows for an instant horizontal comparison of how each model degrades out-of-sample, drastically reducing the required text to explain the phenomenon.

#### 2. Streamline Diebold-Mariano Test Reporting
In Section 5.3, an entire paragraph is dedicated to narrating the Diebold-Mariano test results, which are subsequently hosted in Table 10 in Appendix C.[1] This is highly inefficient. 

Standard practice in applied econometrics is to append statistical significance asterisks (*, **, ***) directly to the primary performance metrics in the main tables.[19, 20, 21, 22] Move the Diebold-Mariano results into the newly merged Validation/Test MASE table proposed above. Add a footnote to the table explaining the asterisks (e.g., "*, **, *** indicate significant differences from the random walk baseline at the 10%, 5%, and 1% levels, respectively, using the Diebold-Mariano test with Newey-West standard errors"). This allows you to delete Table 10 entirely and remove the narrative paragraph from Section 5.3.[6, 17]

#### 3. Transform the Ablation "Scissors" Plot and Table
The ablation analysis (Section 5.5) represents the most critical intellectual contribution of the paper—proving that incremental optimization actively harms out-of-sample robustness.[1] However, dedicating both Table 6 and Figure 4 to presenting the exact same validation-to-test gap data is a poor use of space.[6, 17] 

These elements must be unified into a single, high-impact composite visual. A split-pane layout that pairs the precise numerical tabular data on the left with a diverging line chart on the right creates a single, undeniable focal point for the paper's core scientific contribution.

http://googleusercontent.com/assisted_ui_content/1 

#### 4. Move Baseline Specifications to the Appendix
Section 4.4 lists the seven baselines utilized in the study (Random
