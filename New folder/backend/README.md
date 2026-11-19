# 🏦 Banking CRM Agent — AI-Powered Relationship Manager

An end-to-end agentic AI system for banking relationship management. A Relationship Manager types a natural language query → the LangGraph agent plans, scores, and drafts personalised WhatsApp outreach → messages are sent via WhatsApp Web (free) or Twilio (with rich templates + quick-reply buttons) → customer replies are handled automatically by an AI sales agent that speaks as "Rahul, RM" → every reply, intent, and stage change is tracked in the CRM pipeline.

---

## 🎬 What It Does End-to-End

```
RM types: "Find premium customers in Mumbai and draft a personal loan message"
         ↓
    LangGraph Agent (4 nodes, 13 tool calls)
    ├─ Planner   → breaks query into tasks
    ├─ Executor  → calls scoring + transaction + message tools per customer
    ├─ Reflector → loops until all tasks done
    └─ Responder → synthesises answer with real loan figures
         ↓
    React Dashboard shows:
    ├─ 3 customer drafts with real EMIs, rates, personalisation signals
    ├─ Conversion probability badges (63% warm | 2% urgent)
    └─ WhatsApp bubble preview with ✓✓ ticks
         ↓
    RM clicks "Send" → selects WhatsApp Web or Twilio tab
         ↓
    WhatsApp Web  → free, uses RM's own account via QR session
    Twilio        → Content API template + 3 quick-reply buttons
                    [✅ Yes, Interested!] [📞 Call Me] [❌ Not Now]
         ↓
    Customer taps a button on WhatsApp
         ↓
    Twilio webhook → Cloudflare tunnel → FastAPI /api/outreach/twilio-webhook
         ↓
    AI Sales Agent (Rahul, RM) classifies intent and replies:
    ├─ YES        → "Great, Aaina! 🎉 Your ₹19.1L at 10.5% p.a. is pre-approved.
    │               What time works — morning or afternoon?"
    ├─ 📞 Call Me → "Of course! Morning (10am–12pm) or afternoon (2pm–5pm)?"
    ├─ Price obj  → reframes EMI, suggests longer tenure
    ├─ Docs query → lists PAN, salary slips, Aadhaar (KYC pre-verified note)
    └─ ❌ Not Now → graceful exit, offer stays open till month-end
         ↓
    Pipeline stage updated: CONTACTED → INTERESTED / CALLBACK_REQUESTED / DECLINED
    Conversations dashboard shows live thread with AI reply
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                         │
│  Workspace  │  Customers  │  Analytics  │  Conversations (live) │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend  :8000                          │
│                                                                  │
│  /api/agent/run          LangGraph pipeline                      │
│  /api/outreach/send-batch  WhatsApp Web + Twilio dispatch        │
│  /api/outreach/reply       WhatsApp Web inbound → AI agent       │
│  /api/outreach/twilio-webhook  Twilio button taps → AI agent     │
│  /api/outreach/pipeline    Live funnel + reply log               │
│  /api/customers/*          Filter, score, recommend              │
│  /api/analytics/*          KPIs, charts, campaigns               │
└──────────┬───────────────────────────────────┬──────────────────┘
           │                                   │
┌──────────▼──────────┐             ┌──────────▼──────────┐
│  WhatsApp Web JS    │             │   Twilio Content API │
│  Node.js :3001      │             │   +14155238886       │
│  whatsapp-web.js    │             │   Quick-reply buttons│
│  QR session         │             │   Template SID:      │
│  AI auto-reply      │             │   HX2bc78adf93fb...  │
└──────────┬──────────┘             └──────────┬──────────┘
           │                                   │
┌──────────▼───────────────────────────────────▼──────────┐
│               SQLite  banking_crm.db                     │
│  customers (500) │ transactions (8,569) │ interactions   │
│  products (4)    │ identity_graph       │ pipeline log   │
└─────────────────────────────────────────────────────────┘
```

---

## 🧠 LangGraph Agent Pipeline

Four nodes, runs in a loop until all tasks complete:

