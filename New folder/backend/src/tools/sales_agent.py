"""
AI Sales Agent — responds to incoming WhatsApp messages as a real RM would.

Personalization layers (Adobe-level):
  1. Customer segment + tenure + city → RM persona selection
  2. Life events from transactions → wedding? promotion? medical? → tailor the hook
  3. Behavioral signals → spend personality, timing preference, EMI risk
  4. Conversation memory → prior objections, promised callbacks, turn count
  5. Intent classification → YES / NO / PRICE_OBJECTION / etc. → template or LLM
  6. Product-specific CTAs → cold/warm/hot variants per stage
"""
from typing import Optional
from src.database import SessionLocal, Customer, Interaction, Product
from src.llm.base import LLMMessage
from src.config import settings


# ── Intent classifier ─────────────────────────────────────────────────────────

def _classify_intent(text: str) -> str:
    t = text.lower().strip()
    if any(k in t for k in ["yes", "interested", "ok", "okay", "sure", "haan", "ha ", "proceed", "apply", "want", "i want", "tell me more", "more info"]):
        return "YES"
    if any(k in t for k in ["no", "nahi", "not interested", "dont", "don't", "nope", "cancel", "stop", "unsubscribe"]):
        return "NO"
    if any(k in t for k in ["expensive", "high rate", "emi", "interest", "rate", "cost", "affordab", "too much", "reduce"]):
        return "PRICE_OBJECTION"
    if any(k in t for k in ["already have", "existing loan", "current loan", "other bank", "already taken"]):
        return "HAS_PRODUCT"
    if any(k in t for k in ["document", "docs", "paper", "kyc", "what do i need", "requirement", "form", "upload"]):
        return "DOCUMENTS"
    if any(k in t for k in ["how long", "time", "days", "process", "fast", "quick", "disburs", "when"]):
        return "TIMELINE"
    if any(k in t for k in ["call", "callback", "speak", "talk", "phone", "meet", "ring me", "call me"]):
        return "WANTS_CALLBACK"
    if any(k in t for k in ["think", "consider", "later", "sometime", "maybe", "will let you know", "check with", "discuss"]):
        return "THINKING"
    if any(k in t for k in ["hi", "hello", "hey", "how are", "good morning", "good evening"]):
        return "GREETING"
    return "GENERAL"


# ── Life event → personalized hook ───────────────────────────────────────────

_LIFE_EVENT_HOOKS = {
    "WEDDING_LIKELY": "We noticed some wedding-related expenses recently — a personal loan could help cover the celebration costs comfortably",
    "MEDICAL_EXPENSE": "We noticed some medical expenses recently — a personal loan can provide an instant financial cushion for such needs",
    "PROMOTION_LIKELY": "Congrats on what looks like a recent income upgrade! This is the perfect time to leverage your increased earning power",
    "HAS_CHILDREN": "With a growing family, having a financial cushion makes all the difference",
    "TRAVEL_FREQUENT": "As someone who loves travel, having instant access to funds means never missing a great trip",
    "LIFESTYLE_SPENDER": "Your lifestyle reflects someone who values quality — this offer gives you the flexibility to enjoy life on your terms",
    "MEDICAL_LOAN_CANDIDATE": "Given recent healthcare expenses, a pre-approved loan can serve as a ready financial safety net",
}


def _get_life_event_hook(customer_id: str) -> str:
    """Fetch the strongest life event hook for this customer."""
    try:
        from src.tools.scoring_tool import detect_life_events
        events = detect_life_events(customer_id)
        for ev in (events or []):
            hook = _LIFE_EVENT_HOOKS.get(ev.get("event_type", ""))
            if hook:
                return hook
    except Exception:
        pass
    return ""


def _get_behavioral_signals(customer_id: str) -> dict:
    """Fetch spend personality, timing, and tone hint."""
    try:
        from src.tools.scoring_tool import get_behavioral_signals
        return get_behavioral_signals(customer_id) or {}
    except Exception:
        return {}


# ── RM Persona ────────────────────────────────────────────────────────────────

_PERSONAS = {
    "premium":  ("Arjun Sharma",  "Senior Private Banking RM",  "consultative, sophisticated, high-touch"),
    "affluent": ("Priya Mehta",   "Relationship Manager",        "professional, warm, solutions-focused"),
    "mass":     ("Rahul Verma",   "Customer Relationship Manager", "friendly, simple, encouraging"),
}


# ── Personalized template replies ─────────────────────────────────────────────

