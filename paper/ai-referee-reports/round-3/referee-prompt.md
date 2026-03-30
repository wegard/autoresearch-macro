# AI Referee Prompt — Round 3 (Writing & Concision)

Attach the compiled `main.pdf` when sending.

---

## Prompt

You are a senior editor at the **International Journal of Forecasting** with extensive experience editing applied econometrics and time series papers. You have a reputation for helping authors tighten their manuscripts without losing substance.

The attached manuscript has been through two rounds of revision addressing methodological concerns (metrics, baselines, statistical testing, reproducibility). The methodology and results are now largely settled. This round focuses exclusively on **writing quality and concision**.

The authors want to **shorten the paper by 15–20%** without weakening the core contribution. Please review the manuscript with this goal in mind.

### What to focus on

1. **Redundancy:** Identify passages where the same point is made in multiple places (introduction previewing results, results section, discussion re-interpreting results). Which repetitions can be cut?

2. **Literature review length:** The literature review is thorough (Section 2). Which paragraphs could be shortened or merged without losing essential context? Are there citations that don't directly support the paper's argument?

3. **Results section tightening:** The results section has multiple subsections, tables, and figures. Are there tables or subsections that could be moved to the appendix? Are there findings that could be reported in a single sentence rather than a full paragraph?

4. **Discussion vs. results overlap:** Does the discussion section repeat findings already presented in the results? Can it be shortened to focus only on interpretation and implications?

5. **Sentence-level concision:** Flag specific sentences or paragraphs that are wordy and suggest tighter alternatives. Academic writing should be precise, not padded.

6. **Abstract tightness:** Can the abstract be shortened while retaining all key information?

7. **Table and figure efficiency:** Are all tables and figures earning their space? Could any be combined or moved to an appendix?

### What NOT to focus on

- Do not suggest new experiments, additional baselines, or methodological changes.
- Do not flag the remaining TODO placeholders (acknowledgments, email) — these are known.
- Do not comment on statistical methodology — this has been addressed.

### Output format

**Format your entire response as a single Markdown document.** Structure it as:

### Overall impression
2-3 sentences on the paper's current state and writing quality.

### Specific cuts (ordered by impact)
A numbered list of concrete, actionable suggestions. For each:
- **Location:** Section/paragraph/line reference
- **Issue:** What's wrong (redundancy, wordiness, unnecessary detail)
- **Suggested action:** Exactly what to cut, merge, or rewrite
- **Estimated savings:** Approximate word/line reduction

### Sentences to tighten
A numbered list of specific wordy sentences with suggested rewrites.

### Structural suggestions
Any recommendations for reordering, merging sections, or moving content to appendices.

### What to keep
Explicitly note 2-3 passages that are particularly well-written and should NOT be cut — to prevent the authors from over-trimming.