```
create_initial_state(query)
        ↓
   [PLANNER]  — LLM decomposes query into ordered task list
        ↓
   [EXECUTOR] — picks next task, calls tools, caches results
        │
        │  Tools called per customer:
        │   1. predict_conversion_probability → conv% + top signals
        │   2. get_transaction_summary        → 90-day spend pattern
        │   3. draft_outreach_message         → real EMI, rate, tone
        ↓
   [REFLECTOR] — more tasks? → EXECUTOR | done? → RESPONDER
        ↓
   [RESPONDER] — LLM synthesises final answer with all results
```

**Typical run:** 3 customers × (scoring + txn + draft) = **13 tool calls**

---

## 🤖 AI Sales Agent

`src/tools/sales_agent.py` — responds to incoming WhatsApp messages as Rahul (RM)

### Intent Classifier (keyword-based, no LLM cost)

| Intent | Triggers | Reply |
|---|---|---|
| `YES` | "yes", "interested", "ok", "haan" | Confirms, asks callback time |
| `NO` | "no", "nahi", "not interested" | Graceful exit, offer open till month-end |
| `PRICE_OBJECTION` | "expensive", "high rate", "EMI" | Reframes, suggests longer tenure |
| `DOCUMENTS` | "document", "KYC", "what do I need" | PAN + salary slips + Aadhaar (KYC pre-verified) |
| `TIMELINE` | "how long", "fast", "disbursal" | 24 hrs for existing customers, 100% digital |
| `WANTS_CALLBACK` | "call", "speak", "phone" | Morning vs afternoon preference |
| `THINKING` | "maybe", "later", "will let you know" | Rate valid till month-end, no pressure |
| `HAS_PRODUCT` | "already have", "existing loan" | Fresh facility, different use case |
| `GENERAL` | anything else | Falls through to LLM (Gemini/Ollama) |

**Fast path:** template reply for common intents (saves LLM quota, <50ms)
**LLM path:** Gemini → Ollama fallback for nuanced / multi-turn conversations

---

## 💰 Real Financial Calculations

No placeholder tokens. Every message has actual numbers computed from the customer's DB record.

```python
# Rate mapped from credit score band
def _rate_for_credit_score(score):
    if score >= 750: return 10.5   # excellent
    if score >= 700: return 11.5   # good
    if score >= 650: return 12.5   # fair
    return 13.0                    # standard

# Standard EMI formula
def _emi(principal, annual_rate_pct, months):
    r = annual_rate_pct / 100 / 12
    return principal * r * (1+r)**months / ((1+r)**months - 1)

# Loan amount = min(max(annual_income, 200000), 2500000)
```

**Conversion probability** drives message tone:
- ≥ 40% → `warm` (personal, relationship-focused)
- 15–40% → `professional`
- < 15% → `urgent` (scarcity + expiry date)

---

## 📦 Project Structure

```
banking-crm-backend/
├── .env                          # All config (see Configuration section)
├── requirements.txt
├── banking_crm.db                # SQLite — 500 customers, 8,569 txns
│
├── src/
│   ├── api.py                    # FastAPI app — all REST endpoints
│   ├── config.py                 # Pydantic settings
│   ├── database.py               # SQLAlchemy models
│   │
│   ├── llm/
│   │   ├── base.py               # LLMProvider abstract + LLMMessage
│   │   ├── gemini.py             # Google Gemini 2.0 Flash
│   │   ├── ollama.py             # Local Ollama (any model)
│   │   └── nvidia.py             # NVIDIA NIM (free cloud tier)
│   │
│   ├── tools/
│   │   ├── customer_tool.py      # query_customers, get_customer_profile
│   │   ├── transaction_tool.py   # get_transaction_summary
│   │   ├── scoring_tool.py       # score_customer_value, predict_conversion_probability
│   │   ├── product_tool.py       # recommend_products
│   │   ├── message_tool.py       # draft_outreach_message (real EMI/rate)
│   │   ├── outreach_tool.py      # send_outreach_message (WhatsApp Web + Twilio)
│   │   └── sales_agent.py        # AI sales agent — intent + reply generation
│   │
│   └── rm_agent/
│       ├── state.py              # RMAgentState TypedDict
│       ├── nodes.py              # planner, executor, reflector, responder
│       ├── graph.py              # LangGraph StateGraph assembly
│       └── tool_registry.py      # Tool schemas (JSON) + execute_tool()
│
└── whatsapp-service/
    ├── server.js                 # Node.js WhatsApp Web bridge
    └── package.json

agentic-bank-insight/             # React + Vite frontend
├── src/
│   ├── lib/api.ts                # Typed API client (all endpoints)
│   ├── routes/                   # TanStack Router pages
│   └── components/pages/
│       ├── WorkspacePage.tsx     # Agent chat + Send modal (WhatsApp/Twilio)
│       ├── ConversationsPage.tsx # Live WhatsApp inbox + pipeline funnel
│       ├── CustomersPage.tsx     # Customer browser + scoring
│       ├── AnalyticsPage.tsx     # KPIs, charts, campaigns
│       └── DashboardPage.tsx     # Overview
```

