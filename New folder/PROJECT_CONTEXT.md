# BankingRM AI — Full Project Context

## What is this?

BankingRM AI is an **agentic CRM for bank Relationship Managers (RMs)**. It uses AI to help RMs find the right customers, generate personalised WhatsApp outreach messages, and manage the entire sales pipeline — from lead discovery to customer reply — with minimal manual effort.

The RM logs in, picks a product (e.g. Personal Loan), the AI finds the best-fit customers, drafts personalised WhatsApp messages for each, and sends them. When customers reply on WhatsApp, the AI reads the reply and responds automatically.

---

## Who is it for?

- **Primary user**: Relationship Managers at a retail bank (e.g. HDFC, ICICI style)
- **Use case**: Running outreach campaigns for products like Personal Loans, Credit Cards, Home Loans, Fixed Deposits
- **Scale**: 500 customers in DB, campaigns of 20–50 leads at a time

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (React)                  │
│  Campaign Builder → Review Leads → Send → Done      │
│  RM AI Workspace → Agent drafts → Per-customer send │
│  Conversation Console → Live WhatsApp inbox         │
│  Customer Intelligence → Search, filter, profile   │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (proxied via Vite)
                     ▼
┌─────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI)                   │
│                                                     │
│  /api/campaigns/compose   → AI message per lead     │
│  /api/outreach/send-batch → Twilio WhatsApp send    │
│  /api/outreach/webhook    → Inbound reply handler   │
│  /api/agent/run           → LangGraph RM agent      │
│  /api/customers           → Customer search         │
└───────┬──────────────┬──────────────────────────────┘
        │              │
        ▼              ▼
  ┌──────────┐   ┌───────────────────────────────┐
  │  SQLite  │   │        LangGraph Pipeline      │
  │  500     │   │  Planner → Executor →          │
  │customers │   │  Reflector → Responder         │
  │  748     │   └───────────────┬───────────────┘
  │interactions│                 │
  └──────────┘           ┌──────▼──────┐
                         │  OpenAI     │
                         │  GPT-4o     │
                         └─────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                  TWILIO (WhatsApp)                  │
│  Sandbox number: +14155238886                       │
│  Inbound webhook → /api/outreach/webhook            │
│  Cloudflare tunnel exposes localhost to Twilio      │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build tool | Vite |
| Routing | TanStack Router (file-based) |
| UI components | shadcn/ui + Radix UI primitives |
| Styling | Tailwind CSS |
| Animations | Framer Motion |
| Charts | Recharts |
| State | React `useState` / `useEffect` (no Redux) |
| Dev server | `localhost:8080` |

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI (Python 3.12) |
| ORM | SQLAlchemy |
| Database | SQLite (`banking_crm.db`) |
| AI model | OpenAI GPT-4o |
| Agent framework | LangGraph 0.1 |
| WhatsApp | Twilio SDK |
| Tunnel | Cloudflare (`cloudflared`) |
| Dev server | `localhost:8000` |

---

## Pages & Features

### 1. Campaign Builder (`/campaign`)
3-step wizard: Configure → Review Leads → Done

- **Step 1 – Configure**: Pick product, customer segment (mass/affluent/premium), city, min conversion probability, message tone (warm/professional/urgent), max leads
- **Step 2 – Review Leads**: AI-scored lead cards ranked by conversion probability. Each card shows:
  - Customer name, city, segment, likelihood badge (e.g. 78.7% likely)
  - Reasons (product gap, high balance, lifestyle spender, etc.)
  - Pre-drafted WhatsApp message
  - **Edit button** — opens inline textarea to manually edit the message
  - **✨ Regenerate button** — calls AI to rewrite the message fresh
- **Action bar** (bottom):
  - **Sandbox Mode toggle** (on by default) — routes all messages to RM's own number for testing
  - Phone number input pre-filled with `+917838146286`
  - Dynamic send button: `"Send 20 → +917838146286 (sandbox)"` or `"Send Campaign (20 leads)"`
- **Step 3 – Done**: Confirmation screen with "View Conversations" and "New Campaign"

### 2. RM AI Workspace (`/workspace`)
AI agent interface where the RM can type a natural language request like "find affluent customers in Mumbai for a credit card campaign" and the LangGraph agent handles it end-to-end.

- Agent runs 4-node pipeline: Planner → Executor → Reflector → Responder
- Shows reasoning trace and drafted messages
- **Draft cards**: each has a per-customer "Send" button (sends to that customer only)
- **"Send to all customers"** button opens a modal (built with `ReactDOM.createPortal` to avoid Framer Motion transform z-index bug)
- **MVP Sampling Note**: explains that "50 customers sampled from 500" with an expandable "Read more" section explaining why and how to fix it properly with vector search

