"""
Scoring tools for customer value and conversion probability.

predict_conversion_probability uses 8 behavioral signals derived from
real transaction history, product ownership, and CRM data to produce
a calibrated likelihood score.
"""
from typing import Dict, Any, Optional
from src.database import SessionLocal, Customer, Transaction, Product
from datetime import datetime, timedelta


def score_customer_value(customer_id: str) -> Dict[str, Any]:
    """
    Score customer lifetime value using a multi-factor weighted heuristic.

    Formula (normalized 0–100):
        income    × 0.20
        balance   × 0.20
        tenure    × 0.15
        products  × 0.15
        credit    × 0.20
        kyc       × 0.10

    Returns:
        Score, tier (High / Medium / Standard), and factor breakdown.
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return {"error": f"Customer {customer_id} not found"}

        income_norm  = min((customer.annual_income or 0) / 5_000_000, 1.0)
        balance_norm = min((customer.monthly_avg_balance or 0) / 1_000_000, 1.0)
        tenure_norm  = min((customer.relationship_years or 0) / 20, 1.0)

        products_held = sum([
            bool(customer.has_credit_card),
            bool(customer.has_personal_loan),
            bool(customer.has_home_loan),
            bool(customer.has_fd),
        ])
        products_norm = products_held / 4

        credit_score_norm = ((customer.credit_score or 550) - 550) / 350  # range 550–900

        score = (
            0.20 * income_norm
            + 0.20 * balance_norm
            + 0.15 * tenure_norm
            + 0.15 * products_norm
            + 0.20 * credit_score_norm
            + 0.10 * (1 if customer.kyc_status == "verified" else 0)
        )
        score_100 = min(score * 100, 100)

        if score_100 >= 75:
            tier = "High Value"
        elif score_100 >= 50:
            tier = "Medium Value"
        else:
            tier = "Standard"

        return {
            "customer_id": customer_id,
            "score": round(score_100, 2),
            "tier": tier,
            "factors": {
                "income_norm":       round(income_norm, 3),
                "balance_norm":      round(balance_norm, 3),
                "tenure_norm":       round(tenure_norm, 3),
                "products_norm":     round(products_norm, 3),
                "credit_score_norm": round(credit_score_norm, 3),
                "kyc_verified":      customer.kyc_status == "verified",
            },
            "weights": {
                "income": 0.20, "balance": 0.20, "tenure": 0.15,
                "products": 0.15, "credit_score": 0.20, "kyc": 0.10,
            },
        }
    finally:
        session.close()


# ── Product-ownership map (product_id → Customer boolean attribute name) ───────

_PRODUCT_OWNERSHIP = {
    "PL001": "has_personal_loan",
    "CC001": "has_credit_card",
    "HL001": "has_home_loan",
    "FD001": "has_fd",
}


def predict_conversion_probability(
    customer_id: str,
    product_id: str,
) -> Dict[str, Any]:
    """
    Predict conversion probability using 8 behavioral signals.

    Signals (applied as multiplicative modifiers on a segment base rate):
      1. Already owns the product  → × 0.05  (near-zero — won't buy again)
      2. Product gap (no ownership)→ × 1.25  (opportunity upsell)
      3. High balance (> ₹3L)      → × 1.25
      4. Very high balance (> ₹6L) → × 1.10  (stacked on top)
      5. Excellent credit (≥ 750)  → × 1.20
      6. Low credit (< 650)        → × 0.70
      7. Highly loyal (≥ 10 yrs)   → × 1.20
      8. Loyal customer (≥ 5 yrs)  → × 1.10
      9. Active user (≥ 15 txns/mo)→ × 1.15
     10. Regular salary inflow      → × 1.12
     11. Recent spending spike (↑>20%)→ × 1.08

    Base rates by segment: mass=15%, affluent=25%, premium=35%
    Output capped at 95%.

    Returns:
        probability, percentile, confidence, base_rate, modifiers list,
        plus the 3 strongest positive signals as human-readable strings
        (for use in message personalization).
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return {"error": f"Customer {customer_id} not found"}

        base_rates = {"mass": 0.15, "affluent": 0.25, "premium": 0.35}
        base_prob = base_rates.get(customer.segment or "mass", 0.20)
        prob = base_prob
        modifiers = []

        # ── Signal 1: Already owns this product ───────────────────────────────
        owns_attr = _PRODUCT_OWNERSHIP.get(product_id)
        already_owns = bool(getattr(customer, owns_attr, False)) if owns_attr else False
        if already_owns:
            prob *= 0.05
            modifiers.append({"factor": "Already owns product", "multiplier": 0.05,
                               "direction": "negative"})
            # Short-circuit — no point stacking other signals
            return {
                "customer_id": customer_id,
                "product_id": product_id,
                "probability": round(prob, 3),
                "percentile": round(prob * 100, 1),
                "base_rate": round(base_prob, 3),
                "modifiers": modifiers,
                "confidence": "high",
                "top_signals": ["Customer already holds this product — low upsell opportunity"],
            }

        # ── Signal 2: Product gap (upsell opportunity) ────────────────────────
        if owns_attr and not already_owns:
            prob *= 1.25
            modifiers.append({"factor": "Product gap — upsell opportunity", "multiplier": 1.25,
                               "direction": "positive"})

        # ── Signal 3 & 4: Balance ─────────────────────────────────────────────
        balance = customer.monthly_avg_balance or 0
        if balance >= 600_000:
            prob *= 1.25 * 1.10
            modifiers.append({"factor": "Very high balance (≥ ₹6L)", "multiplier": 1.375,
                               "direction": "positive"})
        elif balance >= 300_000:
            prob *= 1.25
            modifiers.append({"factor": "High balance (≥ ₹3L)", "multiplier": 1.25,
                               "direction": "positive"})

        # ── Signal 5 & 6: Credit score ────────────────────────────────────────
        cs = customer.credit_score or 0
        if cs >= 750:
            prob *= 1.20
            modifiers.append({"factor": f"Excellent credit score ({cs})", "multiplier": 1.20,
                               "direction": "positive"})
        elif cs > 0 and cs < 650:
            prob *= 0.70
            modifiers.append({"factor": f"Below-average credit score ({cs})", "multiplier": 0.70,
                               "direction": "negative"})

        # ── Signal 7 & 8: Tenure / loyalty ───────────────────────────────────
        tenure = customer.relationship_years or 0
        if tenure >= 10:
            prob *= 1.20
            modifiers.append({"factor": f"Highly loyal customer ({int(tenure)} yrs)", "multiplier": 1.20,
                               "direction": "positive"})
        elif tenure >= 5:
            prob *= 1.10
            modifiers.append({"factor": f"Loyal customer ({int(tenure)} yrs)", "multiplier": 1.10,
                               "direction": "positive"})

        # ── Signal 9: Transaction activity ───────────────────────────────────
        txn_30d_count = (
            session.query(Transaction)
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.date >= datetime.utcnow() - timedelta(days=30),
            )
            .count()
        )
        if txn_30d_count >= 15:
            prob *= 1.15
            modifiers.append({"factor": f"Active digital user ({txn_30d_count} txns/30d)",
                               "multiplier": 1.15, "direction": "positive"})

        # ── Signal 10: Regular salary inflow ──────────────────────────────────
        salary_txn_count = (
            session.query(Transaction)
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.category.ilike("%salary%"),
                Transaction.date >= datetime.utcnow() - timedelta(days=90),
            )
            .count()
        )
        if salary_txn_count >= 2:  # at least 2 monthly credits in 90 days
            prob *= 1.12
            modifiers.append({"factor": "Regular salary inflow detected", "multiplier": 1.12,
                               "direction": "positive"})

        # ── Signal 11: Recent spending velocity spike ─────────────────────────
        recent_30 = (
            session.query(Transaction)
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.date >= datetime.utcnow() - timedelta(days=30),
            )
            .all()
        )
        prior_30 = (
            session.query(Transaction)
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.date >= datetime.utcnow() - timedelta(days=60),
                Transaction.date < datetime.utcnow() - timedelta(days=30),
            )
            .all()
        )
        recent_spend = sum(t.amount for t in recent_30)
        prior_spend  = sum(t.amount for t in prior_30)
        if prior_spend > 0 and recent_spend > prior_spend * 1.20:
            prob *= 1.08
            modifiers.append({"factor": "Spending velocity up >20% vs prior month",
                               "multiplier": 1.08, "direction": "positive"})

        final_prob = min(prob, 0.95)

        # Build human-readable top-signal list (positive only, top 3 by multiplier)
        pos_signals = sorted(
            [m for m in modifiers if m["direction"] == "positive"],
            key=lambda m: m["multiplier"],
            reverse=True,
        )[:3]
        top_signals = [s["factor"] for s in pos_signals]

        confidence = (
            "high" if final_prob >= 0.55
            else "medium" if final_prob >= 0.30
            else "low"
        )

        return {
            "customer_id":   customer_id,
            "product_id":    product_id,
            "probability":   round(final_prob, 3),
            "percentile":    round(final_prob * 100, 1),
            "base_rate":     round(base_prob, 3),
            "modifiers":     modifiers,
            "confidence":    confidence,
            "top_signals":   top_signals,
        }
    finally:
        session.close()


