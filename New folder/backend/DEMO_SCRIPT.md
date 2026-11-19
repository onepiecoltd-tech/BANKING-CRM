# Demo Script — Banking CRM Agent

A 10-minute walkthrough to show every layer of the system to an interviewer.

---

## 0. Start Everything (2 min)

```bash
# Terminal 1 — Backend
cd banking-crm-backend
python -m uvicorn src.api:app --port 8000 --reload

# Terminal 2 — WhatsApp Web bridge
cd banking-crm-backend/whatsapp-service
node server.js
# Already authenticated → shows "🟢 WhatsApp client ready"

# Terminal 3 — Frontend
cd agentic-bank-insight
npm run dev
# Opens http://localhost:8080

# Terminal 4 — Twilio webhook tunnel
cloudflared tunnel --url http://localhost:8000 --no-autoupdate
# Copy URL → paste in Twilio Console
```

---

## 1. Agent Intelligence (3 min)

**Open:** http://localhost:8080 → Workspace tab

**Type this query:**
> "Find premium customers in Mumbai who don't have a personal loan and draft personalised messages"

**Walk through the execution trace:**
- Planner breaks it into: Query → Score → Draft
- Executor chains 3 tools **per customer** (scoring + transaction + message)
- Total: ~13 tool calls
- Results show real loan amounts (₹19.1L at 10.5% p.a., EMI ₹25,900/month)
- Conversion probability badges: 63% (warm tone) vs 2% (urgent tone)
- Personalization signal: "13-year loyal customer | Excellent credit (793)"

**Key talking point:** Every number in the message is computed, not hallucinated.
Rate is derived from credit score band. EMI uses the standard annuity formula.
The LLM only chooses tone — the maths is Python.

---

## 2. Send Modal — Two Backends (2 min)

**Click "Send to customers"**

**WhatsApp Web tab (default):**
- Shows connection status: "WhatsApp connected — messages from your account"
- Free, uses own number, no API
- Sandbox mode ON → all go to +917838146286

**Switch to Twilio tab:**
- Shows: "Twilio connected · Sandbox +14155238886"
- Template SID visible
- Message bubble shows 3 quick-reply buttons rendered:
  `[✅ Yes, Interested!]  [📞 Call Me]  [❌ Not Now]`

**Explain sandbox toggle:**
- Sandbox ON: all messages → test number (safe for demos)
- Sandbox OFF: messages → each customer's actual CRM phone (production)

**Click Send (Twilio tab)**
- Message arrives on your phone with the 3 buttons

---

## 3. AI Sales Agent — Live Button Tap (2 min)

**On your phone:** tap **✅ Yes, Interested!**

**Watch the Conversations tab (http://localhost:8080/conversations):**
- Conversation appears within 8 seconds (auto-poll)
- Left panel: Aaina Karpe | INTERESTED (green badge)
- Center: her reply + AI's reply below it
- Right panel: pipeline stage tracker — INTERESTED is highlighted
- Hot lead alert: "🔥 Hot lead — schedule callback!"

**What happened under the hood:**
1. Twilio received button tap → POSTed to your Cloudflare tunnel
2. FastAPI `/api/outreach/twilio-webhook` parsed `ButtonText: "yes"`
3. Mapped "yes" → "yes interested"
4. `_classify_intent()` → `YES`
5. Pipeline updated: → `INTERESTED`
6. `generate_sales_reply()` → template reply (fast path, no LLM needed)
7. TwiML returned → Twilio sent reply to your WhatsApp

**Try ❌ Not Now:** AI replies gracefully, stage → DECLINED.

---

## 4. Pipeline Dashboard (1 min)

**Conversations tab → Full Funnel section (right panel):**

```
CONTACTED         ████████████ 21
ENGAGED           ████████████████ 27
INTERESTED        █ 1
CALLBACK_REQUESTED ██ 2
DECLINED          █ 1
CONVERTED         ████ 10
```

Every customer reply tracked. Every AI reply saved to DB.

---

## Key Design Decisions to Mention

**Why LangGraph?**
Explicit nodes → observable execution trace, easy to debug, testable nodes in isolation. ReAct loops are a black box.

**Why WhatsApp Web as primary?**
Zero cost, no API approval process, uses existing business number. Twilio is for production where you need delivery receipts, templates, and compliance.

**Why intent classifier without LLM?**
Keyword matching handles 90% of replies in <1ms with no API quota. LLM fallback only fires for genuinely ambiguous multi-turn conversations.

**Why real EMI formula?**
Banks cannot send messages with hallucinated interest rates. Every number is computed from the customer's actual credit score and income. The LLM sees the numbers — it doesn't create them.

**Why Cloudflare tunnel?**
Free, no signup, instant public URL. ngrok requires account auth. Survives across sessions via the same URL (tunnel can be made permanent with a Cloudflare account for production).

---

## Impressive Queries to Try Live

```
"Find customers with credit score above 750 and no credit card — draft messages"
"Show dormant premium customers and create a re-engagement campaign"
"Score the top 5 affluent customers in Bangalore"
"Which customers had a salary spike last month?"
```

---

## If Something Breaks

| Issue | Fix |
|---|---|
| WhatsApp shows "DISCONNECTED" | `cd whatsapp-service && node server.js` |
| Port 3001 already in use | `lsof -ti:3001 \| xargs kill -9` |
| Twilio webhook not firing | Re-paste tunnel URL in Twilio Console (URL changes on restart) |
| AI reply is generic | Check sandbox_sessions — run a send-batch first to register context |
| Backend 500 on twilio-webhook | Restart uvicorn — picks up latest code |
