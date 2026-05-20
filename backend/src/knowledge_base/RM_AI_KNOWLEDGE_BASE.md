# RM AI Workspace — Knowledge Base
**Version**: 1.0 | **Scope**: All banking products | **Updated**: 2026-05

This knowledge base is loaded by the RM AI agent at runtime. It defines eligibility rules,
assessment formats, verdict logic, and auto-suggest behaviour for every product.
Each product section is **independent** — eligibility for one product never influences another.

---

## PRODUCTS IN SCOPE

| Product ID | Name             | Rate     | Min CIBIL | Min Income (Annual) |
|------------|------------------|----------|-----------|----------------------|
| PL001      | Personal Loan    | 10.5% pa | 650       | ₹3,00,000           |
| CC001      | Premium Credit Card | —     | 700       | ₹4,00,000           |
| HL001      | Home Loan        | 7.2% pa  | 700       | ₹3,00,000 (salaried) / ₹4,80,000 (self-employed) |
| FD001      | Fixed Deposit    | 6.0% pa  | —         | No minimum          |

---

## GLOBAL RULES (apply to all products)

1. Each product eligibility check is **always a separate, independent call**.
2. Never carry over pass/fail from one product to another.
3. If any data field is missing → mark that criterion **⚠️ Marginal** with note: *"Data unavailable — manual verification required."*
4. Always show a recommended amount/limit range — even for conditional verdicts (use conservative estimate).
5. Run **Auto-Suggest** for Home Loan whenever any other product is evaluated (see HL001 section).

---

## PRODUCT: PL001 — Personal Loan

### Eligibility Criteria
| # | Criterion        | Condition                                                    |
|---|------------------|--------------------------------------------------------------|
| 1 | Income           | Annual income ≥ ₹3,00,000 (monthly ≥ ₹25,000)             |
| 2 | CIBIL Score      | ≥ 700 → ✅ / 650–699 → ⚠️ / <650 → ❌                    |
| 3 | Age              | 21–60 years                                                  |
| 4 | Existing Loans   | FOIR ≤ 50% of monthly income                                 |
| 5 | Employment       | Salaried: 1+ year / Self-employed: 2+ years                  |

### Verdict Logic
- **ELIGIBLE** — All criteria ✅
- **CONDITIONALLY ELIGIBLE** — CIBIL ⚠️ (650–699), rest ✅
- **NOT ELIGIBLE** — CIBIL ❌ or Income ❌ or FOIR > 60%

### Loan Amount Formula
- Max EMI = (Monthly Income × 0.50) − Existing EMIs
- Max Loan = Max EMI × tenure multiplier (60 months at 10.5%)
- Typical range: ₹1L – ₹25L

### Output Format
```
PERSONAL LOAN ELIGIBILITY — [Customer Name] | [Date]
VERDICT: ELIGIBLE / CONDITIONALLY ELIGIBLE / NOT ELIGIBLE

  ✅/❌/⚠️  Income       — ₹[monthly] — Pass/Fail/Marginal
  ✅/❌/⚠️  CIBIL Score  — [score]    — Pass/Fail/Marginal
  ✅/❌/⚠️  Age          — [age] yrs  — Pass/Fail/Marginal
  ✅/❌/⚠️  FOIR         — [%]%       — Pass/Fail/Marginal
  ✅/❌/⚠️  Employment   — [tenure]   — Pass/Fail/Marginal

RECOMMENDED AMOUNT: ₹[min] – ₹[max]
NOTE: Indicative. Subject to underwriting and document verification.
```

---

## PRODUCT: CC001 — Premium Credit Card

### Eligibility Criteria
| # | Criterion        | Condition                                                    |
|---|------------------|--------------------------------------------------------------|
| 1 | Income           | Annual income ≥ ₹4,00,000 (monthly ≥ ₹33,333)             |
| 2 | CIBIL Score      | ≥ 750 → ✅ / 700–749 → ⚠️ / <700 → ❌                    |
| 3 | Age              | 21–65 years                                                  |
| 4 | Existing Cards   | No more than 3 active credit cards                           |
| 5 | KYC              | Must be verified                                             |

### Verdict Logic
- **ELIGIBLE** — All criteria ✅
- **CONDITIONALLY ELIGIBLE** — CIBIL ⚠️ (700–749), rest ✅ → issue with lower credit limit
- **NOT ELIGIBLE** — CIBIL < 700 or Income < ₹4L or KYC pending