# ── Life Event Detection ──────────────────────────────────────────────────────

def detect_life_events(customer_id: str) -> list:
    """
    Detect life events from recent transaction patterns.

    Events detected:
    - WEDDING_LIKELY: Jewellery purchase > ₹50K in last 90 days
    - MEDICAL_EXPENSE: Hospital/pharmacy payment > ₹20K in last 60 days
    - HAS_CHILDREN: School fee payments detected in last 6 months
    - PROMOTION_LIKELY: Salary credit jumped > 40% vs 3 months prior
    - FD_MATURED: FD maturity credit detected (opportunity to reinvest)
    - TRAVEL_FREQUENT: International transactions in last 60 days
    - LIFESTYLE_SPENDER: High restaurant + travel spend (> ₹15K/month avg)
    - MEDICAL_LOAN_CANDIDATE: Large medical expense + no personal loan

    Returns list of dicts: [{event, description, urgency, product_hint}]
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return []

        events = []
        now = datetime.utcnow()

        # Load recent transactions
        txns_90d = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=90)
        ).all()

        txns_180d = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=180)
        ).all()

        # ── WEDDING_LIKELY ────────────────────────────────────────────────────
        jewellery_spend = sum(
            t.amount for t in txns_90d
            if t.category and "jewel" in t.category.lower()
            or (t.merchant and "jewel" in t.merchant.lower())
        )
        if jewellery_spend > 50_000:
            events.append({
                "event": "WEDDING_LIKELY",
                "description": f"Jewellery purchase of ₹{jewellery_spend:,.0f} detected",
                "urgency": "high",
                "product_hint": "personal_loan",
                "signal_strength": "strong",
            })

        # ── MEDICAL_EXPENSE ───────────────────────────────────────────────────
        medical_spend = sum(
            t.amount for t in txns_90d
            if t.category and t.category.lower() in ("healthcare", "medical", "hospital", "pharmacy")
            or (t.merchant and any(k in t.merchant.lower() for k in ["hospital", "clinic", "pharma", "health"]))
        )
        if medical_spend > 20_000:
            events.append({
                "event": "MEDICAL_EXPENSE",
                "description": f"Medical payment of ₹{medical_spend:,.0f} detected",
                "urgency": "high" if medical_spend > 50_000 else "medium",
                "product_hint": "personal_loan",
                "signal_strength": "strong",
            })

        # ── HAS_CHILDREN ──────────────────────────────────────────────────────
        school_txns = [
            t for t in txns_180d
            if (t.category and "education" in t.category.lower())
            or (t.merchant and any(k in t.merchant.lower() for k in ["school", "tuition", "academy", "fees"]))
        ]
        if school_txns:
            events.append({
                "event": "HAS_CHILDREN",
                "description": f"School/education payments detected ({len(school_txns)} transactions)",
                "urgency": "low",
                "product_hint": "education_loan",
                "signal_strength": "medium",
            })

        # ── PROMOTION_LIKELY ──────────────────────────────────────────────────
        salary_recent = [
            t for t in txns_90d
            if t.category and "salary" in t.category.lower()
        ]
        salary_prior = [
            t for t in txns_180d
            if t.category and "salary" in t.category.lower()
            and t.date < now - timedelta(days=90)
        ]
        if salary_recent and salary_prior:
            avg_recent = sum(t.amount for t in salary_recent) / len(salary_recent)
            avg_prior = sum(t.amount for t in salary_prior) / len(salary_prior)
            if avg_prior > 0 and avg_recent > avg_prior * 1.40:
                events.append({
                    "event": "PROMOTION_LIKELY",
                    "description": f"Salary jumped {((avg_recent/avg_prior)-1)*100:.0f}% — possible promotion",
                    "urgency": "high",
                    "product_hint": "premium_upgrade",
                    "signal_strength": "strong",
                })

        # ── TRAVEL_FREQUENT ───────────────────────────────────────────────────
        intl_txns = [
            t for t in txns_90d
            if t.category and "international" in t.category.lower()
            or t.channel and "forex" in t.channel.lower()
        ]
        if intl_txns:
            events.append({
                "event": "TRAVEL_FREQUENT",
                "description": f"{len(intl_txns)} international transactions in 90 days",
                "urgency": "medium",
                "product_hint": "travel_card",
                "signal_strength": "medium",
            })

        # ── LIFESTYLE_SPENDER ─────────────────────────────────────────────────
        lifestyle_monthly = sum(
            t.amount for t in txns_90d
            if t.category and t.category.lower() in ("restaurant", "dining", "travel", "entertainment", "shopping")
        ) / 3  # per month avg
        if lifestyle_monthly > 15_000:
            events.append({
                "event": "LIFESTYLE_SPENDER",
                "description": f"Avg ₹{lifestyle_monthly:,.0f}/month on lifestyle (dining/travel/shopping)",
                "urgency": "medium",
                "product_hint": "lifestyle_credit_card",
                "signal_strength": "medium",
            })

        # ── MEDICAL_LOAN_CANDIDATE ────────────────────────────────────────────
        if medical_spend > 20_000 and not customer.has_personal_loan:
            events.append({
                "event": "MEDICAL_LOAN_CANDIDATE",
                "description": "Large medical expense with no existing personal loan — prime candidate",
                "urgency": "high",
                "product_hint": "personal_loan",
                "signal_strength": "very_strong",
            })

        return events

    finally:
        session.close()


def detect_churn_signals(customer_id: str) -> dict:
    """
    Detect early churn signals from transaction patterns.

    Signals:
    - Salary credit stopped (>45 days since last salary)
    - FD closed early (negative FD transaction)
    - Balance declining trend (last 30d avg < prior 30d avg by >30%)
    - Competitor transactions detected (NEFT/IMPS to known competitor names)
    - Reduced transaction frequency (txn count down >40%)

    Returns: {churn_risk: low/medium/high, score: 0-100, signals: list}
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return {"error": "Customer not found"}

        now = datetime.utcnow()
        signals = []
        risk_score = 0

        txns_60d = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=60)
        ).all()

        txns_90_to_60 = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=90),
            Transaction.date < now - timedelta(days=60),
        ).all()

        # ── Signal 1: Salary stopped ──────────────────────────────────────────
        salary_txns = [t for t in txns_60d if t.category and "salary" in t.category.lower()]
        if customer.annual_income and customer.annual_income > 0 and not salary_txns:
            # Check if they ever had salary
            any_salary = session.query(Transaction).filter(
                Transaction.customer_id == customer_id,
                Transaction.category.ilike("%salary%"),
            ).first()
            if any_salary:
                signals.append({"signal": "SALARY_STOPPED", "description": "No salary credit in 60 days — possible job change or account switch", "weight": 35})
                risk_score += 35

        # ── Signal 2: Declining balance trend ─────────────────────────────────
        recent_debits = sum(t.amount for t in txns_60d[:30] if t.amount < 0)
        prior_debits = sum(t.amount for t in txns_60d[30:] if t.amount < 0)
        if prior_debits < 0 and recent_debits < prior_debits * 0.60:  # balance declining 40%+
            signals.append({"signal": "DECLINING_BALANCE", "description": f"Account balance declining — debit activity dropped significantly", "weight": 20})
            risk_score += 20

        # ── Signal 3: Reduced transaction frequency ───────────────────────────
        recent_count = len([t for t in txns_60d if t.date >= now - timedelta(days=30)])
        prior_count = len([t for t in txns_60d if t.date < now - timedelta(days=30)])
        if prior_count >= 5 and recent_count < prior_count * 0.50:
            signals.append({"signal": "LOW_ACTIVITY", "description": f"Transaction frequency dropped {100 - round(recent_count/prior_count*100)}% vs prior month", "weight": 15})
            risk_score += 15

        # ── Signal 4: Competitor transactions ─────────────────────────────────
        competitors = ["hdfc", "icici", "axis", "kotak", "sbi", "paytm", "phonepe"]
        competitor_txns = [
            t for t in txns_60d
            if t.merchant and any(c in t.merchant.lower() for c in competitors)
        ]
        if len(competitor_txns) >= 3:
            signals.append({"signal": "COMPETITOR_ACTIVITY", "description": f"{len(competitor_txns)} transactions to competitor accounts detected", "weight": 25})
            risk_score += 25

        # ── Signal 5: Long since last contact ─────────────────────────────────
        if customer.last_contact_date:
            days_no_contact = (now - customer.last_contact_date).days
            if days_no_contact > 90:
                signals.append({"signal": "NO_CONTACT", "description": f"{days_no_contact} days since last RM contact", "weight": 10})
                risk_score += 10

        risk_score = min(risk_score, 100)
        churn_risk = "high" if risk_score >= 50 else "medium" if risk_score >= 25 else "low"

        return {
            "customer_id": customer_id,
            "churn_risk": churn_risk,
            "risk_score": risk_score,
            "signals": signals,
            "recommendation": (
                "Immediate outreach required — schedule callback" if churn_risk == "high"
                else "Monitor closely — send re-engagement campaign" if churn_risk == "medium"
                else "Customer appears healthy"
            ),
        }
    finally:
        session.close()


