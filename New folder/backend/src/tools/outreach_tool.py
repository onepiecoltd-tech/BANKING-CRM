"""
Outreach sending tool — multi-backend WhatsApp delivery.

Backends (SENDER_BACKEND env var):
  whatsapp-web  — free, uses your own WhatsApp via QR session (local Node service)
  twilio        — Twilio WhatsApp API with rich Content template + quick-reply buttons
  mock          — dev/demo mode; logs to DB, returns mock status

Twilio template (Content SID: TWILIO_WHATSAPP_CONTENT_SID):
  Hi {{1}}! 🎉 You've been *pre-approved* for a {{2}}:
  💰 Amount: ₹{{3}} | Rate: {{4}}% p.a. | EMI: ₹{{5}}/month
  ⏰ Valid till: {{6}}
  Quick-reply buttons: ✅ Yes, Interested! | 📞 Call Me | ❌ Not Now
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from src.database import SessionLocal, Interaction
from src.config import settings


# ── CRM logging ───────────────────────────────────────────────────────────────

def log_outreach(
    customer_id: str,
    message: str,
    product_id: str,
    channel: str = "whatsapp",
    framework_used: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist an outreach interaction to the CRM database."""
    session = SessionLocal()
    try:
        interaction = Interaction(
            interaction_id=f"INT_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            date=datetime.utcnow(),
            channel=channel,
            product_offered=product_id,
            message=message,
            pipeline_state="CONTACTED",
            framework_used=framework_used,
        )
        session.add(interaction)
        session.commit()
        return {
            "interaction_id": interaction.interaction_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "channel": channel,
            "status": "logged",
            "timestamp": interaction.date.isoformat(),
        }
    finally:
        session.close()


# ── WhatsApp Web JS backend ───────────────────────────────────────────────────

def _send_via_whatsapp_web(phone_number: str, message: str) -> Dict[str, Any]:
    """
    POST to the local Node.js WhatsApp Web bridge (localhost:3001).
    Free, unlimited — uses your own WhatsApp account via QR session.
    """
    import urllib.request, urllib.error, json as _json

    url = settings.whatsapp_service_url.rstrip("/") + "/send"
    payload = _json.dumps({"phone": phone_number, "message": message}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            return {
                "status": data.get("status", "sent"),
                "messageId": data.get("messageId"),
                "to": phone_number,
                "preview": message[:100] + ("…" if len(message) > 100 else ""),
            }
    except urllib.error.HTTPError as e:
        raw = e.read()
        body = _json.loads(raw) if raw else {}
        return {"status": "error", "error": body.get("error", str(e))}
    except Exception as exc:
        return {
            "status": "error",
            "error": f"WhatsApp service unreachable: {exc}. Run: cd whatsapp-service && node server.js",
        }


# ── Twilio WhatsApp backend ───────────────────────────────────────────────────

def _parse_loan_vars(message: str) -> Optional[Dict[str, str]]:
    """
    Extract loan variables for the Twilio Content template (loan products only).
    Returns None if:
      - the message is for a non-loan product (credit card, FD) — falls back to body
      - any required numeric field (amount, rate, EMI) is missing — falls back to body

    The Content template has slots for Amount / Rate / EMI which only make sense for
    Personal Loan and Home Loan. Credit Card and FD messages must go as plain body text.
    """
    import re

    msg_lower = message.lower()

    # ── Non-loan products: always use body text, never the loan template ──────
    NON_LOAN_SIGNALS = [
        "credit card", "cashback", "zero annual fee", "lounge access",
        "fixed deposit", "maturity", "book.*fd", "invest.*₹",
    ]
    for sig in NON_LOAN_SIGNALS:
        if re.search(sig, msg_lower):
            return None   # skip template → fall through to body

    # ── Loan products: parse required numeric fields ──────────────────────────

    # Customer first name
    name_m = re.search(r"Hi\s+(\w+)[!,]", message)
    name = name_m.group(1) if name_m else "there"

    # Product label
    product = "Loan"
    for p in ["Personal Loan", "Home Loan"]:
        if p.lower() in msg_lower:
            product = p
            break

    # Amount — ₹ followed by digits and optional L/Cr suffix
    amt_m = re.search(r"₹([\d,.]+[LCr]*)", message)
    amount = amt_m.group(1) if amt_m else None

    # Rate — digits.digits% p.a.
    rate_m = re.search(r"(\d+\.?\d*)\s*%\s*p\.a\.", message)
    rate = rate_m.group(1) if rate_m else None

    # EMI — ₹XX,XXX/month or EMI ₹...
    emi_m = re.search(r"EMI[:\s]*₹?([\d,]+)", message, re.IGNORECASE)
    if not emi_m:
        emi_m = re.search(r"₹([\d,]+)/month", message)
    emi = emi_m.group(1) if emi_m else None

    # If ANY numeric field is missing, fall back to body text (no blank ₹— slots)
    if not amount or not rate or not emi:
        return None

    # Expiry date
    exp_m = re.search(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})", message)
    if not exp_m:
        exp_m = re.search(r"(end of month)", message, re.IGNORECASE)
    expiry = exp_m.group(1) if exp_m else "month-end"

    return {
        "1": name,
        "2": product,
        "3": amount,
        "4": rate,
        "5": emi,
        "6": expiry,
    }