### Credit Limit Formula
- Starting limit: 2× monthly income (capped at ₹5L for new issuance)
- Premium tier (income > ₹10L): up to ₹10L

### Output Format
```
CREDIT CARD ELIGIBILITY — [Customer Name] | [Date]
VERDICT: ELIGIBLE / CONDITIONALLY ELIGIBLE / NOT ELIGIBLE

  ✅/❌/⚠️  Income       — ₹[monthly] — Pass/Fail/Marginal
  ✅/❌/⚠️  CIBIL Score  — [score]    — Pass/Fail/Marginal
  ✅/❌/⚠️  Age          — [age] yrs  — Pass/Fail/Marginal
  ✅/❌/⚠️  Existing Cards — [count]  — Pass/Fail/Marginal
  ✅/❌/⚠️  KYC          — [status]   — Pass/Fail/Marginal

RECOMMENDED CREDIT LIMIT: ₹[min] – ₹[max]
NOTE: Indicative. Subject to credit policy and document verification.
```

---

## PRODUCT: HL001 — Home Loan ⭐

> **Auto-Suggest Rule**: Whenever ANY other product is evaluated for a customer,
> silently run a parallel Home Loan eligibility check. If eligible, surface:
> 💡 *"This customer may also qualify for a Home Loan. [View Home Loan Assessment]"*

### What Data to Use
| Field                    | Source in DB                          |
|--------------------------|---------------------------------------|
| Monthly Income           | `annual_income / 12`                  |
| CIBIL Score              | `credit_score`                        |
| Existing EMI Obligations | `existing_emi` (monthly, in ₹)        |
| Employment Type          | `employment_type` (salaried/self_employed) |
| Employment Tenure        | `employment_tenure_years`             |
| Age                      | `age`                                 |
| Property City            | `city` (mapped to approved zone list) |

### Eligibility Criteria
Evaluate each criterion **independently**. Tag as ✅ Pass / ❌ Fail / ⚠️ Marginal.

| # | Criterion          | Condition                                                                 |
|---|--------------------|---------------------------------------------------------------------------|
| 1 | Minimum Income     | Monthly net ≥ ₹25,000 (salaried) → ✅ / ₹40,000 (self-employed) → ✅   |
| 2 | CIBIL Score        | ≥ 700 → ✅ / 650–699 → ⚠️ / <650 → ❌                                 |
| 3 | FOIR               | (Existing EMI + Proposed EMI) / Monthly Income ≤ 50% → ✅ / 50–55% → ⚠️ / >55% → ❌ |
| 4 | Age                | 21–58 at loan start / loan must mature before age 65 → ✅ / >58 → ⚠️ / >63 → ❌ |
| 5 | Employment Stability | Salaried: ≥ 2 yrs total + 6 months current / Self-employed: ≥ 3 yrs vintage |
| 6 | Property           | Residential / No disputed title / City in approved zone list              |

### Approved Cities (Zone List)
Mumbai, Delhi, Bangalore, Hyderabad, Chennai, Pune, Kolkata, Ahmedabad, Jaipur, Surat, Nagpur, Noida, Gurgaon, Lucknow, Bhopal

### Verdict Logic
- **ELIGIBLE** — All 6 criteria ✅
- **CONDITIONALLY ELIGIBLE** — ≥ 4 criteria ✅, no ❌ on Income, CIBIL, or Property, rest ⚠️
- **NOT ELIGIBLE** — Any ❌ on Income, CIBIL, or Property (non-approved city), OR 3+ criteria ❌

### Loan Amount Formula
```
Max EMI Capacity  = (Monthly Income × 0.50) − Existing EMI
Loan Tenure       = min(30 years, 65 − customer_age) in years
Tenure Multiplier = EMI factor for 7.2% over tenure (e.g. 30yr → ~149, 20yr → ~117, 10yr → ~70)
Max Loan Amount   = Max EMI Capacity × Tenure Multiplier
Min Loan Amount   = ₹10,00,000 (standard floor)
```