### 3. Conversation Console (`/conversations`)
Live WhatsApp inbox. Shows all inbound customer messages and AI replies in real time.

### 4. Customer Intelligence (`/customers`)
Search and filter the 500-customer database. View full profiles, interaction history, product eligibility.

### 5. Outreach Center (`/outreach`)
Manual outreach management, campaign history, interaction logs.

### 6. Analytics (`/analytics`)
Pipeline dashboard — conversion rates, campaign performance, segment breakdown.

---

## Database Schema

### Customer (500 rows)
```
customer_id       TEXT PRIMARY KEY   e.g. "CUST001"
name              TEXT
age               INTEGER
gender            TEXT
city              TEXT               e.g. "Mumbai", "Delhi", "Bangalore"
segment           TEXT               "mass" | "affluent" | "premium"
occupation        TEXT
annual_income     FLOAT              in rupees
kyc_status        TEXT               "verified" | "pending"
relationship_years INTEGER           years as bank customer
has_credit_card   BOOLEAN
has_personal_loan BOOLEAN
has_home_loan     BOOLEAN
has_fd            BOOLEAN
monthly_avg_balance FLOAT            in rupees
credit_score      INTEGER            300–900
last_contact_date DATETIME
created_at        DATETIME
updated_at        DATETIME
```

### Interaction (748 rows)
```
interaction_id    TEXT PRIMARY KEY
customer_id       TEXT (FK → Customer)
date              DATETIME
channel           TEXT               "whatsapp" | "email" | "call"
product_offered   TEXT               product_id
message           TEXT               outbound message sent
response          TEXT               customer reply
converted         BOOLEAN
pipeline_state    TEXT               "CONTACTED" | "REPLIED" | "CONVERTED" | "REJECTED"
framework_used    TEXT               "AIDA" | "TWILIO_INBOUND" | "AI_AGENT"
created_at        DATETIME
```

### Product (4 rows)
```
product_id        TEXT    "PL001" | "CC001" | "HL001" | "FD001"
name              TEXT    "Personal Loan" | "Premium Credit Card" | "Home Loan" | "Fixed Deposit"
product_type      TEXT
min_income        FLOAT
min_credit_score  INTEGER
eligible_segments TEXT
interest_rate     FLOAT   PL001: 10.5%, HL001: 7.2%, FD001: 6.0%
features          TEXT
```

---

## AI Pipeline (LangGraph)

4-node graph that runs when the RM submits a query in the Workspace:

```
START → Planner → Executor → Reflector → Responder → END
              ↑_______________|  (retry loop if needed)
```

- **Planner**: Understands the RM's intent, selects which tools to call
- **Executor**: Calls the tools (query_customers, score_lead, draft_outreach_message)
- **Reflector**: Checks quality of results, decides if retry is needed
- **Responder**: Formats final output — leads list + drafted messages

---

## WhatsApp / Twilio Flow

### Outbound (RM sends campaign)
```
RM clicks Send → /api/outreach/send-batch
  → sandbox=true: all messages → +917838146286 (RM's number)
  → sandbox=false: messages → real customer phone numbers
  → Twilio API sends WhatsApp from +14155238886
  → Interaction saved to DB with pipeline_state="CONTACTED"
```

### Inbound (customer replies)
```
Customer types reply on WhatsApp
  → Twilio webhook → /api/outreach/webhook
  → Identify customer:
      1. Check _sandbox_sessions (in-memory FIFO queue)
      2. Fallback: DB lookup — last CONTACTED interaction with no prior reply
  → LangGraph agent generates AI reply
  → Twilio sends reply back to customer
  → Interaction saved with pipeline_state="REPLIED", framework_used="AI_AGENT"
```

### Sandbox Session Queue
- `_sandbox_sessions` is a dict: `phone → [list of customer contexts]`
- FIFO — first customer sent gets matched to first reply received
- **Wiped on backend restart** — fallback uses DB subquery

### Cloudflare Tunnel
- Exposes `localhost:8000` to public internet so Twilio can reach the webhook
- URL changes every restart (e.g. `numeric-analyses-ages-opposed.trycloudflare.com`)
- Must update **Twilio Console → Messaging → Sandbox settings → When a message comes in** with new URL after every restart

---

## MCP Server (AI Tool Integration)

`src/mcp_server.py` exposes 7 tools via Model Context Protocol so any MCP-compatible AI (Claude Code, Cursor, Windsurf) can directly call the banking CRM:

