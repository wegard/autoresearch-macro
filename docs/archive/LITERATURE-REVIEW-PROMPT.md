# Literature Review Prompt for Deep Research

> Copy the prompt below into Google Deep Research (or similar). Use the output to populate references.bib and draft the literature review section.

---

## Prompt

I am writing an academic paper on **automated feature engineering for macroeconomic forecasting using time series foundation models**. The paper studies whether an agentic search procedure (inspired by Karpathy's "autoresearch" framework) can improve pseudo-real-time forecasts of the Norwegian macroeconomy by automatically selecting data representations, covariates, transformations, and fine-tuning settings for foundation models like Chronos-2.

I need a comprehensive literature review covering three strands. For each strand, identify the most important and most-cited papers, plus recent working papers and preprints from 2023-2026 that a reviewer would expect to see cited. Prioritize papers published in top economics journals (Econometrica, AER, QJE, REStud, JoE, JMCB, JAE, IER) and top ML venues (NeurIPS, ICML, ICLR, AAAI, JMLR). Include working papers from NBER, CEPR, CESifo, BIS, ECB, and central bank series where relevant.

### Strand 1: Macroeconomic forecasting

Key topics to cover:
- Factor models and diffusion indexes for macro forecasting (Stock & Watson, Forni et al.)
- Bayesian VAR methods for large macro panels (Bańbura, Giannone & Reichlin; Koop & Korobilis)
- Mixed-frequency and nowcasting methods (MIDAS, bridge equations, Giannone et al.)
- Machine learning for macro forecasting (Medeiros et al., Coulombe et al., Goulet Coulombe, Babii et al.)
- Real-time data and publication lag issues in macro forecasting
- Forecasting the Norwegian economy specifically (Norges Bank work, Bjørnland, Aastveit et al.)
- Forecast combination and model averaging
- Evaluation methodology: rolling windows, pseudo-out-of-sample, Diebold-Mariano tests
- Density/probabilistic forecasting in macroeconomics

### Strand 2: Foundation models for time series

Key topics to cover:
- Chronos and Chronos-2 (Amazon): architecture, zero-shot performance, covariate handling, fine-tuning
- TimesFM (Google): decoder-only foundation model for forecasting
- Lag-Llama: open-source LLM for probabilistic time series forecasting
- MOIRAI / TimeGEN / other foundation models for time series (2023-2026)
- LLMs applied to time series: Time-LLM, GPT4MTS, PromptCast, UniTime
- Transfer learning and zero-shot vs fine-tuning for time series
- Comparison studies: foundation models vs classical methods for forecasting
- Tokenization strategies for continuous time series data
- Pre-training on heterogeneous time series corpora

### Strand 3: Automated machine learning and agentic search

Key topics to cover:
- AutoML: Auto-WEKA, Auto-sklearn, AutoGluon, H2O
- Neural architecture search (NAS): key papers and connection to our outer-loop approach
- Automated feature engineering: specifically for tabular/time series data
- Hyperparameter optimization: Bayesian optimization, random search, successive halving
- LLM-guided/agentic approaches to ML experimentation (2024-2026 papers)
- Karpathy's autoresearch (March 2026) — describe the framework and any follow-up work
- The "AI scientist" concept and automated research (Lu et al. 2024, Sakana AI)
- Automated data augmentation and transformation search
- Reproducibility and interpretability concerns in automated ML

### Additional context

Our specific setup:
- **Application domain:** Small open commodity-exporting economy (Norway), monthly macro panel
- **Method:** An outer-loop agent searches over covariate selection, data transformations, fine-tuning configurations for Chronos-2, scored via rolling pseudo-out-of-sample validation
- **Key contribution:** Three-way decomposition of forecast gains: (1) foundation model vs classical baselines, (2) fine-tuning vs zero-shot, (3) agentic search vs manual pipeline design
- **Our prior work:** Larsen (2021) "Components of Uncertainty" in International Economic Review — used LDA on Norwegian newspaper text to construct uncertainty measures. The current paper connects by asking whether automated search can discover which indicators (including potentially text-based ones) improve macro forecasts.

### Output format

For each strand, provide:
1. A narrative review (~1000-1500 words per strand) suitable for an academic paper's literature section
2. A table of the 15-20 most important papers per strand, with: authors, year, title, journal/venue, and a one-sentence description of relevance to our paper
3. Key gaps in the literature that our paper addresses
4. Any papers that combine two or more strands (e.g., AutoML for macro forecasting, foundation models for economic data)

For all cited papers, provide complete bibliographic information suitable for BibTeX.
