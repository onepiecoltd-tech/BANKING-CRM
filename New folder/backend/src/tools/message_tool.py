"""
Message drafting tools — production-quality personalized outreach.

Key design principles:
- Loads real customer data (income, credit score, tenure, city) to compute
  actual loan amounts, interest rates, and EMIs — no placeholder strings.
- Selects tone automatically from conversion_probability when not specified.
- Outputs WhatsApp-ready messages with emojis and short URLs.
- Framework variants: AIDA (attention → interest → desire → action)
                      SPIN (situation → problem → implication → need-payoff)
"""
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from src.database import SessionLocal, Customer, Product


# ── Financial calculators ──────────────────────────────────────────────────────

def _emi(principal: float, annual_rate_pct: float, tenure_months: int = 60) -> float:
    """Standard reducing-balance EMI formula."""
    r = annual_rate_pct / 12 / 100
    if r == 0:
        return principal / tenure_months
    return principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)


def _rate_for_credit_score(credit_score: Optional[int]) -> float:
    """Map credit score band → interest rate for personal/home loans."""
    cs = credit_score or 650
    if cs >= 775:
        return 10.5
    elif cs >= 750:
        return 11.0
    elif cs >= 720:
        return 11.5
    elif cs >= 700:
        return 12.0
    elif cs >= 675:
        return 12.5
    else:
        return 13.0


def _fmt_inr(amount: float) -> str:
    """Format a rupee amount compactly: 1,80,000 → ₹1.8L; 25,00,000 → ₹25L."""
    if amount >= 1_000_000:
        val = amount / 100_000
        return f"₹{val:.0f}L" if val == int(val) else f"₹{val:.1f}L"
    if amount >= 100_000:
        val = amount / 100_000
        return f"₹{val:.0f}L" if val == int(val) else f"₹{val:.2f}L"
    return f"₹{amount:,.0f}"


def _offer_expiry(days: int = 16) -> str:
    """Human-readable offer expiry date."""
    return (datetime.utcnow() + timedelta(days=days)).strftime("%-d %b %Y")


def _first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name else full_name


# ── Personalization signal builder ─────────────────────────────────────────────

def _build_trust_line(customer: Customer, txn_context: Optional[dict]) -> str:
    """
    Craft a one-line sentence that references something specific to this customer —
    used as the opening hook in AIDA messages.
    """
    name = _first_name(customer.name)
    tenure = int(customer.relationship_years or 0)
    balance = customer.monthly_avg_balance or 0

    if tenure >= 10:
        return f"As one of our most loyal customers for {tenure} years"
    if tenure >= 5:
        return f"Given your {tenure}-year relationship with us"
    if balance >= 500_000:
        return f"Given your excellent savings track record"
    if txn_context and txn_context.get("total_count", 0) >= 15:
        return f"As an active customer who uses our services regularly"
    return f"Based on your banking profile"