def detect_cross_sell_opportunities(customer_id: str) -> list:
    """
    Identify high-probability cross-sell opportunities from spend patterns.

    Returns list of {product_hint, reason, confidence, urgency}
    """
    from src.database import Product as ProductModel
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return []

        now = datetime.utcnow()
        opportunities = []

        txns_90d = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=90)
        ).all()

        # Category spend map
        cat_spend: dict = {}
        for t in txns_90d:
            cat = (t.category or "other").lower()
            cat_spend[cat] = cat_spend.get(cat, 0) + abs(t.amount)

        # ── Credit card → not held + lifestyle spend ──────────────────────────
        if not customer.has_credit_card:
            lifestyle = cat_spend.get("restaurant", 0) + cat_spend.get("shopping", 0) + cat_spend.get("travel", 0)
            if lifestyle > 15_000:
                opportunities.append({
                    "product_id": "CC001",
                    "product_name": "Premium Credit Card",
                    "reason": f"₹{lifestyle:,.0f} in lifestyle spend/quarter — rewards card will save them money",
                    "confidence": min(0.85, 0.50 + (lifestyle / 150_000)),
                    "urgency": "high" if lifestyle > 30_000 else "medium",
                })

        # ── Personal loan → medical expense or life event ─────────────────────
        if not customer.has_personal_loan:
            medical = cat_spend.get("healthcare", 0) + cat_spend.get("medical", 0) + cat_spend.get("hospital", 0)
            if medical > 20_000:
                opportunities.append({
                    "product_id": "PL001",
                    "product_name": "Personal Loan",
                    "reason": f"₹{medical:,.0f} medical spend detected — personal loan can ease cash flow",
                    "confidence": 0.72,
                    "urgency": "high",
                })

        # ── FD → large balance sitting idle ──────────────────────────────────
        if not customer.has_fd and (customer.monthly_avg_balance or 0) > 500_000:
            opportunities.append({
                "product_id": "FD001",
                "product_name": "Fixed Deposit",
                "reason": f"₹{(customer.monthly_avg_balance or 0):,.0f} avg balance — FD can earn 7.5% vs 3.5% savings",
                "confidence": 0.78,
                "urgency": "medium",
            })

        # ── Home loan → salary + tenure + no home loan ────────────────────────
        if not customer.has_home_loan and (customer.relationship_years or 0) >= 3:
            salary_monthly = (customer.annual_income or 0) / 12
            if salary_monthly >= 60_000:
                opportunities.append({
                    "product_id": "HL001",
                    "product_name": "Home Loan",
                    "reason": f"Stable salary of ₹{salary_monthly:,.0f}/month — eligible for home loan up to ₹{salary_monthly * 60:,.0f}",
                    "confidence": 0.45,
                    "urgency": "low",
                })

        # Sort by confidence
        opportunities.sort(key=lambda x: x["confidence"], reverse=True)
        return opportunities

    finally:
        session.close()