---

## 🚀 Running the System

### Prerequisites
```bash
node --version   # v18+
python3 --version  # 3.11+
```

### 1. Backend
```bash
cd banking-crm-backend
pip install -r requirements.txt
python -m uvicorn src.api:app --port 8000 --reload
```

### 2. WhatsApp Web Bridge (free sender)
```bash
cd banking-crm-backend/whatsapp-service
npm install
node server.js
# Open http://localhost:3001 → scan QR with WhatsApp → Linked Devices
# Session is saved — subsequent starts connect automatically
```

### 3. Frontend
```bash
cd agentic-bank-insight
npm install
npm run dev
# Opens on http://localhost:8080
```

### 4. Twilio Webhook (for button-tap AI replies)
```bash
# Install cloudflared (free tunnel, no signup)
brew install cloudflare/cloudflare/cloudflared

# Expose backend publicly
cloudflared tunnel --url http://localhost:8000 --no-autoupdate
# Copy the https://xxx.trycloudflare.com URL

# Paste into Twilio Console:
# https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
# Field: "When a message comes in"
# Value: https://xxx.trycloudflare.com/api/outreach/twilio-webhook
```

---

## ⚙️ Configuration (.env)

```bash
# ── LLM ─────────────────────────────────────────────────────────────
LLM_BACKEND=gemini                    # gemini | ollama | nvidia
GEMINI_API_KEY=AIza...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama-3.1-70b-instruct

# ── CRM ─────────────────────────────────────────────────────────────
CRM_BACKEND=sqlite
DATABASE_URL=sqlite:///./banking_crm.db

# ── Sender backend ───────────────────────────────────────────────────
# whatsapp-web = free (own WhatsApp account via QR)
# twilio       = Twilio Content API with quick-reply buttons
# mock         = logs to DB only, no real send
SENDER_BACKEND=whatsapp-web

# ── WhatsApp Web bridge ──────────────────────────────────────────────
WHATSAPP_SERVICE_URL=http://localhost:3001

# ── Sandbox mode ─────────────────────────────────────────────────────
# sandbox=true routes ALL messages to one test number
# prod mode sends to each customer's actual CRM number
WHATSAPP_SANDBOX=true
WHATSAPP_SANDBOX_NUMBER=+917838146286  # your test number

# ── Twilio ───────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID=ACxxx...
TWILIO_AUTH_TOKEN=xxx...
TWILIO_PHONE_NUMBER=+14155238886       # WhatsApp sandbox sender
TWILIO_WHATSAPP_CONTENT_SID=HX2bc78adf93fb63c4b571799910d53776
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/agent/run` | Run LangGraph agent on a natural language query |
| `GET` | `/api/customers` | Filter customers (segment, city, income, credit score) |
| `GET` | `/api/customers/{id}/score` | CLV score + contributing factors |
| `GET` | `/api/customers/{id}/recommendations` | Product recommendations + affinity scores |
| `GET` | `/api/customers/{id}/transactions` | 90-day transaction summary |
| `POST` | `/api/outreach/send-batch` | Send messages via WhatsApp Web or Twilio |
| `POST` | `/api/outreach/reply` | WhatsApp Web inbound → AI sales agent |
| `POST` | `/api/outreach/twilio-webhook` | Twilio button taps → AI agent → TwiML reply |
| `GET` | `/api/outreach/pipeline` | Funnel stages + recent reply log |
| `GET` | `/api/outreach/whatsapp-status` | WhatsApp Web connection status + QR |
| `GET` | `/api/outreach/phone/{customer_id}` | Customer phone from IdentityGraph |
| `GET` | `/api/analytics/kpis` | Dashboard KPIs |
| `GET` | `/api/analytics/charts` | Chart data (segment breakdown, conversion trend) |
| `GET` | `/api/analytics/campaigns` | Campaign history |
| `GET` | `/api/settings` | Current backend config |