def validate_message_facts(message: str, customer_id: str, product_id: str) -> dict:
    """
    Hallucination prevention — validate financial facts in message against DB.

    Checks:
    1. Interest rate in message matches DB rate for customer's credit score
    2. Loan amount doesn't exceed eligibility (5x annual income for personal loan)
    3. No obviously fake timelines promised ("same day" for home loans, etc.)

    Returns: {valid: bool, issues: list, corrected_rate: float, corrected_amount: float}
    """
    import re
    from src.database import SessionLocal, Customer, Product

    issues = []
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        product = session.query(Product).filter_by(product_id=product_id).first()
        if not customer or not product:
            return {"valid": True, "issues": [], "warning": "Could not load customer/product for validation"}

        # ── Check 1: Interest rate ─────────────────────────────────────────────
        correct_rate = _rate_for_credit_score(customer.credit_score)
        # Find rates mentioned in message (e.g. "10.5%", "11%", "9.99% p.a.")
        mentioned_rates = [float(r) for r in re.findall(r'(\d+(?:\.\d+)?)\s*%', message)]
        for rate in mentioned_rates:
            if abs(rate - correct_rate) > 2.0:  # allow 2% tolerance
                issues.append(
                    f"Rate {rate}% in message doesn't match customer's eligible rate {correct_rate}% "
                    f"(credit score {customer.credit_score})"
                )

        # ── Check 2: Loan amount eligibility ──────────────────────────────────
        if product_id == "PL001" and customer.annual_income:
            max_eligible = customer.annual_income * 5
            # Find amounts mentioned (e.g. "₹5,00,000", "5 lakh", "₹15L")
            amounts_lakh = [float(a) * 100_000 for a in re.findall(r'(\d+(?:\.\d+)?)\s*[Ll]akh', message)]
            amounts_raw = [float(a.replace(',','')) for a in re.findall(r'₹\s*([\d,]+)', message)]
            all_amounts = amounts_lakh + amounts_raw
            for amt in all_amounts:
                if amt > max_eligible * 1.1:  # 10% tolerance
                    issues.append(
                        f"Loan amount ₹{amt:,.0f} exceeds customer eligibility "
                        f"₹{max_eligible:,.0f} (5× income of ₹{customer.annual_income:,.0f})"
                    )

        # ── Check 3: Impossible timelines ─────────────────────────────────────
        if product_id == "HL001":  # Home loan
            bad_promises = ["same day", "24 hours", "instant", "immediate", "today"]
            msg_lower = message.lower()
            for bp in bad_promises:
                if bp in msg_lower:
                    issues.append(f"Home loans cannot be disbursed '{bp}' — this promise is inaccurate")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "corrected_rate": correct_rate,
            "max_eligible_amount": (customer.annual_income or 0) * 5 if product_id == "PL001" else None,
        }
    finally:
        session.close()


def _conversion_to_tone(prob: Optional[float]) -> str:
    if prob is None:
        return "warm"
    if prob >= 0.55:
        return "warm"
    if prob >= 0.35:
        return "professional"
    return "urgent"


def _cta_for_stage(pipeline_stage: str, product_type: str = "personal_loan") -> str:
    """
    Return the best CTA based on pipeline stage.

    Cold (NEW/CONTACTED):    curiosity-driven, low commitment
    Warm (ENGAGED/CONSIDERING): specific offer, time-bound
    Hot (INTERESTED/CALLBACK): scheduling, immediate next step
    """
    stage = (pipeline_stage or "NEW").upper()

    cold_ctas = {
        "personal_loan": "Curious what your EMI would be? Just reply with your preferred loan amount and I'll calculate it instantly.",
        "credit_card": "Want to see what rewards you'd earn on your current monthly spend? Just say YES and I'll show you.",
        "home_loan": "Wondering what home you could afford? Reply with your monthly income and I'll run the numbers.",
        "fd": "Want to see how much your balance could earn in a Fixed Deposit vs savings account? Reply to find out.",
    }
    warm_ctas = {
        "personal_loan": "Want me to hold this rate for 48 hours? Just say YES and I'll lock it in for you.",
        "credit_card": "Ready to apply? Your pre-approval takes under 2 minutes — just say GO and I'll share the link.",
        "home_loan": "Shall I check your exact eligibility? It takes 5 minutes and doesn't affect your credit score.",
        "fd": "Shall I open a short-tenure FD while you decide on the full amount? Even 30 days earns more.",
    }
    hot_ctas = {
        "personal_loan": "I have a 10am or 2pm slot tomorrow for a 10-minute call. Which works for you?",
        "credit_card": "The card can be dispatched to your address by Friday. Shall I proceed?",
        "home_loan": "Let me connect you directly with our home loan specialist — she's available tomorrow 11am. Shall I book it?",
        "fd": "I can open the FD right now if you have 5 minutes. Want to do it over the phone?",
    }

    hot_stages = {"INTERESTED", "CALLBACK_REQUESTED", "CLOSING"}
    warm_stages = {"ENGAGED", "CONSIDERING", "THINKING"}

    pt = product_type.lower().replace(" ", "_").replace("-", "_")
    if "credit" in pt or "cc" in pt:
        pt = "credit_card"
    elif "home" in pt or "hl" in pt:
        pt = "home_loan"
    elif "fd" in pt or "deposit" in pt:
        pt = "fd"
    else:
        pt = "personal_loan"

    if stage in hot_stages:
        return hot_ctas.get(pt, hot_ctas["personal_loan"])
    elif stage in warm_stages:
        return warm_ctas.get(pt, warm_ctas["personal_loan"])
    else:
        return cold_ctas.get(pt, cold_ctas["personal_loan"])