def _template_reply(
    intent: str,
    customer: Customer,
    product: Product,
    loan_amount: str,
    rate: float,
    emi: str,
    life_event_hook: str = "",
    behavioral: dict = None,
) -> Optional[str]:
    name = customer.name.split()[0]
    p    = product.name
    seg  = customer.segment or "mass"
    tenure = int(customer.relationship_years or 0)
    behavioral = behavioral or {}

    # Loyalty anchor — used across templates
    loyalty = f"As a {tenure}-year customer" if tenure >= 3 else "As a valued customer"

    # Life event hook insertion
    hook_line = f"\n\n💡 _{life_event_hook}_" if life_event_hook else ""

    templates = {
        "YES": (
            f"That's wonderful, {name}! 🎉 Your *{p}* for *{loan_amount} at {rate}% p.a.* "
            f"is pre-approved — no collateral, instant disbursal within 24 hours.\n\n"
            f"{loyalty}, your application gets priority processing. "
            f"What time works best for a quick 10-minute call — *morning (10–12pm)* or *afternoon (2–5pm)*?"
            f"{hook_line}"
        ),
        "NO": (
            f"Completely understood, {name}! No pressure at all. 🙏\n\n"
            f"The offer at *{rate}% p.a.* stays open till end of month — feel free to ping me if anything changes. "
            f"Have a great day! 😊"
        ),
        "DOCUMENTS": (
            f"Great question, {name}! For the *{p}*, you'll need:\n\n"
            f"✅ PAN card\n"
            f"✅ Last 3 months' salary slips\n"
            f"✅ 6 months bank statement\n"
            f"✅ Aadhaar (for address verification)\n\n"
            f"{loyalty}, your *KYC is already verified* — so the process is significantly faster for you. "
            f"Want me to send the secure upload link right now?"
        ),
        "TIMELINE": (
            f"Fast is an understatement, {name}! ⚡\n\n"
            f"For existing customers like you: *document upload → disbursal in 24 hours*. "
            f"No branch visit, 100% digital, and your {tenure} years with us means we skip several verification steps. "
            f"Want to get started now?"
        ),
        "WANTS_CALLBACK": (
            f"Absolutely, {name}! I'd love to walk you through this personally. 📞\n\n"
            f"What works better for you — *morning (10am–12pm)* or *afternoon (2pm–5pm)* today? "
            f"I'll call from this number and have your pre-approved details ready."
        ),
        "THINKING": (
            f"Of course, {name} — take your time! 😊\n\n"
            f"Just a heads-up: this *{rate}% p.a. pre-approved offer* is valid till *end of this month*. "
            f"If you have any questions while you think it over, just reply here — I'm always available. "
            f"Is there anything specific I can clarify to help you decide?"
        ),
        "PRICE_OBJECTION": (
            f"I completely understand, {name}! Let me put it in perspective:\n\n"
            f"The *{emi}/month* is for the full *{loan_amount}* amount. "
            f"You can choose a smaller amount or extend to a *7-year tenure* to bring the monthly commitment way down. "
            f"Which would work better — a smaller loan or a longer tenure?"
        ),
        "HAS_PRODUCT": (
            f"That makes sense, {name}! This is actually a *fresh facility* — separate from any existing loan.\n\n"
            f"Many customers use it for a specific goal (home renovation, travel, emergency fund). "
            f"Given your {tenure} years with us, you're eligible for our best rates. "
            f"Is there a specific financial goal on your mind right now?"
        ),
        "GREETING": (
            f"Hi {name}! 👋 Great to hear from you.\n\n"
            f"I'm Arjun, your Relationship Manager at BankRM. "
            f"I reached out earlier about a special *pre-approved {p} offer* — *{loan_amount} at just {rate}% p.a.*\n\n"
            f"Would you like me to walk you through the details?"
        ),
    }
    return templates.get(intent)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_sales_reply(
    customer: Customer,
    product: Product,
    outreach_message: str,
    customer_reply: str,
    conversation_history: list,
    loan_amount_str: str,
    rate: float,
    emi_str: str,
) -> str:
    """
    Generate a hyper-personalized WhatsApp reply.
    Layers: intent → life events → behavioral signals → persona → template/LLM.
    """
    intent = _classify_intent(customer_reply)
    name   = customer.name.split()[0]

    # ── Personalization signals ───────────────────────────────────────────────
    life_hook  = _get_life_event_hook(customer.customer_id)
    behavioral = _get_behavioral_signals(customer.customer_id)
    tone_hint  = behavioral.get("tone_hint", "warm")  # warm | urgent | empathetic | professional

    # Fast path — rich template for common intents (first 2 turns)
    template = _template_reply(
        intent, customer, product,
        loan_amount_str, rate, emi_str,
        life_event_hook=life_hook,
        behavioral=behavioral,
    )
    if template and len(conversation_history) <= 2:
        return template

    # ── LLM path — complex / multi-turn conversations ─────────────────────────
    seg = customer.segment or "mass"
    rm_name, rm_title, rm_style = _PERSONAS.get(seg, _PERSONAS["mass"])
    tenure = int(customer.relationship_years or 0)

    # Conversation memory
    prior_objections = [
        turn["content"] for turn in conversation_history
        if turn.get("role") == "user" and _classify_intent(turn["content"])
        in ("PRICE_OBJECTION", "HAS_PRODUCT", "NO")
    ]
    callbacks_promised = any(
        _classify_intent(t["content"]) == "WANTS_CALLBACK"
        for t in conversation_history if t.get("role") == "user"
    )
    turn_num = len(conversation_history) // 2 + 1

    memory_ctx = ""
    if prior_objections:
        memory_ctx += f"\nOBJECTIONS RAISED BEFORE: {'; '.join(prior_objections[-2:])}"
    if callbacks_promised:
        memory_ctx += "\n⚠️ Customer requested a callback earlier — acknowledge and confirm."
    if turn_num > 2:
        memory_ctx += f"\nThis is turn {turn_num} of the conversation — be warmer, more personal."

    # Behavioral context
    spend_persona = behavioral.get("spend_personality", "")
    timing_pref   = behavioral.get("best_contact_time", "")
    emi_risk      = behavioral.get("emi_risk", False)
    behav_ctx = ""
    if spend_persona:
        behav_ctx += f"\nSpend personality: {spend_persona}"
    if timing_pref:
        behav_ctx += f" | Best contact time: {timing_pref}"
    if emi_risk:
        behav_ctx += "\n⚠️ EMI risk detected — do NOT push for maximum loan amount. Suggest smaller amount."

    system_prompt = f"""You are {rm_name}, {rm_title} at BankRM. Style: {rm_style}.
WhatsApp conversation with {customer.name} ({seg} segment, {tenure} years with bank).

CUSTOMER PROFILE:
- Income: ₹{(customer.annual_income or 0)/100000:.1f}L/yr | Balance: ₹{(customer.monthly_avg_balance or 0)/100000:.1f}L avg
- Credit Score: {customer.credit_score or 'N/A'} | City: {customer.city or 'N/A'}
- Products held: {'Credit Card' if customer.has_credit_card else ''}{'| Personal Loan' if customer.has_personal_loan else ''}{'| Home Loan' if customer.has_home_loan else ''}{'| FD' if customer.has_fd else ''}

PRODUCT: {product.name}
- Amount: {loan_amount_str} | Rate: {rate}% p.a. | EMI: {emi_str}/month (5 yrs) | 0 collateral | 24hr disbursal
{memory_ctx}{behav_ctx}

LIFE EVENT INSIGHT: {life_hook or "None detected"}

RULES (non-negotiable):
1. MAX 3–4 sentences. WhatsApp ≠ email.
2. Use {name}'s first name naturally.
3. Current intent detected: {intent} — address it directly.
4. End with ONE clear question or call-to-action.
5. Tone: {tone_hint}. Use 1–2 emojis max.
6. Never invent numbers. Use ONLY the figures above.
7. If EMI risk: suggest smaller amount, never push full amount."""

    history_text = ""
    for turn in conversation_history[-6:]:
        role = rm_name if turn["role"] == "assistant" else name
        history_text += f"{role}: {turn['content']}\n"

    user_prompt = (
        f"Conversation:\n{history_text}\n"
        f"{name}: \"{customer_reply}\"\n\n"
        f"Reply as {rm_name}. Be specific, human, and concise."
    )

    # LLM cascade: Gemini → Ollama → template fallback
    for _attempt in range(2):
        try:
            if _attempt == 0:
                from src.llm.gemini import GeminiProvider
                llm = GeminiProvider()
            else:
                from src.llm.ollama import OllamaProvider
                llm = OllamaProvider()
            reply = llm.complete(
                [LLMMessage("system", system_prompt), LLMMessage("user", user_prompt)],
                temperature=0.65,
                max_tokens=220,
            )
            return reply.strip()
        except Exception:
            continue

    return template or f"Thanks {name}! I'll get back to you very shortly. 😊"
