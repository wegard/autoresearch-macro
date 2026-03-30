# Revision Plan — Round 3 (Writing & Concision)

Based on two AI referee reports (Gemini-DR, GPT-Pro). Both confirm the paper is methodologically sound but needs 15-20% trimming. The main problems: redundancy across sections, over-catalogued literature review, and results narrating what's already in the tables.

**Target: cut ~1,500 words + consolidate 2 tables + remove 2 figures.**

---

## Tier 1: Highest-impact cuts (both referees agree)

### C1. Cut Section 2 (Literature Review) from ~1,450 to ~900 words

The biggest single cut. Three specific actions:

**a) Delete "Factor models" and "ML for macro" paragraphs** (Section 2.1, paragraphs 1-2). These are textbook-level reviews of Stock & Watson, Bayesian VARs, and Random Forests. The IJF audience knows this. Keep only the "Mixed-frequency" and "Norwegian economy" paragraphs.

**Savings: ~250 words**

**b) Compress "Alternative architectures" paragraph** (Section 2.2, paragraph 3). Currently lists TimesFM, Lag-Llama, MOIRAI, Time-LLM, PromptCast with architectural details. Reduce to one sentence: "Chronos-2 belongs to a broader class of TSFMs including TimesFM, Lag-Llama, and MOIRAI, each with distinct architectural choices."

**Savings: ~120 words**

**c) Delete "Traditional AutoML" paragraph** (Section 2.3, paragraph 1). Auto-sklearn, successive halving, NAS — tangential. Start Section 2.3 directly with "LLM-guided agentic search."

**Savings: ~130 words**

### C2. Rewrite Discussion (Section 6) as interpretation only

Currently restates numerical findings before interpreting them. Delete ALL numbers from the discussion — assume the reader just read the results.

Specifically:
- "the zero-shot baseline has a validation-to-test gap of only −0.3%" → delete, already in Table 6
- "the policy rate as the single largest source of overfitting (+9.9% gap)" → reference Table 6 instead
- All MASE values in the "zero-shot robustness" paragraph → delete

Keep only the economic interpretation and implications.

**Savings: ~200 words**

### C3. Compress Conclusion (Section 7) to two paragraphs

Currently repeats specific covariates, the 6.8% improvement, and the +14.6% gap — all in the abstract and results. Cut to:
- Paragraph 1: One-sentence headline result + the core tension (validation gains don't survive regime changes)
- Paragraph 2: Two or three implications (not four) + future work compressed to one sentence

Delete the "four implications" enumerated structure.

**Savings: ~150 words**

### C4. Tighten Abstract to ~150 words

Current: ~185 words. Cut procedural details ("120M parameters", "120 monthly forecast origins"). Keep: the tension between validation gains and test-era failure.

Suggested rewrite:
> We test whether LLM-guided search can improve pseudo-real-time forecasts of the Norwegian macroeconomy by choosing covariates, transformations, and fine-tuning settings for Chronos-2. An LLM agent evaluates candidate pipelines on a rolling 2006–2015 validation window. It selects oil prices, the policy rate, US inflation, and the NOK/EUR exchange rate, reducing validation MASE by 6.8% relative to zero-shot Chronos-2. Yet these gains do not generalize to 2016–2025, which includes the pandemic and post-2022 inflation surge: zero-shot Chronos-2 proves more robust than the agent-tuned pipeline and classical baselines. Ablation shows the search overfits to covariate relationships that fail under regime change. Agent-guided search can find economically interpretable pipelines, but its gains are fragile in non-stationary macroeconomic environments.

**Savings: ~35 words**

---

## Tier 2: Structural consolidation

### C5. Combine Tables 2 and 4 into one two-panel table

Currently: separate tables for validation MASE and test MASE. Merge into one table with grouped columns. This eliminates redundant headers, makes the validation→test comparison instant, and reduces narrative needed to connect them.

**Savings: ~0.5 page + narrative text**

### C6. Remove Figures 2 and 3

- **Figure 2** (covariate discovery timeline) shows the same information as Table 3. Cut it.
- **Figure 3** (subperiod bars) shows one slice of Table 5. Cut it.

Keep Figure 1 (search trajectory) and Figure 4 (ablation scissors — the paper's key visual).

**Savings: ~1 page of display space**

### C7. Move Sections 5.6-5.7 to appendix or compress to one paragraph

The domain-blind experiment (5.6) and "what the agent discovers" (5.7) are secondary results that repeat economics already covered in 5.2. Keep one compact paragraph in the main text:

> A domain-blind variant (without Norwegian-specific hints) independently re-discovers the policy rate and US CPI but substitutes the federal funds rate for Brent crude and retains unlimited context — suggesting that domain knowledge biases the search toward oil-specific channels that drive overfitting (Appendix X).

Move Table 7 (search comparison) to appendix.

**Savings: ~250 words**

---

## Tier 3: Sentence-level tightening

Apply throughout the paper. Both referees identified 20-25 specific sentences. Key patterns:

1. **Kill nominalization:** "has been balancing the desire to exploit" → "balances"
2. **Cut meta-commentary:** "Our most striking finding is that" → delete, start with the finding
3. **Merge figure callouts:** "Figure 1 visualizes the trajectory, and Figure 2 shows the timeline. The search converged by iteration 45." → "The search trajectory (Figure 1) converges near iteration 45."
4. **Don't narrate tables:** "Zero-shot Chronos-2 is the best method on the test era at all horizons, with MASE below 1 at h=1, h=3, and h=6" → "Zero-shot Chronos-2 outperforms at all horizons (Table 4)"
5. **Cut conversational asides:** "a task that would be tedious for a human researcher to perform exhaustively" → delete
6. **Delete the roadmap paragraph** at the end of the introduction

**Savings: ~200 words across ~25 sentences**

---

## What NOT to cut (both referees agree)

1. **"This overfitting result is itself a key contribution"** paragraph in the introduction — cleanest statement of intellectual novelty
2. **Publication-lag discipline** (Section 4.2, equation 1) — credibility-enhancing, precise, well-written
3. **Ablation analysis logic** (Section 5.5) — the paper's strongest explanatory result; keep Table 6 and Figure 4 intact

---

## Estimated total reduction

| Action | Words saved | Display saved |
|--------|------------|---------------|
| C1: Cut lit review | ~500 | — |
| C2: Rewrite discussion | ~200 | — |
| C3: Compress conclusion | ~150 | — |
| C4: Tighten abstract | ~35 | — |
| C5: Merge tables 2+4 | ~50 | 0.5 page |
| C6: Remove figs 2+3 | — | 1.0 page |
| C7: Compress 5.6-5.7 | ~250 | — |
| Tier 3: Sentences | ~200 | — |
| **Total** | **~1,385 words** | **~1.5 pages** |

This should achieve roughly **15-18% reduction** from the current ~8,500-word main text, plus 1.5 pages of display space freed.