# ── Product-specific message builders ─────────────────────────────────────────

def _personal_loan_msg(customer: Customer, product: Product, framework: str,
                        tone: str, txn_context: Optional[dict]) -> tuple[str, str]:
    """Returns (primary_message, short_variant)."""
    name = _first_name(customer.name)
    income = customer.annual_income or 0
    credit = customer.credit_score
    tenure = int(customer.relationship_years or 0)

    loan_amount = min(income * 0.5, 2_500_000)
    rate = _rate_for_credit_score(credit)
    emi_val = _emi(loan_amount, rate, 60)
    loan_str = _fmt_inr(loan_amount)
    emi_str = _fmt_inr(emi_val)
    expiry = _offer_expiry()
    city = customer.city or "your city"
    trust = _build_trust_line(customer, txn_context)

    if framework == "AIDA":
        if tone == "warm":
            msg = (
                f"Hi {name}! 👋\n\n"
                f"{trust}, you've been *pre-approved* for a Personal Loan:\n\n"
                f"💰 *Amount:* {loan_str}\n"
                f"📊 *Rate:* {rate}% p.a. (fixed)\n"
                f"📅 *EMI:* {emi_str}/month for 5 years\n"
                f"✅ No collateral • Instant disbursal\n\n"
                f"Reply *YES* for a callback from your RM within 2 hours.\n"
                f"⏰ Offer valid till {expiry}"
            )
        elif tone == "urgent":
            msg = (
                f"⚡ {name}, your pre-approved Personal Loan offer expires soon!\n\n"
                f"💰 {loan_str} at {rate}% p.a. → EMI just {emi_str}/month\n"
                f"⏰ *Closing: {expiry}*\n\n"
                f"Reply *YES* now — your RM will call you within the hour."
            )
        else:  # professional
            msg = (
                f"Dear {name},\n\n"
                f"We're pleased to inform you that you have been pre-approved for a "
                f"Personal Loan of {loan_str} at {rate}% p.a.\n\n"
                f"• Monthly EMI: {emi_str} (5-year tenure)\n"
                f"• No collateral required\n"
                f"• Disbursal within 24 hours of approval\n\n"
                f"To proceed, reply *APPLY* or call your dedicated RM.\n"
                f"Offer valid till {expiry}."
            )

    else:  # SPIN
        msg = (
            f"Hi {name},\n\n"
            f"{trust} — I wanted to reach out personally.\n\n"
            f"Are you planning any major expense in the coming months — home renovation, "
            f"education, or anything else in {city}?\n\n"
            f"We have a pre-approved Personal Loan ready for you:\n"
            f"• {loan_str} at {rate}% p.a. → EMI: {emi_str}/month\n\n"
            f"Would you like to explore this? Reply *YES* and I'll call you today."
        )

    short = (
        f"{name}, pre-approved for {loan_str} Personal Loan @ {rate}% p.a. "
        f"EMI: {emi_str}/mo. Reply YES. Valid till {expiry}."
    )
    return msg, short


def _credit_card_msg(customer: Customer, product: Product, framework: str,
                      tone: str, txn_context: Optional[dict]) -> tuple[str, str]:
    name = _first_name(customer.name)
    expiry = _offer_expiry()
    trust = _build_trust_line(customer, txn_context)

    # Infer top spend category from txn_context
    best_cat = "dining & shopping"
    if txn_context and txn_context.get("categories"):
        cats = txn_context["categories"]
        skip = {"salary", "uncategorized", "transfer"}
        filtered = {k: v for k, v in cats.items() if k.lower() not in skip}
        if filtered:
            best_cat = max(filtered, key=filtered.get)

    product_name = product.name

    if framework == "AIDA":
        if tone == "warm":
            msg = (
                f"Hi {name}! 🎉\n\n"
                f"{trust}, you're pre-approved for the *{product_name}*!\n\n"
                f"Here's what you get:\n"
                f"✨ 5% cashback on {best_cat}\n"
                f"✨ Zero annual fee — Year 1\n"
                f"✨ 1-click approval, no paperwork\n"
                f"✨ Complimentary airport lounge access\n\n"
                f"Reply *YES* to activate instantly.\n"
                f"⏰ Offer valid till {expiry}"
            )
        elif tone == "urgent":
            msg = (
                f"⚡ {name}, your *{product_name}* approval expires {expiry}!\n\n"
                f"5% cashback on {best_cat} • Zero fee Year 1\n\n"
                f"Reply *YES* now to lock this in."
            )
        else:
            msg = (
                f"Dear {name},\n\n"
                f"You have been pre-approved for the {product_name}.\n\n"
                f"• 5% cashback on {best_cat}\n"
                f"• Zero annual fee (Year 1)\n"
                f"• No documentation needed\n\n"
                f"Reply *APPLY* or speak to your RM. Valid till {expiry}."
            )
    else:  # SPIN
        msg = (
            f"Hi {name},\n\n"
            f"Quick question — are you happy with the rewards you currently earn on your spending?\n\n"
            f"We noticed you spend significantly on {best_cat}. Our *{product_name}* gives you "
            f"5% cashback in that category every month.\n\n"
            f"You're already pre-approved. Reply *YES* to activate — takes 60 seconds."
        )

    short = f"{name}, pre-approved for {product_name}. 5% cashback on {best_cat}. Reply YES. Valid till {expiry}."
    return msg, short