### Output Format
```
HOME LOAN ELIGIBILITY ASSESSMENT
Customer: [Name] | Evaluated on: [Date]

VERDICT: ELIGIBLE / NOT ELIGIBLE / CONDITIONALLY ELIGIBLE

CRITERIA BREAKDOWN:
  ✅/❌/⚠️  Income          — ₹[monthly] (annual ₹[annual]) — Pass/Fail/Marginal
  ✅/❌/⚠️  CIBIL Score     — [score]                       — Pass/Fail/Marginal
  ✅/❌/⚠️  FOIR            — [%]% (EMI ₹[proposed])       — Pass/Fail/Marginal
  ✅/❌/⚠️  Age             — [age] yrs (matures at [age+tenure]) — Pass/Fail/Marginal
  ✅/❌/⚠️  Employment      — [type], [tenure] yrs          — Pass/Fail/Marginal
  ✅/❌/⚠️  Property        — [city] (Approved/Not Approved) — Pass/Fail/Marginal

REASON SUMMARY:
  [2–3 lines: what passed, what failed, any conditions]

RECOMMENDED LOAN AMOUNT RANGE:
  Minimum: ₹10,00,000     Maximum: ₹[calculated]
  Based on: FOIR headroom ₹[max_emi] × [tenure_multiplier] (7.2%, [tenure] yrs)

NOTE: Indicative. Final approval subject to underwriting and document verification.
```

---

## PRODUCT: FD001 — Fixed Deposit

### Eligibility Criteria
| # | Criterion        | Condition                                                    |
|---|------------------|--------------------------------------------------------------|
| 1 | Age              | 18+ years                                                    |
| 2 | KYC              | Verified                                                     |
| 3 | Min Deposit      | ₹10,000                                                      |
| 4 | Account Status   | Active savings/current account with the bank                 |

### Verdict Logic
- **ELIGIBLE** — All criteria ✅ (FD is open to almost all customers)
- **NOT ELIGIBLE** — KYC pending or account not active

### Recommended Amount
- Conservative: 3–6 months of monthly average balance
- Suggested tenure: 1 year (6.0% pa) or 3 years (6.5% pa)

---

## AUTO-SUGGEST BEHAVIOUR

When the agent evaluates **any product** for a customer, it should **always** run Home Loan
eligibility in the background and surface it if the result is ELIGIBLE or CONDITIONALLY ELIGIBLE.

```
After primary product result:
IF home_loan_verdict in ["ELIGIBLE", "CONDITIONALLY ELIGIBLE"]:
    surface → "💡 This customer may also qualify for a Home Loan. [View Home Loan Assessment]"
```

Do NOT surface if verdict is NOT ELIGIBLE. Keep it clean.

---

## EDGE CASES & HANDLING

| Scenario                           | Handling                                                      |
|------------------------------------|---------------------------------------------------------------|
| Age > 58 at loan start             | FOIR ⚠️, shorter tenure, show reduced max loan               |
| CIBIL missing                      | ⚠️ on CIBIL, verdict → CONDITIONALLY ELIGIBLE at best        |
| Self-employed, tenure < 3 yrs      | Employment ❌, likely NOT ELIGIBLE                            |
| FOIR exactly 50%                   | ⚠️ Marginal — borderline, note in summary                    |
| City not in approved zone list     | Property ❌                                                   |
| existing_emi missing               | ⚠️ on FOIR — assume 0 for calculation, flag for verification  |
| income = 0 or null                 | Income ❌, stop — NOT ELIGIBLE                                |
| All 6 ⚠️                          | CONDITIONALLY ELIGIBLE (4 of 6 rule still met with all marginal) |

---

## DEMO CUSTOMERS FOR EDGE CASE TESTING

These customers are pre-loaded in the DB for testing all verdict outcomes:

| Customer ID   | Name              | Expected Verdict         | Key Factor                        |
|---------------|-------------------|--------------------------|-----------------------------------|
| HL_DEMO_001   | Aryan Mehta       | ELIGIBLE                 | All 6 pass                        |
| HL_DEMO_002   | Priya Sharma      | CONDITIONALLY ELIGIBLE   | CIBIL 675 (⚠️)                   |
| HL_DEMO_003   | Ravi Nair         | NOT ELIGIBLE             | CIBIL 620 (❌)                    |
| HL_DEMO_004   | Sunita Rao        | NOT ELIGIBLE             | Income < ₹25,000/month (❌)       |
| HL_DEMO_005   | Deepak Joshi      | CONDITIONALLY ELIGIBLE   | FOIR 52% (⚠️), Age 57 (⚠️)      |
| HL_DEMO_006   | Meena Pillai      | NOT ELIGIBLE             | Age 64, loan matures at 84 (❌)  |
| HL_DEMO_007   | Kartik Singh      | CONDITIONALLY ELIGIBLE   | Employment tenure 1yr (⚠️)       |
| HL_DEMO_008   | Anjali Desai      | NOT ELIGIBLE             | City not in approved list (❌)   |