| Tool | Description |
|---|---|
| `query_customers` | Filter customers by segment, city, income, credit score, etc. |
| `get_customer_profile` | Full profile for one customer by ID |
| `score_lead` | Conversion probability for a customer + product pair |
| `compose_message` | AI-draft a WhatsApp message (AIDA framework, tone variants) |
| `get_customer_interactions` | Interaction history for a customer |
| `send_whatsapp_message` | Send via Twilio (sandbox-safe by default) |
| `find_best_leads` | Top N leads for a product, ranked by conversion score |

Config locations:
- Claude Code: `~/.claude/claude_desktop_config.json` ✅ (already set)
- Cursor: `banking-crm-backend/.cursor/mcp.json` ✅ (already set)
- Windsurf: `~/.codeium/windsurf/mcp_config.json`

---

## Key Design Decisions & Known Limitations

### MVP Limitation — Customer Sampling
`query_customers(limit=50)` returns the first 50 customers in DB insertion order — not the best 50. This means campaign targeting is random, not ranked.

**Quick fix**: Add `ORDER BY credit_score DESC, annual_income DESC` before LIMIT  
**Proper fix**: OpenAI `text-embedding-3-small` embeddings + pgvector/Pinecone ANN search

### Portal Modal Fix
Framer Motion applies `transform` CSS on animated parent containers, which creates a new CSS containing block — breaking `position: fixed` modals. Fixed by wrapping all modals with `ReactDOM.createPortal(content, document.body)`.

### Sandbox vs Production
- Sandbox mode is always ON by default in the Campaign Builder
- The sandbox_number (`+917838146286`) must have joined the Twilio sandbox by texting the join phrase to `+14155238886`
- In production, remove sandbox mode and use real customer phone numbers from the DB

---

## File Structure

```
banking-crm-backend/
├── src/
│   ├── api.py                  ← All FastAPI routes (main file)
│   ├── app.py                  ← FastAPI app init
│   ├── database.py             ← SQLAlchemy models + DB init
│   ├── mcp_server.py           ← MCP server (AI tool integration)
│   ├── config.py               ← Environment config
│   ├── rm_agent/
│   │   └── nodes.py            ← LangGraph 4-node pipeline
│   ├── tools/
│   │   ├── customer_tool.py    ← query_customers, get_customer_profile
│   │   ├── message_tool.py     ← draft_outreach_message (AIDA)
│   │   ├── scoring_tool.py     ← lead conversion probability
│   │   ├── outreach_tool.py    ← send_whatsapp, batch send
│   │   └── sales_agent.py      ← sales agent logic
│   └── senders/                ← Twilio sender abstraction

agentic-bank-insight/
├── src/
│   ├── routes/                 ← TanStack Router file-based routes
│   │   ├── campaign.tsx        ← /campaign route
│   │   ├── workspace.tsx       ← /workspace route
│   │   └── ...
│   ├── components/
│   │   ├── AppLayout.tsx       ← Sidebar nav layout
│   │   └── pages/
│   │       ├── CampaignPage.tsx    ← Campaign Builder (main feature)
│   │       ├── WorkspacePage.tsx   ← RM AI Workspace
│   │       ├── ConversationsPage.tsx
│   │       ├── CustomersPage.tsx
│   │       ├── OutreachPage.tsx
│   │       └── AnalyticsPage.tsx
│   └── lib/
│       └── api.ts              ← API helper functions
```

---

## Environment Variables Required

```env
# Backend (.env in banking-crm-backend/)
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

---

## How to Run

```bash
# Backend
cd banking-crm-backend
uvicorn src.app:app --reload --port 8000

# Frontend
cd agentic-bank-insight
npm run dev     # runs at localhost:8080

# Cloudflare tunnel (for Twilio webhook)
cloudflared tunnel --url http://localhost:8000
# Copy new URL → paste into Twilio Console sandbox settings

# MCP Server (for AI tool integration)
cd banking-crm-backend
python3 -m src.mcp_server
```

---

## GitHub Repo

- Main repo: https://github.com/namanchitkara2/bankrm-ai
  - `frontend/` — React/Vite app (was: agentic-bank-insight)
  - `backend/`  — FastAPI backend (was: banking-crm-backend)

## Local Paths

- Frontend: `/Users/namanchitkara/agentic-bank-insight`
- Backend: `/Users/namanchitkara/banking-crm-backend`
- Canonical copy: `/Users/namanchitkara/bankrm-ai/` (frontend/ + backend/ + review/)
- Review folder: `/Users/namanchitkara/bankrm-ai/review/` (5 key files flat)