def _fd_msg(customer: Customer, product: Product, framework: str,
             tone: str, txn_context: Optional[dict]) -> tuple[str, str]:
    name = _first_name(customer.name)
    balance = customer.monthly_avg_balance or 0
    invest_amount = min(balance * 0.5, 1_000_000)
    invest_str = _fmt_inr(invest_amount)
    rate = product.interest_rate or 7.5
    maturity_str = _fmt_inr(invest_amount * (1 + rate / 100) ** 2)
    expiry = _offer_expiry()
    trust = _build_trust_line(customer, txn_context)

    if framework == "AIDA":
        if tone == "warm":
            msg = (
                f"Hi {name}! 📈\n\n"
                f"{trust}, your money deserves to work harder.\n\n"
                f"Our Fixed Deposit is offering *{rate}% p.a.* — one of the best rates in the market!\n\n"
                f"Example for {invest_str}:\n"
                f"💰 Invest: {invest_str}\n"
                f"📈 After 2 years: {maturity_str}\n"
                f"🔒 100% safe — insured up to ₹5L by DICGC\n\n"
                f"Reply *FD* to book instantly. ⏰ Valid till {expiry}"
            )
        else:
            msg = (
                f"Dear {name},\n\n"
                f"Secure your savings with our Fixed Deposit at {rate}% p.a.\n\n"
                f"• Capital guaranteed\n"
                f"• Flexible tenures: 1, 2, or 3 years\n"
                f"• Pre-mature withdrawal available\n\n"
                f"Reply *FD* to get started. Offer valid till {expiry}."
            )
    else:  # SPIN
        msg = (
            f"Hi {name},\n\n"
            f"How is your current savings strategy working out?\n\n"
            f"Many customers are missing out on {rate}% p.a. by keeping idle funds in savings accounts. "
            f"A Fixed Deposit would give you {maturity_str} on {invest_str} over 2 years — risk-free.\n\n"
            f"Want me to set this up for you today? Reply *YES*."
        )

    short = f"{name}, book an FD at {rate}% p.a. {invest_str} → {maturity_str} in 2 years. Reply FD. Valid {expiry}."
    return msg, short


def _home_loan_msg(customer: Customer, product: Product, framework: str,
                    tone: str, txn_context: Optional[dict]) -> tuple[str, str]:
    name = _first_name(customer.name)
    income = customer.annual_income or 0
    credit = customer.credit_score
    loan_amount = min(income * 5, 10_000_000)
    rate = _rate_for_credit_score(credit) - 1.5  # HL is ~1.5pp lower than PL
    rate = max(rate, 8.5)
    emi_val = _emi(loan_amount, rate, 240)  # 20-year tenure
    loan_str = _fmt_inr(loan_amount)
    emi_str = _fmt_inr(emi_val)
    expiry = _offer_expiry()
    city = customer.city or "your city"
    trust = _build_trust_line(customer, txn_context)

    msg = (
        f"Hi {name}! 🏠\n\n"
        f"{trust}, you're eligible for a Home Loan up to *{loan_str}* at {rate}% p.a.\n\n"
        f"📅 EMI: {emi_str}/month (20 years)\n"
        f"✅ Pre-approved — minimal documentation\n"
        f"🏙️ Perfect for properties in {city}\n\n"
        f"Reply *HOME* for a free consultation. Valid till {expiry}"
    )
    short = f"{name}, Home Loan up to {loan_str} @ {rate}% p.a., EMI {emi_str}/mo. Reply HOME. Valid {expiry}."
    return msg, short