---

## 📊 Scoring & Signals

### CLV Score (0–100, rule-based for explainability)
```
score = 0.20 × norm(annual_income)
      + 0.20 × norm(monthly_avg_balance)
      + 0.15 × tenure_years / 20
      + 0.15 × products_held / 4
      + 0.20 × norm(credit_score)
      + 0.10 × kyc_verified_bonus

Tiers: High Value (≥75) | Medium (50–75) | Standard (<50)
```

### Conversion Probability (9 signals)
| Signal | Weight | Notes |
|---|---|---|
| Product gap | +25% | Customer doesn't own the product |
| Monthly balance tier | +5–20% | Higher balance → more likely |
| Credit score | +0–15% | ≥750 gets max boost |
| Loyalty (tenure) | +5–10% | 5+ years loyal |
| Active transactions | +5% | Transacted in last 30 days |
| Salary inflow | +8% | Salary credited this month |
| Spending spike | +10% | 20%+ spend increase |
| Already owns product | ×0.05 | Early exit — not a good lead |

---

## 💬 WhatsApp Delivery

### Backend 1: WhatsApp Web (Free)
- Uses your personal WhatsApp account via QR code session
- `whatsapp-web.js` + Puppeteer runs in Node.js
- Session persists — no re-scan needed after first setup
- AI auto-reply is ON by default (`AI_AUTO_REPLY=true`)
- Set `AI_AUTO_REPLY=false` to disable automatic replies

### Backend 2: Twilio Content API (Production-grade)
- Template: rich message + 3 quick-reply buttons
- Template SID: `HX2bc78adf93fb63c4b571799910d53776`
- Variables auto-extracted from AI-drafted message text
- Button tap → Twilio POST → `/api/outreach/twilio-webhook` → TwiML reply

```
Template preview:
┌─────────────────────────────────────────────┐
│ Hi Aaina! 🎉 You have been pre-approved for │
│ a Personal Loan:                             │
│                                             │
│ 💰 Amount: ₹19.1L                           │
│ 📊 Rate: 10.5% p.a. (fixed)                 │
│ 💳 EMI: ₹25,900/month                       │
│ ⏰ Valid till: 31 May 2026                   │
│                                             │
│ 100% digital · No branch visit · 24 hrs     │
├─────────────────────────────────────────────┤
│ ✅ Yes, Interested!                          │
├─────────────────────────────────────────────┤
│ 📞 Call Me                                  │
├─────────────────────────────────────────────┤
│ ❌ Not Now                                   │
└─────────────────────────────────────────────┘
```

### Sandbox vs Production
| Mode | Sandbox | Production |
|---|---|---|
| All messages go to | Single test number (configurable) | Each customer's actual CRM phone |
| Twilio replies route to | Same test number | IdentityGraph lookup |
| Sandbox number | Default: `+917838146286` | N/A |

---

## 🔄 Sales Pipeline Stages

```
NEW → CONTACTED → ENGAGED → CONSIDERING → CALLBACK_REQUESTED → INTERESTED
                                                   ↓
                                    OBJECTION → DECLINED
                                                   ↓
                                              CONVERTED / WON
```

