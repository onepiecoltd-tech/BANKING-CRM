# Architecture — Banking CRM Agent

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                    React Frontend  :8080                            │
│                                                                    │
│  /workspace     Agent chat + Send modal (WhatsApp Web / Twilio)   │
│  /conversations Live inbox — button taps, AI replies, funnel      │
│  /customers     Browse, score, recommend products                  │
│  /analytics     KPIs, conversion trend, campaign history          │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST (Vite proxy → :8000)
┌──────────────────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend  :8000                            │
│                                                                    │
│  /api/agent/run               LangGraph pipeline entry point       │
│  /api/outreach/send-batch     WhatsApp Web + Twilio dispatch       │
│  /api/outreach/reply          WhatsApp Web inbound webhook         │
│  /api/outreach/twilio-webhook Twilio button-tap → TwiML reply      │
│  /api/outreach/pipeline       Funnel + recent conversations        │
│  /api/outreach/whatsapp-status QR + connection state               │
│  /api/customers/*             CRUD + score + recommend             │
│  /api/analytics/*             KPIs, charts, campaigns              │
└────────┬──────────────────────────────────────┬────────────────────┘
         │                                      │
┌────────▼────────┐                  ┌──────────▼──────────┐
│  WhatsApp Web   │                  │  Twilio             │
│  Node.js  :3001 │                  │  Content API        │
│                 │                  │                     │
│  whatsapp-web.js│                  │  Template:          │
│  + Puppeteer    │                  │  HX2bc78adf93fb...  │
│                 │                  │  3 quick-reply      │
│  QR session     │                  │  buttons            │
│  (auto-reconnect│                  │                     │
│  after first    │                  │  Sandbox:           │
│  scan)          │                  │  +14155238886       │
│                 │                  │                     │
│  AI_AUTO_REPLY  │                  │  Webhook →          │
│  ON by default  │                  │  Cloudflare Tunnel  │
└────────┬────────┘                  └──────────┬──────────┘
         │                                      │
         └──────────────────┬───────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────────┐
│                       SQLite  banking_crm.db                        │
│                                                                    │
│  customers    (500 rows)   — demographics, financials, products    │
│  transactions (8,569 rows) — 12-month spend history               │
│  products     (4 rows)     — PL001, CC001, HL001, FD001           │
│  interactions (592 rows)   — outreach log + reply log + AI log    │
│  identity_graph            — phone/email → canonical_id mapping   │
└────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Agent (4 Nodes)

```
create_initial_state(query, llm_provider)
           │
           ▼
    ┌─────────────┐
    │   PLANNER   │  LLM decomposes query into ordered task list
    │             │  e.g. ["Score customers", "Draft messages"]
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   EXECUTOR  │◄──────────────────────────┐
    │             │                           │
    │  Per task:  │                           │
    │  1. predict_conversion_probability      │
    │  2. get_transaction_summary             │
    │  3. draft_outreach_message              │
    └──────┬──────┘                           │
           │                                  │
           ▼                                  │
    ┌─────────────┐   more tasks?             │
    │  REFLECTOR  │──────────────────────────►┘
    │             │
    │  done?      │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  RESPONDER  │  LLM synthesises final answer
    └──────┬──────┘
           │
          END
```

**State carried across nodes:**
```python
RMAgentState = {
    "query": str,
    "task_plan": List[str],
    "current_plan_step": int,
    "customer_set": List[Customer],
    "scores_cache": Dict[str, float],        # conv probability per customer
    "behaviors_cache": Dict[str, dict],      # transaction summaries
    "drafts": List[DraftMessage],
    "tool_call_log": List[ToolCallRecord],   # full execution trace
    "final_answer": str,
    "error": str | None,
}
```

---

## Tool Registry (8 tools)

| Tool | Module | Input | Output |
|---|---|---|---|
| `query_customers` | customer_tool | filters dict | List[Customer] |
| `get_customer_profile` | customer_tool | customer_id | Customer + enrichment |
| `get_transaction_summary` | transaction_tool | customer_id, days | spend, velocity, categories |
| `score_customer_value` | scoring_tool | customer_id | score 0–100, tier, factors |
| `predict_conversion_probability` | scoring_tool | customer_id, product_id | prob%, top_signals |
| `recommend_products` | product_tool | customer_id | ranked products + reasons |
| `draft_outreach_message` | message_tool | name, product_id, conv_prob, txn_context | message, EMI, rate, tone |
| `send_outreach_message` | outreach_tool | customer_id, phone, message, product_id | interaction_id, status, SID |

---

## Message Drafting Pipeline

```
draft_outreach_message(customer_id, product_id, conv_prob, txn_context)
            │
            ├─ _rate_for_credit_score(credit_score)
            │    750+ → 10.5%  |  700–749 → 11.5%  |  650–699 → 12.5%  |  <650 → 13.0%
            │
            ├─ _emi(principal, rate, 60 months)
            │    P × r(1+r)^n / ((1+r)^n − 1)
            │
            ├─ _build_trust_line(customer)
            │    "13-year loyal customer | Excellent credit (793)"
            │
            ├─ _conversion_to_tone(conv_prob)
            │    ≥40% → warm  |  15–40% → professional  |  <15% → urgent
            │
            └─ Product builder (PL / CC / HL / FD)
                 Returns: primary_message, short_variant,
                          personalization_note, offer_expiry
```

---

## WhatsApp Inbound Flow (Both Backends)

### Backend A: WhatsApp Web JS

```
Customer sends WhatsApp message
        │
        ▼
whatsapp-web.js  client.on("message")
        │
        ▼
POST /api/outreach/reply  { phone, message }
        │
        ├─ _sandbox_sessions[phone] → customer_id, product_id, outreach_msg
        │   (or IdentityGraph lookup for production)
        │
        ├─ _classify_intent(message)  → YES / NO / PRICE_OBJECTION / ...
        │
        ├─ Update Interaction.pipeline_state
        │
        ├─ generate_sales_reply(customer, product, ...)
        │   ├─ Fast path: template reply (common intents, <50ms)
        │   └─ LLM path: Gemini → Ollama fallback (nuanced/multi-turn)
        │
        └─ Return { ai_reply: "..." }
                │
                ▼
        client.sendMessage(msg.from, aiReply)
```

### Backend B: Twilio

```
Customer taps quick-reply button
        │
        ▼
Twilio POST (form-encoded) to webhook URL
        │
        ▼
Cloudflare Tunnel → POST /api/outreach/twilio-webhook
        │
        ├─ form.get("ButtonText") → "yes" | "callback" | "no"
        │   BUTTON_MAP: "yes" → "yes interested"
        │               "callback" → "call me callback"
        │               "no" → "not interested"
        │
        ├─ Same sandbox_sessions lookup + intent classify
        │
        ├─ Same AI sales agent → ai_reply string
        │
        └─ Return TwiML:
           <?xml version="1.0"?>
           <Response><Message>{ai_reply}</Message></Response>
                │
                ▼
        Twilio sends reply to customer's WhatsApp
```

---

## Sandbox Session Map

Problem: In sandbox mode, the RM sends to their own phone. When they reply, the reply comes from their number — not the customer's. The backend needs to know which customer's context to use.

```python
# In-memory dict — registered when send-batch fires
_sandbox_sessions: dict = {
    "+917838146286": {
        "customer_id": "CUST000006",    # Aaina Karpe
        "product_id":  "PL001",         # Personal Loan
        "message":     "Hi Aaina! ...", # original outreach text
    }
}

# In /reply and /twilio-webhook:
sandbox_ctx = _sandbox_sessions.get(phone)
if sandbox_ctx:
    # use sandbox context → correct customer
else:
    # production → IdentityGraph lookup by phone
```

---

## LLM Provider Abstraction

```python
class LLMProvider(ABC):
    def complete(self, messages: List[LLMMessage], **kwargs) -> str: ...
    def function_call(self, messages, functions, **kwargs) -> dict: ...

# Implementations:
GeminiProvider   → gemini-2.0-flash-exp
OllamaProvider   → any local model (gemma3:4b, llama3.1:8b, ...)
NvidiaProvider   → NVIDIA NIM (llama-3.1-70b-instruct, nemotron-70b)

# Swap with zero code change:
LLM_BACKEND=gemini    # .env
LLM_BACKEND=ollama
LLM_BACKEND=nvidia
```

The frontend model picker supports **per-request override** — planner and executor can use different models in the same agent run.

---

## Twilio Content Template

**Template SID:** `HX2bc78adf93fb63c4b571799910d53776`
**Type:** `twilio/quick-reply`
**Variables:** `{1}` name, `{2}` product, `{3}` amount, `{4}` rate, `{5}` EMI, `{6}` expiry

Variable extraction happens automatically via regex in `outreach_tool._parse_loan_vars()` — parses the AI-drafted message text to fill template variables. Falls back to plain `body` text if parsing fails.

---

## Pipeline Stage Machine

```
NEW
 └─► CONTACTED      (message sent)
       └─► ENGAGED         (opened / generic reply)
             ├─► CONSIDERING      (thinking / maybe)
             ├─► CALLBACK_REQUESTED  (wants a call)
             ├─► INTERESTED          (YES / keen)
             │     └─► CONVERTED / WON
             ├─► OBJECTION           (price / already has)
             └─► DECLINED            (NO / not interested)
                   └─► LOST
```

Each stage transition saves a new `Interaction` row with `pipeline_state` set and (for customer replies) `response` field populated. AI replies are saved as a separate `Interaction` row with `framework_used = "AI_AGENT"`.
