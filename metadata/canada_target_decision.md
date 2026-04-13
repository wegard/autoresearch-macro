# Canada Industrial Output Target Decision

## Decision

Use **Monthly GDP at basic prices, all industries** (Statistics Canada Table 36-10-0434-01) as Canada's industrial output target variable.

## Rationale

Per REVISION-PLAN-4 §4.3 decision order:

1. **Preferred (IPI):** Canada does not publish a standalone monthly Industrial Production Index (IPI) comparable to Norway's SSB table 14208 or Sweden's SCB IPI table.

2. **Fallback A (Monthly GDP by industry):** Statistics Canada publishes monthly real GDP at basic prices by industry (Table 36-10-0434-01, product ID 36100434). This is Canada's headline monthly real-activity indicator, widely used by the Bank of Canada and Statistics Canada for short-term economic analysis. The "All industries" aggregate provides a comprehensive measure of monthly economic output at constant prices (chained 2017 dollars), seasonally adjusted at annual rates.

3. **Fallback B:** Not needed — Fallback A is available and appropriate.

## Series details

- **Table:** 36-10-0434-01
- **Product ID:** 36100434
- **Series:** Gross domestic product (GDP) at basic prices, by industry, monthly
- **Filter:** NAICS = "All industries [T001]", Seasonal adjustment = "Seasonally adjusted at annual rates"
- **Unit:** Chained (2017) dollars, millions
- **Frequency:** Monthly
- **Coverage:** 1997-01 to present
- **Publication lag:** ~60 days after reference month

## Comparability note

Norway and Sweden use manufacturing/industrial production indices (narrower scope). Canada's monthly GDP covers all industries (broader scope). This difference is documented and should be noted in the paper. The broader measure is preferred for Canada because: (a) it is the standard real-activity indicator used by Canadian institutions, and (b) no narrower manufacturing index exists at monthly frequency with adequate history.