Each stage transition is logged as an Interaction record. The `/api/outreach/pipeline` endpoint returns:
- Funnel count per stage
- Total contacted / replied / converted
- Last 20 customer replies with paired AI responses

---

## 🤖 LLM Backends

| Backend | Speed | Notes |
|---|---|---|
| `gemini` | Fast | Gemini 2.0 Flash — 20 req/day free tier |
| `nvidia` | Fast | NVIDIA NIM (Llama 70B, Nemotron 70B) — free cloud |
| `ollama` | Local | Gemma 3 4B, Llama 3.1 8B — fully offline |

Switch via `LLM_BACKEND` in `.env` or per-request in the UI (model picker in Workspace).

Planner and executor can use **different models** — e.g., Gemini for planning (better reasoning) + Ollama for execution (no quota usage).

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| LangGraph over plain ReAct | Explicit nodes → observable, testable, debuggable |
| WhatsApp Web as primary | Zero cost, no API approval, uses existing number |
| Twilio Content API for prod | Approved templates, buttons, delivery receipts |
| Intent classifier without LLM | <1ms, no quota, handles 90% of replies correctly |
| Template shortcuts + LLM fallback | Fast for common intents, smart for edge cases |
| Real EMI formula in messages | No placeholder hallucination — every number is from DB |
| Sandbox session map | Allows testing with own phone without faking CRM numbers |
| Cloudflare tunnel | Free, no account, instant public URL for Twilio webhook |
| Rule-based CLV scoring | Explainability for banking regulatory compliance |
| Conversion tone mapping | 3 tones driven by probability — not random |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TanStack Router, Tailwind CSS, Framer Motion, Recharts |
| Backend | FastAPI, Python 3.12, SQLAlchemy, Pydantic v2 |
| Agent | LangGraph, custom tool registry, 4-node state machine |
| LLM | Google Gemini 2.0 Flash / NVIDIA NIM / Ollama |
| Database | SQLite (500 customers, 8,569 transactions, 592 interactions) |
| WhatsApp (free) | whatsapp-web.js, Puppeteer, Node.js Express |
| WhatsApp (prod) | Twilio WhatsApp Business API, Content API v1 |
| Tunnel | Cloudflare Tunnel (cloudflared) |

---

## 🧪 Quick Smoke Test

```bash
# 1. Agent pipeline
curl -s -X POST http://localhost:8000/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "Find 1 premium customer in Mumbai and draft a personal loan message", "llm_backend": "gemini"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Tool calls:', d['tool_call_count']); print('Drafts:', len(d['drafts']))"
# Expected: Tool calls: 13, Drafts: 3

# 2. AI sales agent — YES reply
curl -s -X POST http://localhost:8000/api/outreach/reply \
  -H "Content-Type: application/json" \
  -d '{"phone": "+917838146286", "message": "yes interested"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['intent'], '|', d['pipeline_state']); print(d['ai_reply'])"
# Expected: YES | INTERESTED | "That's great, Aaina! 🎉 ..."

# 3. WhatsApp status
curl -s http://localhost:8000/api/outreach/whatsapp-status
# Expected: {"ready": true, "state": "READY"}

# 4. Pipeline funnel
curl -s http://localhost:8000/api/outreach/pipeline | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'Replied: {d[\"total_replied\"]} | Converted: {d[\"total_converted\"]}')
"
```

---

## 🗺️ Future Roadmap

- **Twilio Voice + AI** — real phone calls with AI doing the pitch (Twilio Voice + ElevenLabs TTS)
- **HubSpot CRM adapter** — pluggable CRM backend swap demo
- **A/B variant tracking** — compare AIDA vs SPIN vs Cialdini conversion rates
- **Send-time optimisation** — per-customer best response window from transaction history
- **Suppression gates** — DND, opt-out, frequency cap (code rules, not LLM)
- **Human escalation** — "Escalate to RM" button routes to human with conversation summary