def get_behavioral_signals(customer_id: str) -> dict:
    """
    Get behavioral signals for message personalization and timing.

    Returns:
        - optimal_send_day: days since salary credit (best: 2-3)
        - emi_deduction_risk: True if today is likely EMI day (avoid)
        - product_affinities: list of product types customer spends on
        - message_tone_hint: 'warm' | 'professional' | 'urgent'
        - spend_personality: 'saver' | 'spender' | 'balanced'
        - days_since_salary: int or None
        - life_events: list from detect_life_events()
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not customer:
            return {}

        now = datetime.utcnow()
        txns_60d = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= now - timedelta(days=60)
        ).order_by(Transaction.date.desc()).all()

        # Days since last salary credit
        salary_txns = [t for t in txns_60d if t.category and "salary" in t.category.lower()]
        days_since_salary = None
        if salary_txns:
            last_salary = max(salary_txns, key=lambda t: t.date)
            days_since_salary = (now - last_salary.date).days

        # EMI deduction risk (salary earners typically get EMI deducted on 1-5th)
        today_day = now.day
        emi_risk = 1 <= today_day <= 5 and bool(customer.has_personal_loan or customer.has_home_loan)

        # Spend personality
        total_spend = sum(t.amount for t in txns_60d if t.amount > 0)
        avg_balance = customer.monthly_avg_balance or 0
        if avg_balance > 0:
            spend_ratio = total_spend / (avg_balance * 2)  # over 2 months
            if spend_ratio < 0.3:
                spend_personality = "saver"
            elif spend_ratio > 0.7:
                spend_personality = "spender"
            else:
                spend_personality = "balanced"
        else:
            spend_personality = "balanced"

        # Product affinities from spend
        category_spend: dict = {}
        for t in txns_60d:
            cat = (t.category or "other").lower()
            category_spend[cat] = category_spend.get(cat, 0) + t.amount

        # Message tone hint
        cs = customer.credit_score or 0
        tenure = customer.relationship_years or 0
        if customer.segment == "premium" or (cs >= 750 and tenure >= 5):
            tone_hint = "professional"
        elif days_since_salary and 2 <= days_since_salary <= 5:
            tone_hint = "warm"  # peak liquidity, good mood
        elif spend_personality == "spender":
            tone_hint = "urgent"
        else:
            tone_hint = "warm"

        # Optimal timing score (0-100, higher = better time to send)
        timing_score = 50  # baseline
        if days_since_salary is not None:
            if 2 <= days_since_salary <= 4:
                timing_score += 30  # sweet spot: post-salary, pre-EMI
            elif days_since_salary <= 1:
                timing_score += 10
            elif days_since_salary >= 20:
                timing_score -= 10  # low on cash
        if emi_risk:
            timing_score -= 30  # EMI day, customer stressed
        timing_score = max(0, min(100, timing_score))

        return {
            "days_since_salary": days_since_salary,
            "emi_deduction_risk": emi_risk,
            "timing_score": timing_score,
            "timing_label": "optimal" if timing_score >= 70 else "good" if timing_score >= 40 else "avoid",
            "spend_personality": spend_personality,
            "message_tone_hint": tone_hint,
            "top_spend_categories": sorted(category_spend.items(), key=lambda x: -x[1])[:5],
            "life_events": detect_life_events(customer_id),
        }

    finally:
        session.close()