def _send_via_twilio(phone_number: str, message: str) -> Dict[str, Any]:
    """
    Send via Twilio WhatsApp API.

    Priority:
      1. Content template (TWILIO_WHATSAPP_CONTENT_SID) — rich message with quick-reply buttons
      2. Body text fallback — if Content SID missing or variables unparseable
    """
    try:
        from twilio.rest import Client as TwilioClient  # type: ignore
    except ImportError:
        return {"status": "error", "error": "twilio package not installed — run: pip install twilio"}

    sid   = settings.twilio_account_sid
    token = settings.twilio_auth_token
    from_ = settings.twilio_phone_number
    content_sid = settings.twilio_whatsapp_content_sid

    if not sid or not token or not from_:
        return {
            "status": "error",
            "error": "Missing TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER in .env",
        }

    client = TwilioClient(sid, token)
    wa_from = f"whatsapp:{from_}" if not from_.startswith("whatsapp:") else from_
    wa_to   = f"whatsapp:{phone_number}" if not phone_number.startswith("whatsapp:") else phone_number

    # ── Try Content API template (rich message + buttons) ─────────────────────
    if content_sid:
        variables = _parse_loan_vars(message)
        if variables:
            try:
                import json as _json
                tw_msg = client.messages.create(
                    from_=wa_from,
                    to=wa_to,
                    content_sid=content_sid,
                    content_variables=_json.dumps(variables),
                )
                return {
                    "status": "sent",
                    "sid": tw_msg.sid,
                    "to": phone_number,
                    "backend_detail": "twilio/content-template",
                    "template_vars": variables,
                    "preview": (
                        f"Hi {variables['1']}! 🎉 Pre-approved {variables['2']} "
                        f"₹{variables['3']} @ {variables['4']}% p.a. "
                        f"[Quick-reply buttons: ✅ Yes | 📞 Call Me | ❌ Not Now]"
                    ),
                }
            except Exception as e:
                # If template fails (e.g. not sandbox-approved) fall through to body
                pass

    # ── Fallback: body text ───────────────────────────────────────────────────
    try:
        tw_msg = client.messages.create(
            from_=wa_from,
            to=wa_to,
            body=message,
        )
        return {
            "status": "sent",
            "sid": tw_msg.sid,
            "to": phone_number,
            "backend_detail": "twilio/body",
            "preview": message[:100] + ("…" if len(message) > 100 else ""),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Spam Score ────────────────────────────────────────────────────────────────

_SPAM_WORDS = [
    "limited time", "act now", "guaranteed", "100%", "risk free", "risk-free",
    "no obligation", "winner", "free gift", "click here", "urgent", "expires today",
    "last chance", "don't miss out", "apply now", "instant approval", "no credit check",
    "pre-approved" if False else None,  # pre-approved is okay in banking context
    "congratulations you", "you have been selected",
]
_SPAM_WORDS = [w for w in _SPAM_WORDS if w]


def spam_score(message: str) -> dict:
    """
    Score a message for spam signals before sending.

    Returns:
        score (0-100, lower is better), issues list, recommendation (SEND/REVIEW/BLOCK)
    """
    issues = []
    score = 0

    # Spam word check
    msg_lower = message.lower()
    found_spam = [w for w in _SPAM_WORDS if w in msg_lower]
    if found_spam:
        score += len(found_spam) * 10
        issues.append(f"Spam trigger words: {', '.join(found_spam)}")

    # ALL CAPS ratio
    letters = [c for c in message if c.isalpha()]
    if letters:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if caps_ratio > 0.3:
            score += 20
            issues.append(f"High CAPS ratio ({caps_ratio:.0%})")

    # Emoji density
    import re
    emoji_count = len(re.findall(
        r'[\U0001F300-\U0001FFFF\U00002600-\U000027FF]', message
    ))
    if emoji_count > 4:
        score += 10
        issues.append(f"Too many emojis ({emoji_count})")

    # Message length
    if len(message) > 800:
        score += 15
        issues.append(f"Message too long ({len(message)} chars — WhatsApp is for short messages)")

    # Multiple exclamation marks
    exclamation_count = message.count("!")
    if exclamation_count > 3:
        score += 10
        issues.append(f"Excessive exclamation marks ({exclamation_count})")

    score = min(score, 100)

    if score >= 40:
        recommendation = "BLOCK"
    elif score >= 20:
        recommendation = "REVIEW"
    else:
        recommendation = "SEND"

    return {
        "score": score,
        "issues": issues,
        "recommendation": recommendation,
        "message_length": len(message),
        "emoji_count": emoji_count,
    }


# ── Main dispatch ─────────────────────────────────────────────────────────────

def send_outreach_message(
    customer_id: str,
    phone_number: str,
    message: str,
    product_id: str,
    framework_used: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a WhatsApp outreach message to a customer and log to CRM.

    Backend selection (SENDER_BACKEND env var):
      whatsapp-web → free, your WhatsApp account (local Node service)
      twilio       → Twilio Content template + quick-reply buttons
      mock         → dev mode, no real send
    """
    # ── Compliance: opt-out check ─────────────────────────────────────────
    from src.database import SessionLocal as _SL, Suppression
    from datetime import datetime as _dt
    _db = _SL()
    try:
        active_suppression = _db.query(Suppression).filter(
            Suppression.canonical_id == customer_id,
            (Suppression.expires_at == None) | (Suppression.expires_at > _dt.utcnow())
        ).first()
        if active_suppression:
            return {
                "status": "suppressed",
                "reason": active_suppression.reason,
                "message": f"Customer {customer_id} is on suppression list: {active_suppression.reason}",
            }
    finally:
        _db.close()

    # ── Quality: spam score check ─────────────────────────────────────────
    spam = spam_score(message)
    if spam["recommendation"] == "BLOCK":
        return {
            "status": "blocked_spam",
            "spam_score": spam["score"],
            "issues": spam["issues"],
            "message": "Message blocked by spam filter. Please revise before sending.",
        }

    logged = log_outreach(
        customer_id=customer_id,
        message=message,
        product_id=product_id,
        channel="whatsapp",
        framework_used=framework_used,
    )

    backend = (settings.sender_backend or "mock").lower()

    if backend == "whatsapp-web":
        result = _send_via_whatsapp_web(phone_number, message)
        return {"interaction_id": logged["interaction_id"], "customer_id": customer_id,
                "backend": "whatsapp-web", "timestamp": datetime.utcnow().isoformat(), **result}

    if backend == "twilio":
        result = _send_via_twilio(phone_number, message)
        return {"interaction_id": logged["interaction_id"], "customer_id": customer_id,
                "backend": "twilio", "timestamp": datetime.utcnow().isoformat(), **result}

    # mock
    return {
        "interaction_id": logged["interaction_id"],
        "customer_id": customer_id,
        "backend": "mock",
        "status": "sent_mock",
        "to": phone_number,
        "preview": message[:120] + ("…" if len(message) > 120 else ""),
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Set SENDER_BACKEND=twilio or whatsapp-web in .env to send real messages.",
    }