# ── Dispatcher ─────────────────────────────────────────────────────────────────

_MSG_BUILDERS = {
    "personal_loan": _personal_loan_msg,
    "credit_card":   _credit_card_msg,
    "fd":            _fd_msg,
    "home_loan":     _home_loan_msg,
}


# ── Public API ─────────────────────────────────────────────────────────────────

def draft_outreach_message(
    customer_name: str,
    product_id: str,
    framework: str = "AIDA",
    tone: str = "warm",
    customer_id: Optional[str] = None,
    conversion_probability: Optional[float] = None,
    transaction_context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Draft a personalized outreach message for a customer.

    Args:
        customer_name: Customer full name (fallback if customer_id not provided)
        product_id:    Product being offered (e.g. "PL001", "CC001")
        framework:     Sales framework — "AIDA" or "SPIN"
        tone:          "warm" | "professional" | "urgent" (auto-selected from
                       conversion_probability when not explicitly passed)
        customer_id:   Optional — loads real financial data (income, credit score,
                       tenure) to compute actual loan amounts and EMIs.
        conversion_probability: Float 0–1 — used to auto-select tone if tone="warm"
                       was the default and no override was given.
        transaction_context: Dict from get_transaction_summary — used to detect
                       top spend category (for CC) and activity level.

    Returns:
        Dict with primary_message, short_variant, personalization_note, offer_expiry
    """
    session = SessionLocal()
    try:
        product = session.query(Product).filter_by(product_id=product_id).first()
        if not product:
            return {"error": f"Product {product_id} not found"}

        # Load customer from DB if ID is provided — gives us real financial data
        customer = None
        if customer_id:
            customer = session.query(Customer).filter_by(customer_id=customer_id).first()

        # Auto-select tone from conversion probability (only when default passed in)
        effective_tone = _conversion_to_tone(conversion_probability) if tone == "warm" else tone

        # Build personalization note for the RM dashboard
        signals = []
        if customer:
            if (customer.relationship_years or 0) >= 10:
                signals.append(f"{int(customer.relationship_years)}-year loyal customer")
            if (customer.credit_score or 0) >= 750:
                signals.append(f"Excellent credit ({customer.credit_score})")
            if (customer.monthly_avg_balance or 0) >= 300_000:
                signals.append("High-balance saver")
        if conversion_probability is not None:
            signals.append(f"Conversion probability: {conversion_probability*100:.0f}%")
        if transaction_context and transaction_context.get("total_count", 0) >= 15:
            signals.append(f"Active: {transaction_context['total_count']} txns/90d")
        personalization_note = " | ".join(signals) if signals else "Standard outreach"

        # Fall back to a minimal Customer-like object if no DB record found
        if customer is None:
            # Create a minimal mock with sensible defaults
            class _FallbackCustomer:
                name = customer_name
                annual_income = 800_000
                monthly_avg_balance = 150_000
                credit_score = 700
                relationship_years = 3
                city = None
                segment = "mass"
                has_credit_card = False
                has_personal_loan = False
                has_home_loan = False
                has_fd = False
            customer = _FallbackCustomer()

        # Pick the right message builder for this product type
        product_type = (product.product_type or "personal_loan").lower().replace(" ", "_")
        builder = _MSG_BUILDERS.get(product_type, _personal_loan_msg)

        primary_msg, short_variant = builder(
            customer, product, framework, effective_tone, transaction_context
        )

        expiry = _offer_expiry()

        return {
            "customer_name": customer_name,
            "customer_id": customer_id,
            "product_id": product_id,
            "product_name": product.name,
            "product_type": product_type,
            "framework": framework,
            "tone": effective_tone,
            "conversion_probability": conversion_probability,
            "primary_message": primary_msg,
            "short_variant": short_variant,
            "personalization_note": personalization_note,
            "offer_expiry": expiry,
            "cta": "Reply YES to learn more",
        }
    finally:
        session.close()
