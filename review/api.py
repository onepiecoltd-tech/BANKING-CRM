"""
FastAPI backend — exposes the Python RM-agent as a REST API so the React UI can consume it.
"""
import os
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

# ── absolute DB path so the server can be run from any cwd ──────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_BASE}/banking_crm.db")

from src.database import (
    SessionLocal, Customer, Transaction, Interaction, Product, IdentityGraph, init_db,
    CadenceJob, Suppression, AuditLog
)
from src.tools.customer_tool import query_customers as _query_customers, get_customer_profile
from src.tools.scoring_tool import score_customer_value, predict_conversion_probability
from src.tools.product_tool import recommend_products
from src.tools.transaction_tool import get_transaction_summary
from src.tools.message_tool import draft_outreach_message, _rate_for_credit_score, _emi, _fmt_inr
from src.tools.outreach_tool import send_outreach_message as _send_outreach
from src.tools.sales_agent import generate_sales_reply, _classify_intent
from src.rm_agent.graph import build_rm_agent_graph, create_initial_state
from src.config import settings

app = FastAPI(title="Banking CRM Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build LangGraph once at startup
_agent_graph = None

# Semaphore: only 1 agent run touches the LLM at a time → no parallel quota burn
_llm_semaphore = asyncio.Semaphore(1)

# Sandbox session map: phone_number → {customer_id, product_id, message}
# When sandbox mode is on, all messages go to the RM's own number.
# Sandbox session routing: maps sandbox phone → list of pending customers (FIFO queue).
# Each entry: {"customer_id": ..., "product_id": ..., "message": ...}
# When a reply arrives we pick the first customer who hasn't had a TWILIO_INBOUND interaction yet.
_sandbox_sessions: dict = {}   # "+917838146286" → [{"customer_id":..., "product_id":..., "message":...}, ...]

@app.on_event("startup")
def startup():
    global _agent_graph
    init_db()
    _agent_graph = build_rm_agent_graph()


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Customers ────────────────────────────────────────────────────────────────

@app.get("/api/customers")
def list_customers(
    segment: Optional[str] = None,
    city: Optional[str] = None,
    min_income: Optional[float] = None,
    max_income: Optional[float] = None,
    min_credit_score: Optional[int] = None,
    min_balance: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = Query(60, le=200),
    offset: int = 0,
):
    session = SessionLocal()
    try:
        q = session.query(Customer)
        if segment:
            q = q.filter(Customer.segment == segment.lower())
        if city:
            q = q.filter(Customer.city.ilike(f"%{city}%"))
        if min_income is not None:
            q = q.filter(Customer.annual_income >= min_income)
        if max_income is not None:
            q = q.filter(Customer.annual_income <= max_income)
        if min_credit_score is not None:
            q = q.filter(Customer.credit_score >= min_credit_score)
        if min_balance is not None:
            q = q.filter(Customer.monthly_avg_balance >= min_balance)
        if search:
            q = q.filter(
                Customer.name.ilike(f"%{search}%") |
                Customer.city.ilike(f"%{search}%") |
                Customer.occupation.ilike(f"%{search}%")
            )
        total = q.count()
        customers = q.offset(offset).limit(limit).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_customer_to_dict(c) for c in customers],
        }
    finally:
        session.close()


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    profile = get_customer_profile(customer_id)
    if not profile:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return profile


@app.get("/api/customers/{customer_id}/transactions")
def customer_transactions(customer_id: str, days: int = 90, limit: int = 30):
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        txns = (
            session.query(Transaction)
            .filter(Transaction.customer_id == customer_id, Transaction.date >= cutoff)
            .order_by(Transaction.date.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "txn_id": t.txn_id,
                "date": t.date.isoformat(),
                "amount": t.amount,
                "category": t.category,
                "channel": t.channel,
                "merchant": t.merchant,
            }
            for t in txns
        ]
    finally:
        session.close()


@app.get("/api/customers/{customer_id}/score")
def customer_score(customer_id: str):
    result = score_customer_value(customer_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/customers/{customer_id}/recommendations")
def customer_recommendations(customer_id: str):
    result = recommend_products(customer_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/analytics/kpis")
def analytics_kpis():
    session = SessionLocal()
    try:
        total = session.query(func.count(Customer.customer_id)).scalar()
        high_value = session.query(func.count(Customer.customer_id)).filter(
            Customer.segment == "premium"
        ).scalar()
        affluent = session.query(func.count(Customer.customer_id)).filter(
            Customer.segment == "affluent"
        ).scalar()
        # Hot leads: high balance + good credit
        hot_leads = session.query(func.count(Customer.customer_id)).filter(
            Customer.credit_score >= 720,
            Customer.monthly_avg_balance >= 200000,
        ).scalar()
        # Pipeline value: sum of annual incomes for premium+affluent as proxy
        pipeline = session.query(func.sum(Customer.annual_income)).filter(
            Customer.segment.in_(["premium", "affluent"])
        ).scalar() or 0
        return {
            "totalCustomers": total,
            "highValue": high_value + affluent,
            "hotLeads": hot_leads,
            "pipelineValue": round(pipeline / 12, 0),  # monthly equivalent
        }
    finally:
        session.close()


@app.get("/api/analytics/charts")
def analytics_charts():
    session = SessionLocal()
    try:
        # Segment breakdown
        seg_counts = (
            session.query(Customer.segment, func.count(Customer.customer_id))
            .group_by(Customer.segment)
            .all()
        )
        segment_breakdown = [{"name": s.title(), "value": c} for s, c in seg_counts]

        # Conversion trend: interactions by month for last 12 months
        now = datetime.utcnow()
        trend = []
        for i in range(11, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=30 * i))
            month_end = (now.replace(day=1) - timedelta(days=30 * (i - 1))) if i > 0 else now
            month_label = month_start.strftime("%b")
            sent = session.query(func.count(Interaction.interaction_id)).filter(
                Interaction.date >= month_start, Interaction.date < month_end
            ).scalar()
            converted = session.query(func.count(Interaction.interaction_id)).filter(
                Interaction.date >= month_start,
                Interaction.date < month_end,
                Interaction.converted == True,
            ).scalar()
            responded = session.query(func.count(Interaction.interaction_id)).filter(
                Interaction.date >= month_start,
                Interaction.date < month_end,
                Interaction.response.isnot(None),
            ).scalar()
            trend.append({
                "month": month_label,
                "sent": sent,
                "responded": responded,
                "converted": converted,
            })

        # Pipeline stages from interactions
        stage_counts = (
            session.query(Interaction.pipeline_state, func.count(Interaction.interaction_id))
            .group_by(Interaction.pipeline_state)
            .all()
        )
        pipeline_stages = [{"stage": s, "count": c} for s, c in stage_counts]

        # Response rate by channel
        channel_stats = (
            session.query(Interaction.channel, func.count(Interaction.interaction_id))
            .group_by(Interaction.channel)
            .all()
        )
        response_rate = [{"channel": ch, "interactions": cnt} for ch, cnt in channel_stats]

        return {
            "segmentBreakdown": segment_breakdown,
            "conversionTrend": trend,
            "pipelineStages": pipeline_stages,
            "responseRateData": response_rate,
        }
    finally:
        session.close()


@app.get("/api/analytics/campaigns")
def analytics_campaigns():
    session = SessionLocal()
    try:
        interactions = (
            session.query(Interaction)
            .order_by(Interaction.date.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "interaction_id": i.interaction_id,
                "customer_id": i.customer_id,
                "channel": i.channel,
                "product_offered": i.product_offered,
                "converted": i.converted,
                "pipeline_state": i.pipeline_state,
                "framework_used": i.framework_used,
                "date": i.date.isoformat(),
            }
            for i in interactions
        ]
    finally:
        session.close()


# ── Outreach ─────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    customer_name: str
    product_id: str
    framework: str = "AIDA"
    tone: str = "professional"


@app.post("/api/outreach/draft")
def outreach_draft(body: DraftRequest):
    result = draft_outreach_message(
        customer_name=body.customer_name,
        product_id=body.product_id,
        framework=body.framework,
        tone=body.tone,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/outreach/phone/{customer_id}")
def get_customer_phone(customer_id: str):
    """Look up a customer's mobile number from the IdentityGraph."""
    session = SessionLocal()
    try:
        record = (
            session.query(IdentityGraph)
            .filter(
                IdentityGraph.canonical_id == customer_id,
                IdentityGraph.identifier_type == "mobile",
            )
            .first()
        )
        if not record:
            return {"customer_id": customer_id, "phone": None}
        phone = record.identifier_value
        # Normalize to E.164 — add +91 if exactly 10 digits (Indian mobile)
        if phone and not phone.startswith("+"):
            digits = "".join(c for c in phone if c.isdigit())
            if len(digits) == 10 and digits[0] in "6789":
                # Indian mobile: 6xxx–9xxx
                phone = f"+91{digits}"
            else:
                # Landline / unknown format — can't auto-normalize
                phone = None
        return {"customer_id": customer_id, "phone": phone}
    finally:
        session.close()


class SendBatchItem(BaseModel):
    customer_id: str
    customer_name: str
    product_id: str
    message: str
    phone_number: str          # E.164, e.g. +919876543210
    framework: str = "AIDA"


class SendBatchRequest(BaseModel):
    drafts: list[SendBatchItem]
    sandbox: bool = True                          # True = redirect all to sandbox_number
    sandbox_number: str = ""                      # override; falls back to config default
    sender_backend: str | None = None             # override SENDER_BACKEND for this batch


@app.post("/api/outreach/send-batch")
def send_batch(body: SendBatchRequest):
    """
    Send a batch of outreach messages (WhatsApp/Twilio/mock).

    Sandbox mode: all messages redirect to a single test number.
    Production mode: messages go to each customer's actual CRM number.
    Backend can be overridden per-request: whatsapp-web | twilio | mock
    """
    effective_sandbox_number = (
        body.sandbox_number.strip()
        or settings.whatsapp_sandbox_number
    )

    # Temporarily override sender backend for this batch if requested
    original_backend = settings.sender_backend
    if body.sender_backend:
        settings.sender_backend = body.sender_backend

    results = []
    try:
        for item in body.drafts:
            phone = effective_sandbox_number if body.sandbox else item.phone_number

            result = _send_outreach(
                customer_id=item.customer_id,
                phone_number=phone,
                message=item.message,
                product_id=item.product_id,
                framework_used=item.framework,
            )

            # Register sandbox session for AI reply routing (queue — one slot per customer)
            if body.sandbox:
                queue = _sandbox_sessions.setdefault(effective_sandbox_number, [])
                # Avoid duplicates if re-sending to same customer
                if not any(s["customer_id"] == item.customer_id for s in queue):
                    queue.append({
                        "customer_id": item.customer_id,
                        "product_id":  item.product_id,
                        "message":     item.message,
                    })

            results.append({
                "customer_id":    item.customer_id,
                "customer_name":  item.customer_name,
                "intended_phone": item.phone_number,
                "sent_to":        phone,
                "sandbox":        body.sandbox,
                **result,
            })
    finally:
        settings.sender_backend = original_backend  # restore

    return {
        "sent":           len(results),
        "sandbox":        body.sandbox,
        "sandbox_number": effective_sandbox_number if body.sandbox else None,
        "backend":        results[0].get("backend", "mock") if results else "mock",
        "results":        results,
    }


@app.get("/api/outreach/campaigns")
def outreach_campaigns():
    session = SessionLocal()
    try:
        rows = (
            session.query(Interaction)
            .filter(Interaction.channel.isnot(None))
            .order_by(Interaction.date.desc())
            .limit(50)
            .all()
        )
        # Group into "campaigns" by product+framework
        campaigns: dict = {}
        for r in rows:
            key = f"{r.product_offered}-{r.framework_used}"
            if key not in campaigns:
                campaigns[key] = {
                    "id": key,
                    "product": r.product_offered,
                    "framework": r.framework_used,
                    "channel": r.channel,
                    "sent": 0,
                    "converted": 0,
                    "started": r.date.isoformat(),
                }
            campaigns[key]["sent"] += 1
            if r.converted:
                campaigns[key]["converted"] += 1
        result = list(campaigns.values())
        for c in result:
            c["conversion_rate"] = round(c["converted"] / c["sent"] * 100, 1) if c["sent"] else 0
        return result
    finally:
        session.close()


# ── Agent ────────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    query: str
    llm_backend: str = "ollama"         # default backend for all nodes
    planner_backend: str | None = None  # override for planner node only
    executor_backend: str | None = None # override for executor node only
    ollama_model: str | None = None     # specific ollama model (e.g. llama3.1:8b)
    nvidia_model: str | None = None     # specific nvidia nim model


def _build_provider(backend: str, ollama_model: str | None = None, nvidia_model: str | None = None):
    if backend == "gemini":
        from src.llm.gemini import GeminiProvider
        return GeminiProvider()
    if backend == "nvidia":
        from src.llm.nvidia import NvidiaProvider
        return NvidiaProvider(model=nvidia_model) if nvidia_model else NvidiaProvider()
    from src.llm.ollama import OllamaProvider
    return OllamaProvider(model=ollama_model) if ollama_model else OllamaProvider()


@app.post("/api/agent/run")
async def run_agent(body: AgentRequest):
    # Only 1 LLM request fires at a time — queues extra requests instead of
    # slamming them all into the per-minute quota window simultaneously.
    async with _llm_semaphore:
        provider = _build_provider(body.llm_backend, body.ollama_model, body.nvidia_model)

        initial_state = create_initial_state(
            body.query,
            llm_backend=body.llm_backend,
            llm_provider=provider,
            planner_backend=body.planner_backend,
            executor_backend=body.executor_backend,
            ollama_model=body.ollama_model,
            nvidia_model=body.nvidia_model,
        )
        try:
            final_state = await asyncio.get_event_loop().run_in_executor(
                None, _agent_graph.invoke, initial_state
            )
        except Exception as e:
            raise HTTPException(500, f"Agent error: {e}")

    tool_steps = []
    for call in final_state.get("tool_call_log", []):
        tool_steps.append({
            "id": call.get("timestamp", ""),
            "type": "tool",
            "label": call.get("tool_name", ""),
            "detail": f"Tool: {call.get('tool_name')}",
            "toolCall": {
                "name": call.get("tool_name"),
                "input": call.get("arguments", {}),
                "output": call.get("result"),
                "durationMs": 400,
                "status": "success",
            },
            "startedAt": 1,
            "endedAt": 2,
        })

    plan_steps = [
        {
            "id": f"plan-{i}",
            "type": "plan",
            "label": step,
            "detail": step,
            "startedAt": 1,
            "endedAt": 2,
        }
        for i, step in enumerate(final_state.get("task_plan", []))
    ]

    all_steps = plan_steps + tool_steps + [
        {
            "id": "respond",
            "type": "respond",
            "label": "Synthesize response",
            "detail": "LLM summarizes execution results",
            "startedAt": 1,
            "endedAt": 2,
        }
    ]

    customer_set = final_state.get("customer_set", [])
    return {
        "answer": final_state.get("final_answer", ""),
        "steps": all_steps,
        "customers": customer_set,           # full list — frontend shows all
        "total_customers_found": len(customer_set),
        "drafts": final_state.get("drafts", []),
        "tool_call_count": len(final_state.get("tool_call_log", [])),
        "task_plan": final_state.get("task_plan", []),
        "error": final_state.get("error"),
    }


# ── Agent streaming (SSE) ─────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse

@app.post("/api/agent/stream")
async def stream_agent(body: AgentRequest):
    """
    Server-Sent Events endpoint — emits one JSON event per LangGraph node
    so the frontend can show real-time progress:
      {"event":"node","node":"planner","status":"running"}
      {"event":"node","node":"planner","status":"done","detail":"Plan: Query → Score → Draft"}
      {"event":"tool","name":"query_customers","status":"done","count":50}
      {"event":"done","answer":"...","customers":[...],"drafts":[...]}
    """
    import json as _json

    async def _generate():
        async with _llm_semaphore:
            provider = _build_provider(body.llm_backend, body.ollama_model, body.nvidia_model)
            state = create_initial_state(
                body.query,
                llm_backend=body.llm_backend,
                llm_provider=provider,
                planner_backend=body.planner_backend,
                executor_backend=body.executor_backend,
                ollama_model=body.ollama_model,
                nvidia_model=body.nvidia_model,
            )

            nodes = ["planner", "executor", "reflector", "responder"]
            node_labels = {
                "planner":   "📋 Planning task",
                "executor":  "⚙️  Executing tools",
                "reflector": "🔍 Checking results",
                "responder": "✍️  Synthesizing answer",
            }

            from src.rm_agent.nodes import (
                planner_node, executor_node, reflector_node, responder_node
            )
            node_fns = {
                "planner":   planner_node,
                "executor":  executor_node,
                "reflector": reflector_node,
                "responder": responder_node,
            }

            loop = asyncio.get_event_loop()
            current = "planner"
            max_iters = 12  # safety cap on executor loops

            for _iter in range(max_iters):
                if current not in node_fns:
                    break

                label = node_labels.get(current, current)

                # ── running event ──────────────────────────────────────────
                yield f"data: {_json.dumps({'event':'node','node':current,'status':'running','label':label})}\n\n"
                await asyncio.sleep(0)

                # ── run the node in executor thread ────────────────────────
                try:
                    state = await loop.run_in_executor(None, node_fns[current], state)
                except Exception as exc:
                    yield f"data: {_json.dumps({'event':'error','node':current,'detail':str(exc)})}\n\n"
                    break

                # ── emit tool calls made during this node ──────────────────
                emitted = set()
                for call in state.get("tool_call_log", []):
                    ts = call.get("timestamp", "")
                    if ts not in emitted:
                        emitted.add(ts)
                        result = call.get("result", {})
                        count  = len(result) if isinstance(result, list) else None
                        yield f"data: {_json.dumps({'event':'tool','name':call.get('tool_name',''),'status':'done','count':count,'ts':ts})}\n\n"
                        await asyncio.sleep(0)

                # ── done event for this node ───────────────────────────────
                detail = ""
                if current == "planner":
                    plan = state.get("task_plan", [])
                    detail = " → ".join(plan) if plan else "Plan ready"
                elif current == "executor":
                    n_cust = len(state.get("customer_set", []))
                    n_draft = len(state.get("drafts", []))
                    detail = f"{n_cust} customers found, {n_draft} drafts"
                elif current == "responder":
                    detail = (state.get("final_answer", "") or "")[:80]

                yield f"data: {_json.dumps({'event':'node','node':current,'status':'done','label':label,'detail':detail})}\n\n"
                await asyncio.sleep(0)

                # ── routing ────────────────────────────────────────────────
                if current == "planner":
                    current = "executor"
                elif current == "executor":
                    current = "reflector"
                elif current == "reflector":
                    step = state.get("step", 0)
                    if step == 3 or step == 99:
                        current = "responder"
                    else:
                        current = "executor"
                elif current == "responder":
                    break

            # ── final done event ───────────────────────────────────────────
            customer_set = state.get("customer_set", [])
            payload = {
                "event":                "done",
                "answer":               state.get("final_answer", ""),
                "customers":            customer_set,
                "total_customers_found": len(customer_set),
                "drafts":               state.get("drafts", []),
                "task_plan":            state.get("task_plan", []),
                "tool_call_count":      len(state.get("tool_call_log", [])),
                "error":                state.get("error"),
            }
            yield f"data: {_json.dumps(payload)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Settings ─────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return {
        "llm_backend": settings.llm_backend,
        "ollama_model": settings.ollama_model,
        "crm_backend": settings.crm_backend,
        "sender_backend": settings.sender_backend,
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_hubspot_key": bool(settings.hubspot_developer_key),
        "has_twilio": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "whatsapp_service_url": settings.whatsapp_service_url,
        "whatsapp_sandbox": settings.whatsapp_sandbox,
        "whatsapp_sandbox_number": settings.whatsapp_sandbox_number,
    }


class IncomingReplyRequest(BaseModel):
    phone: str      # E.164 e.g. +917838146286
    message: str    # What the customer said


@app.post("/api/outreach/reply")
def incoming_reply(body: IncomingReplyRequest):
    """
    Called by the WhatsApp Web JS service when a customer replies.
    1. Match phone → customer via IdentityGraph
    2. Find their most recent outreach interaction
    3. Update interaction with their response + pipeline state
    4. Run AI sales agent to generate a reply
    5. Return { ai_reply: "..." } — the Node service sends it on WhatsApp
    """
    session = SessionLocal()
    try:
        # 1. Look up customer — check sandbox session queue first
        #    (in sandbox mode the reply comes from the RM's own number, not the customer's)
        sandbox_queue = _sandbox_sessions.get(body.phone)
        sandbox_ctx = None
        if sandbox_queue:
            # Pick first customer in queue who hasn't replied yet
            for entry in sandbox_queue:
                already = session.query(Interaction).filter(
                    Interaction.customer_id == entry["customer_id"],
                    Interaction.framework_used == "TWILIO_INBOUND",
                ).first()
                if not already:
                    sandbox_ctx = entry
                    break
            if not sandbox_ctx:
                sandbox_ctx = sandbox_queue[-1]

        if sandbox_ctx:
            # Sandbox reply — use stored customer context
            customer_id = sandbox_ctx["customer_id"]
            customer    = session.query(Customer).filter_by(customer_id=customer_id).first()
        else:
            # Production reply — look up by phone in IdentityGraph
            phone_digits = body.phone.replace("+", "").replace(" ", "")
            identity = (
                session.query(IdentityGraph)
                .filter(
                    IdentityGraph.identifier_type == "mobile",
                    IdentityGraph.identifier_value.contains(phone_digits[-10:]),
                )
                .first()
            )
            customer_id = identity.canonical_id if identity else None
            customer    = session.query(Customer).filter_by(customer_id=customer_id).first() if customer_id else None

        # 2. Find latest outreach interaction for this customer
        last_interaction = None
        if customer_id:
            last_interaction = (
                session.query(Interaction)
                .filter(
                    Interaction.customer_id == customer_id,
                    Interaction.channel == "whatsapp",
                    Interaction.framework_used != "AI_AGENT",   # skip AI replies
                )
                .order_by(Interaction.date.desc())
                .first()
            )

        # 3. Update interaction with reply + new pipeline state
        intent = _classify_intent(body.message)
        pipeline_map = {
            "YES": "INTERESTED", "NO": "DECLINED", "PRICE_OBJECTION": "OBJECTION",
            "DOCUMENTS": "ENGAGED", "TIMELINE": "ENGAGED", "WANTS_CALLBACK": "CALLBACK_REQUESTED",
            "THINKING": "CONSIDERING", "HAS_PRODUCT": "OBJECTION", "GENERAL": "ENGAGED",
        }
        new_state = pipeline_map.get(intent, "ENGAGED")

        if last_interaction:
            last_interaction.response     = body.message
            last_interaction.pipeline_state = new_state
            if intent == "YES":
                last_interaction.converted = True
            session.commit()

        # 4. Generate AI sales reply
        ai_reply = None
        if customer and last_interaction:
            product = session.query(Product).filter_by(
                product_id=last_interaction.product_offered
            ).first()

            if product:
                income      = customer.annual_income or 0
                loan_amount = min(income * 0.5, 2_500_000)
                rate        = _rate_for_credit_score(customer.credit_score)
                emi_val     = _emi(loan_amount, rate, 60)

                ai_reply = generate_sales_reply(
                    customer=customer,
                    product=product,
                    outreach_message=last_interaction.message or "",
                    customer_reply=body.message,
                    conversation_history=[
                        {"role": "assistant", "content": last_interaction.message or ""},
                        {"role": "user",      "content": body.message},
                    ],
                    loan_amount_str=_fmt_inr(loan_amount),
                    rate=rate,
                    emi_str=_fmt_inr(emi_val),
                )

                # Log AI reply as a new interaction
                if ai_reply:
                    import uuid
                    ai_interaction = Interaction(
                        interaction_id=f"INT_AI_{uuid.uuid4().hex[:12]}",
                        customer_id=customer_id,
                        date=datetime.utcnow(),
                        channel="whatsapp",
                        product_offered=last_interaction.product_offered,
                        message=ai_reply,
                        pipeline_state=new_state,
                        framework_used="AI_AGENT",
                    )
                    session.add(ai_interaction)
                    session.commit()
        elif not customer:
            # Unknown number — generic reply
            ai_reply = "Thanks for your message! This number is for BankRM customer outreach. Please contact your branch for assistance."

        return {
            "customer_id":   customer_id,
            "customer_name": customer.name if customer else None,
            "intent":        intent,
            "pipeline_state": new_state,
            "ai_reply":      ai_reply,
        }
    finally:
        session.close()


@app.post("/api/outreach/twilio-webhook")
async def twilio_webhook(request: Request):
    """
    Twilio WhatsApp inbound webhook.
    Twilio POSTs here (form-encoded) whenever a customer:
      - Taps a quick-reply button (Body = button text, ButtonText = button id)
      - Sends a free-form WhatsApp message
    We extract phone + text, run the same AI sales agent logic, then reply
    with TwiML so Twilio sends the AI message back to the customer.
    """
    form = await request.form()

    # Log all incoming fields for debugging
    import logging as _log
    _log.warning(f"[WEBHOOK] form fields: { {k: v for k,v in form.items()} }")

    raw_phone = str(form.get("From", "")).replace("whatsapp:", "").strip()
    body_text  = str(form.get("Body", "")).strip()
    button_id  = str(form.get("ButtonText", "") or form.get("ButtonPayload", "")).strip()

    # Prefer button id for intent classification (cleaner signal)
    message_text = button_id if button_id else body_text
    if not message_text:
        _log.warning(f"[WEBHOOK] Empty message_text — phone={raw_phone} body={body_text!r} button={button_id!r}")
        # Last resort: treat any inbound as a greeting so we still reply
        message_text = "hello"

    # Map button labels to intent-friendly text
    BUTTON_MAP = {
        "yes": "yes interested",
        "callback": "call me callback",
        "no": "not interested",
    }
    message_text = BUTTON_MAP.get(message_text.lower(), message_text)

    # Reuse the existing reply logic
    class _Req:
        phone = raw_phone
        message = message_text

    # Call the core reply logic directly
    session = SessionLocal()
    try:
        from src.tools.sales_agent import generate_sales_reply as _gen_reply
        from src.database import Product

        # _sandbox_sessions is now a list (queue). Pick the first customer who hasn't
        # received a TWILIO_INBOUND interaction yet (i.e. hasn't replied before).
        sandbox_queue = _sandbox_sessions.get(raw_phone)
        sandbox_ctx = None
        if sandbox_queue:
            for entry in sandbox_queue:
                already_replied = session.query(Interaction).filter(
                    Interaction.customer_id == entry["customer_id"],
                    Interaction.framework_used == "TWILIO_INBOUND",
                ).first()
                if not already_replied:
                    sandbox_ctx = entry
                    break
            # If all customers have replied, fall back to the last one in queue
            if not sandbox_ctx:
                sandbox_ctx = sandbox_queue[-1]

        if sandbox_ctx:
            customer_id = sandbox_ctx["customer_id"]
            product_id  = sandbox_ctx["product_id"]
            outreach_msg = sandbox_ctx["message"]
            customer = session.query(Customer).filter_by(customer_id=customer_id).first()
            _log.warning(f"[WEBHOOK] Session queue match → {customer_id}")
        else:
            # In-memory session map was lost (restart / new process).
            # Strategy 1: check if this phone matches a real customer in IdentityGraph
            ig = (session.query(IdentityGraph)
                  .filter_by(identifier_type="mobile", identifier_value=raw_phone)
                  .first())
            if ig:
                customer = session.query(Customer).filter_by(customer_id=ig.canonical_id).first()
                last_int = (
                    session.query(Interaction)
                    .filter_by(customer_id=customer.customer_id, channel="whatsapp")
                    .order_by(Interaction.date.desc()).first()
                ) if customer else None
                product_id   = last_int.product_offered if last_int else None
                outreach_msg = last_int.message if last_int else ""
                customer_id  = customer.customer_id if customer else None
            else:
                # Strategy 2 (sandbox fallback): raw_phone is the RM/sandbox number.
                # In sandbox, all outreach goes to the RM's own phone via Twilio test number.
                # Priority: pick the most recently contacted customer who has NOT yet replied
                # (no INTERESTED/DECLINED/ENGAGED etc. follow-on interaction logged).
                # This avoids picking a customer who was already processed in a previous test.
                from sqlalchemy import not_, exists
                replied_subq = (
                    session.query(Interaction.customer_id)
                    .filter(
                        Interaction.channel == "whatsapp",
                        Interaction.pipeline_state.notin_(["CONTACTED"]),
                        Interaction.framework_used.in_(["TWILIO_INBOUND", "AI_AGENT"]),
                    )
                    .subquery()
                )
                last_outreach = (
                    session.query(Interaction)
                    .filter(
                        Interaction.channel == "whatsapp",
                        Interaction.pipeline_state == "CONTACTED",
                        Interaction.message != None,
                        Interaction.message != "",
                        Interaction.message != "Outreach message about product",
                        ~Interaction.customer_id.in_(replied_subq),
                    )
                    .order_by(Interaction.date.desc())
                    .first()
                )
                # If everyone has replied already, just fall back to absolute most recent
                if not last_outreach:
                    last_outreach = (
                        session.query(Interaction)
                        .filter(
                            Interaction.channel == "whatsapp",
                            Interaction.pipeline_state == "CONTACTED",
                            Interaction.message != None,
                            Interaction.message != "",
                            Interaction.message != "Outreach message about product",
                        )
                        .order_by(Interaction.date.desc())
                        .first()
                    )
                if last_outreach:
                    customer_id  = last_outreach.customer_id
                    product_id   = last_outreach.product_offered
                    outreach_msg = last_outreach.message or ""
                    customer = session.query(Customer).filter_by(customer_id=customer_id).first()
                    _log.warning(f"[WEBHOOK] Sandbox fallback → customer={customer_id} ({customer.name if customer else '?'})")
                    # Rebuild in-memory session so subsequent replies are fast
                    _sandbox_sessions[raw_phone] = {
                        "customer_id": customer_id,
                        "product_id":  product_id,
                        "message":     outreach_msg,
                    }
                else:
                    customer = None
                    customer_id = product_id = None
                    outreach_msg = ""

        if customer and product_id:
            from src.tools.sales_agent import _classify_intent
            intent    = _classify_intent(message_text)
            new_state = {
                "YES": "INTERESTED", "WANTS_CALLBACK": "CALLBACK_REQUESTED",
                "PRICE_OBJECTION": "OBJECTION", "HAS_PRODUCT": "OBJECTION",
                "NO": "DECLINED", "THINKING": "CONSIDERING",
            }.get(intent, "ENGAGED")

            # Save customer response
            import uuid as _uuid
            session.add(Interaction(
                interaction_id=f"INT_TW_{_uuid.uuid4().hex[:10]}",
                customer_id=customer_id,
                date=datetime.utcnow(),
                channel="whatsapp",
                product_offered=product_id,
                response=body_text,
                pipeline_state=new_state,
                framework_used="TWILIO_INBOUND",
            ))
            session.commit()

            # Auto-route: if customer requested callback, schedule a follow-up job
            if intent == "WANTS_CALLBACK":
                followup_job = CadenceJob(
                    job_id=str(_uuid.uuid4()),
                    canonical_id=customer_id,
                    product_id=product_id or "PL001",
                    next_run_at=datetime.utcnow() + timedelta(hours=2),  # callback reminder in 2h
                    step=1,
                    status="pending",
                )
                session.add(followup_job)
                session.commit()

            product = session.query(Product).filter_by(product_id=product_id).first()
            if product:
                from src.tools.message_tool import _rate_for_credit_score, _emi, _fmt_inr
                rate = _rate_for_credit_score(customer.credit_score or 650)
                loan = min(max(customer.annual_income or 500000, 200000), 2500000)
                emi_val = _emi(loan, rate, 60)
                ai_reply = _gen_reply(
                    customer=customer, product=product,
                    outreach_message=outreach_msg,
                    customer_reply=message_text,
                    conversation_history=[],
                    loan_amount_str=_fmt_inr(loan),
                    rate=rate, emi_str=_fmt_inr(emi_val),
                )
            else:
                ai_reply = f"Thanks for your response! Our team will follow up shortly. 😊"

            # Save AI reply
            session.add(Interaction(
                interaction_id=f"INT_TW_AI_{_uuid.uuid4().hex[:10]}",
                customer_id=customer_id,
                date=datetime.utcnow(),
                channel="whatsapp",
                product_offered=product_id,
                message=ai_reply,
                pipeline_state=new_state,
                framework_used="AI_AGENT",
            ))
            session.commit()
        else:
            ai_reply = "Thanks for reaching out! Our team will get back to you shortly. 😊"
    finally:
        session.close()

    # ── Send reply via Twilio outbound API (more reliable than TwiML for WhatsApp) ──
    # TwiML <Message> responses are unreliable for WhatsApp template button replies
    # in sandbox mode. Using the Messages API directly guarantees delivery.
    try:
        from twilio.rest import Client as _TwilioClient
        _tw = _TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        _from = settings.twilio_phone_number
        _wa_from = f"whatsapp:{_from}" if not _from.startswith("whatsapp:") else _from
        _wa_to   = f"whatsapp:{raw_phone}" if not raw_phone.startswith("whatsapp:") else raw_phone
        _log.warning(f"[WEBHOOK] Sending Twilio reply to {_wa_to} from {_wa_from}: {ai_reply[:80]!r}")
        _sent = _tw.messages.create(from_=_wa_from, to=_wa_to, body=ai_reply)
        _log.warning(f"[WEBHOOK] Twilio send OK — SID={_sent.sid} status={_sent.status}")
    except Exception as _e:
        # Log but don't crash — still return empty TwiML so Twilio doesn't retry
        _log.warning(f"[WEBHOOK] Twilio reply send FAILED: {_e}")

    # Return empty TwiML (reply already sent via outbound API above)
    return Response(content='<?xml version="1.0"?><Response></Response>',
                    media_type="application/xml")


@app.get("/api/outreach/pipeline")
def outreach_pipeline():
    """
    Pipeline summary — how many customers are at each stage.
    Used by the dashboard to show the sales funnel.
    """
    session = SessionLocal()
    try:
        from sqlalchemy import func

        # ── Funnel: latest pipeline_state per customer ───────────────────────
        subq_latest = (
            session.query(
                Interaction.customer_id,
                func.max(Interaction.date).label("latest")
            )
            .filter(Interaction.channel == "whatsapp")
            .group_by(Interaction.customer_id)
            .subquery()
        )
        latest_interactions = (
            session.query(Interaction)
            .join(subq_latest, (Interaction.customer_id == subq_latest.c.customer_id) &
                               (Interaction.date == subq_latest.c.latest))
            .all()
        )

        # Stage counts for funnel
        stages: dict[str, int] = {}
        for i in latest_interactions:
            state = i.pipeline_state or "CONTACTED"
            stages[state] = stages.get(state, 0) + 1

        # ── Recent replies: latest customer-reply interaction per customer ───
        # A customer reply has response set and framework_used != AI_AGENT
        subq_reply = (
            session.query(
                Interaction.customer_id,
                func.max(Interaction.date).label("latest")
            )
            .filter(
                Interaction.channel == "whatsapp",
                Interaction.response != None,
                Interaction.response != "",
            )
            .group_by(Interaction.customer_id)
            .subquery()
        )
        reply_interactions = (
            session.query(Interaction)
            .join(subq_reply, (Interaction.customer_id == subq_reply.c.customer_id) &
                              (Interaction.date == subq_reply.c.latest))
            .order_by(Interaction.date.desc())
            .limit(20)
            .all()
        )

        recent_replies = []
        for i in reply_interactions:
            c = session.query(Customer).filter_by(customer_id=i.customer_id).first()

            # Find the original outreach message (first CONTACTED interaction)
            original_outreach = (
                session.query(Interaction)
                .filter(
                    Interaction.customer_id == i.customer_id,
                    Interaction.pipeline_state == "CONTACTED",
                    Interaction.message != None,
                    Interaction.message != "",
                    Interaction.message != "Outreach message about product",
                )
                .order_by(Interaction.date.asc())
                .first()
            )
            # Fallback: any interaction with a non-placeholder message
            if not original_outreach:
                original_outreach = (
                    session.query(Interaction)
                    .filter(
                        Interaction.customer_id == i.customer_id,
                        Interaction.message != None,
                        Interaction.message != "",
                        Interaction.message != "Outreach message about product",
                    )
                    .order_by(Interaction.date.asc())
                    .first()
                )

            # Find most recent AI reply after the customer response
            ai_int = (
                session.query(Interaction)
                .filter(
                    Interaction.customer_id == i.customer_id,
                    Interaction.framework_used == "AI_AGENT",
                    Interaction.date >= i.date,
                )
                .order_by(Interaction.date.asc())
                .first()
            )

            # Get full conversation history for this customer (all interactions in order)
            all_interactions = (
                session.query(Interaction)
                .filter(Interaction.customer_id == i.customer_id)
                .order_by(Interaction.date.asc())
                .all()
            )
            conversation_thread = []
            seen_rm_contents: set[str] = set()   # dedup identical outreach blasts
            for intr in all_interactions:
                # The RM outreach message — skip identical duplicates
                if intr.message and intr.message.strip() and intr.message != "Outreach message about product":
                    content_key = intr.message.strip()
                    if content_key not in seen_rm_contents:
                        seen_rm_contents.add(content_key)
                        conversation_thread.append({
                            "role": "rm",
                            "content": intr.message,
                            "date": intr.date.isoformat() if intr.date else None,
                            "type": "outreach" if intr.framework_used != "AI_AGENT" else "ai_response",
                        })
                # The customer's reply
                if intr.response and intr.response.strip():
                    # After a customer reply, allow RM to re-send (clear dedup set)
                    seen_rm_contents.clear()
                    conversation_thread.append({
                        "role": "customer",
                        "content": intr.response,
                        "date": intr.date.isoformat() if intr.date else None,
                        "type": "reply",
                    })

            # Use the latest state from funnel (not the reply row's state)
            state = next(
                (x.pipeline_state for x in latest_interactions if x.customer_id == i.customer_id),
                i.pipeline_state or "CONTACTED"
            ) or "CONTACTED"

            recent_replies.append({
                "customer_id":       i.customer_id,
                "customer_name":     c.name if c else i.customer_id,
                "response":          i.response,
                "pipeline_state":    state,
                "product":           i.product_offered,
                "date":              i.date.isoformat(),
                "converted":         i.converted,
                "ai_reply":          ai_int.message if ai_int else None,
                "outreach_message":  original_outreach.message if original_outreach else None,
                "conversation_thread": conversation_thread,
                "product_offered":   i.product_offered or (original_outreach.product_offered if original_outreach else None),
            })

        # ── Funnel list ──────────────────────────────────────────────────────
        funnel_order = ["CONTACTED", "ENGAGED", "CONSIDERING", "CALLBACK_REQUESTED",
                        "INTERESTED", "OBJECTION", "DECLINED", "CONVERTED"]
        funnel = [{"stage": s, "count": stages.get(s, 0)} for s in funnel_order]
        for s, cnt in stages.items():
            if s not in funnel_order:
                funnel.append({"stage": s, "count": cnt})

        return {
            "funnel":           funnel,
            "total_contacted":  sum(stages.values()),
            "total_replied":    len(reply_interactions),
            "total_converted":  sum(1 for i in latest_interactions if i.converted),
            "recent_replies":   recent_replies[:20],
        }
    finally:
        session.close()


# ── Campaign Builder ──────────────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    product_id: str                          # e.g. "PL001", "CC001"
    segment: Optional[str] = None            # mass, affluent, premium, or None for all
    city: Optional[str] = None
    min_conversion_probability: float = 0.20 # 0.0-1.0
    tone: str = "warm"                       # warm, professional, urgent
    max_leads: int = 20
    sender_backend: str = "whatsapp"         # whatsapp, twilio

class CampaignResponse(BaseModel):
    campaign_id: str
    total_leads: int
    leads: list
    estimated_conversions: int
    product_name: str
    filters_applied: dict

@app.post("/api/campaigns/preview")
def preview_campaign(req: CampaignRequest):
    """
    Campaign Builder — score and rank leads for a given product + segment + city.
    Returns ranked leads with conversion probability, life events, and draft messages.
    Does NOT send anything — preview only.
    """
    import uuid
    from src.tools.scoring_tool import predict_conversion_probability, detect_life_events, get_behavioral_signals
    from src.tools.message_tool import draft_outreach_message

    session = SessionLocal()
    try:
        product = session.query(Product).filter_by(product_id=req.product_id).first()
        if not product:
            raise HTTPException(404, f"Product {req.product_id} not found")

        # Build customer query with filters
        q = session.query(Customer)
        if req.segment:
            q = q.filter(Customer.segment == req.segment)
        if req.city:
            q = q.filter(Customer.city.ilike(f"%{req.city}%"))

        # Eligible segments for this product
        if product.eligible_segments:
            q = q.filter(Customer.segment.in_(product.eligible_segments))

        # KYC must be verified
        q = q.filter(Customer.kyc_status == "verified")

        # Fetch up to 200 candidates and score them
        candidates = q.limit(200).all()

        scored_leads = []
        for c in candidates:
            score_result = predict_conversion_probability(c.customer_id, req.product_id)
            prob = score_result.get("probability", 0)

            if prob < req.min_conversion_probability:
                continue

            # Get behavioral signals for timing
            signals = get_behavioral_signals(c.customer_id)
            life_events = signals.get("life_events", [])
            timing_score = signals.get("timing_score", 50)

            # Draft message — correct arg order: (customer_name, product_id, framework, tone, customer_id=...)
            try:
                draft = draft_outreach_message(c.name, req.product_id, "AIDA", req.tone, customer_id=c.customer_id)
                raw_msg = draft.get("primary_message", "") or draft.get("short_variant", "")
                message_preview = raw_msg[:200] + "..." if len(raw_msg) > 200 else raw_msg
            except Exception:
                message_preview = ""

            scored_leads.append({
                "customer_id": c.customer_id,
                "name": c.name,
                "city": c.city,
                "segment": c.segment,
                "credit_score": c.credit_score,
                "annual_income": c.annual_income,
                "conversion_probability": round(prob * 100, 1),
                "top_signals": score_result.get("top_signals", []),
                "life_events": [e["event"] for e in life_events],
                "life_event_details": life_events[:2],
                "timing_score": timing_score,
                "timing_label": signals.get("timing_label", "good"),
                "tone_hint": signals.get("message_tone_hint", req.tone),
                "message_preview": message_preview,
                "phone": None,  # Never expose in list
            })

        # Sort by conversion probability (desc), then timing score
        scored_leads.sort(key=lambda x: (x["conversion_probability"], x["timing_score"]), reverse=True)
        scored_leads = scored_leads[:req.max_leads]

        return {
            "campaign_id": str(uuid.uuid4())[:8].upper(),
            "total_leads": len(scored_leads),
            "leads": scored_leads,
            "estimated_conversions": max(1, round(sum(l["conversion_probability"] for l in scored_leads) / 100)),
            "product_name": product.name,
            "filters_applied": {
                "product": req.product_id,
                "segment": req.segment or "all",
                "city": req.city or "all",
                "min_probability": req.min_conversion_probability,
                "tone": req.tone,
            },
        }
    finally:
        session.close()


# ── Campaign: AI Message Compose (single customer) ────────────────────────────

class ComposeRequest(BaseModel):
    customer_id: str
    product_id: str
    tone: str = "warm"

@app.post("/api/campaigns/compose")
def compose_message(req: ComposeRequest):
    """
    Generate (or regenerate) an AI outreach message for a single customer.
    Called by Campaign Builder when the RM clicks ✨ Regenerate on a lead card.
    """
    from src.tools.message_tool import draft_outreach_message

    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=req.customer_id).first()
        if not customer:
            raise HTTPException(404, f"Customer {req.customer_id} not found")

        draft = draft_outreach_message(
            customer.name, req.product_id, "AIDA", req.tone,
            customer_id=req.customer_id,
        )
        message = draft.get("primary_message", "") or draft.get("short_variant", "")
        return {"message": message, "customer_id": req.customer_id}
    finally:
        session.close()


# ── Opt-Out / DND Management ──────────────────────────────────────────────────

class OptOutRequest(BaseModel):
    customer_id: str
    reason: str = "customer_requested"  # customer_requested, stop_reply, dnd, compliance
    channel: str = "whatsapp"
    days: Optional[int] = None          # None = permanent, int = suppressed for N days

@app.post("/api/optout")
def register_optout(req: OptOutRequest):
    """Register a customer opt-out / suppression."""
    import uuid
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=req.customer_id).first()
        if not customer:
            raise HTTPException(404, f"Customer {req.customer_id} not found")

        expires_at = None
        if req.days:
            expires_at = datetime.utcnow() + timedelta(days=req.days)

        suppression = Suppression(
            id=str(uuid.uuid4()),
            canonical_id=req.customer_id,
            reason=req.reason,
            expires_at=expires_at,
            source=f"api_{req.channel}",
        )
        session.add(suppression)
        session.commit()

        return {
            "status": "suppressed",
            "customer_id": req.customer_id,
            "reason": req.reason,
            "expires_at": expires_at.isoformat() if expires_at else "permanent",
            "message": f"Customer {customer.name} added to suppression list.",
        }
    finally:
        session.close()

@app.delete("/api/optout/{customer_id}")
def remove_optout(customer_id: str):
    """Remove suppression for a customer (they opted back in)."""
    session = SessionLocal()
    try:
        deleted = session.query(Suppression).filter_by(canonical_id=customer_id).delete()
        session.commit()
        return {"status": "removed", "customer_id": customer_id, "records_removed": deleted}
    finally:
        session.close()


# ── Follow-Up Cadence Engine ──────────────────────────────────────────────────

@app.get("/api/followups/due")
def get_due_followups():
    """
    Get all follow-up jobs that are due to run.

    The cadence:
      Step 0 = initial outreach (Day 0)
      Step 1 = value-add follow-up (Day 3)
      Step 2 = social proof (Day 7)
      Step 3 = last attempt (Day 14)
      Step 4 = suppress 30 days, re-enter on trigger
    """
    session = SessionLocal()
    try:
        due_jobs = session.query(CadenceJob).filter(
            CadenceJob.status == "pending",
            CadenceJob.next_run_at <= datetime.utcnow(),
        ).limit(50).all()

        result = []
        for job in due_jobs:
            customer = session.query(Customer).filter_by(customer_id=job.canonical_id).first()
            result.append({
                "job_id": job.job_id,
                "customer_id": job.canonical_id,
                "customer_name": customer.name if customer else "Unknown",
                "product_id": job.product_id,
                "step": job.step,
                "step_label": ["Initial", "Follow-up (Day 3)", "Social Proof (Day 7)", "Last Attempt (Day 14)"][min(job.step, 3)],
                "due_at": job.next_run_at.isoformat(),
                "overdue_hours": max(0, round((datetime.utcnow() - job.next_run_at).total_seconds() / 3600, 1)),
            })

        return {
            "due_count": len(result),
            "jobs": result,
        }
    finally:
        session.close()


class ScheduleFollowUpRequest(BaseModel):
    customer_id: str
    product_id: str
    step: int = 1  # Which step to schedule (1=day3, 2=day7, 3=day14)

@app.post("/api/followups/schedule")
def schedule_followup(req: ScheduleFollowUpRequest):
    """Schedule the next follow-up step for a customer."""
    import uuid

    step_delays = {1: 3, 2: 7, 3: 14}
    delay_days = step_delays.get(req.step, 3)

    session = SessionLocal()
    try:
        job = CadenceJob(
            job_id=str(uuid.uuid4()),
            canonical_id=req.customer_id,
            product_id=req.product_id,
            next_run_at=datetime.utcnow() + timedelta(days=delay_days),
            step=req.step,
            status="pending",
        )
        session.add(job)
        session.commit()

        step_labels = {1: "Day 3 follow-up", 2: "Day 7 social proof", 3: "Day 14 last attempt"}
        return {
            "status": "scheduled",
            "job_id": job.job_id,
            "step": req.step,
            "step_label": step_labels.get(req.step, "Follow-up"),
            "scheduled_for": job.next_run_at.isoformat(),
        }
    finally:
        session.close()


# ── Morning Digest ────────────────────────────────────────────────────────────

@app.get("/api/digest/morning")
def morning_digest():
    """
    Morning digest for the RM — what needs attention today.
    Returns: hot leads, due follow-ups, callbacks requested, overnight replies.
    """
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        since_yesterday = now - timedelta(hours=16)  # overnight window

        # Overnight replies (customer replied while RM was offline)
        overnight_replies = session.query(Interaction).filter(
            Interaction.date >= since_yesterday,
            Interaction.response != None,
            Interaction.response != "",
        ).order_by(Interaction.date.desc()).limit(10).all()

        # Callback requested
        callback_leads = session.query(Interaction).filter(
            Interaction.pipeline_state == "CALLBACK_REQUESTED",
            Interaction.date >= now - timedelta(days=7),
        ).limit(10).all()

        # Due follow-ups today
        due_jobs = session.query(CadenceJob).filter(
            CadenceJob.status == "pending",
            CadenceJob.next_run_at <= now + timedelta(hours=24),
        ).limit(10).all()

        # Hot leads (INTERESTED or multiple engagements)
        hot_leads = session.query(Interaction).filter(
            Interaction.pipeline_state.in_(["INTERESTED", "ENGAGED"]),
            Interaction.date >= now - timedelta(days=3),
        ).limit(5).all()

        def interaction_summary(i: Interaction):
            c = session.query(Customer).filter_by(customer_id=i.customer_id).first()
            return {
                "customer_id": i.customer_id,
                "name": c.name if c else "Unknown",
                "city": c.city if c else None,
                "pipeline_state": i.pipeline_state,
                "last_message": (i.response or "")[:100],
                "date": i.date.isoformat() if i.date else None,
            }

        return {
            "generated_at": now.isoformat(),
            "summary": {
                "overnight_replies": len(overnight_replies),
                "callbacks_due": len(callback_leads),
                "followups_due_today": len(due_jobs),
                "hot_leads": len(hot_leads),
            },
            "overnight_replies": [interaction_summary(i) for i in overnight_replies],
            "callbacks_requested": [interaction_summary(i) for i in callback_leads],
            "followups_due": [
                {
                    "job_id": j.job_id,
                    "customer_id": j.canonical_id,
                    "product_id": j.product_id,
                    "step": j.step,
                    "due_at": j.next_run_at.isoformat(),
                }
                for j in due_jobs
            ],
            "hot_leads": [interaction_summary(i) for i in hot_leads],
        }
    finally:
        session.close()


# ── Analytics: Churn & Cross-sell ────────────────────────────────────────────

@app.get("/api/analytics/churn-signals")
def get_churn_signals(limit: int = Query(20, le=50)):
    """Get customers with highest churn risk scores."""
    from src.tools.scoring_tool import detect_churn_signals
    session = SessionLocal()
    try:
        # Sample recent active customers for churn scoring
        customers = session.query(Customer).filter(
            Customer.kyc_status == "verified"
        ).limit(100).all()

        results = []
        for c in customers:
            try:
                churn = detect_churn_signals(c.customer_id)
                if churn.get("churn_risk") in ("medium", "high"):
                    results.append({
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "segment": c.segment,
                        "city": c.city,
                        "churn_risk": churn["churn_risk"],
                        "risk_score": churn["risk_score"],
                        "signals": [s["signal"] for s in churn.get("signals", [])],
                        "recommendation": churn.get("recommendation", ""),
                        "annual_income": c.annual_income,
                        "monthly_avg_balance": c.monthly_avg_balance,
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return {
            "at_risk_count": len(results),
            "high_risk": sum(1 for r in results if r["churn_risk"] == "high"),
            "medium_risk": sum(1 for r in results if r["churn_risk"] == "medium"),
            "customers": results[:limit],
        }
    finally:
        session.close()


@app.get("/api/analytics/cross-sell")
def get_cross_sell_opportunities(limit: int = Query(20, le=50)):
    """Get top cross-sell opportunities across portfolio."""
    from src.tools.scoring_tool import detect_cross_sell_opportunities
    session = SessionLocal()
    try:
        customers = session.query(Customer).filter(
            Customer.kyc_status == "verified"
        ).limit(80).all()

        all_opps = []
        for c in customers:
            try:
                opps = detect_cross_sell_opportunities(c.customer_id)
                for opp in opps[:1]:  # top opp per customer
                    all_opps.append({
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "segment": c.segment,
                        "product_name": opp["product_name"],
                        "product_id": opp["product_id"],
                        "reason": opp["reason"],
                        "confidence": round(opp["confidence"] * 100, 1),
                        "urgency": opp["urgency"],
                    })
            except Exception:
                continue

        all_opps.sort(key=lambda x: x["confidence"], reverse=True)

        # Group by product
        by_product: dict = {}
        for o in all_opps:
            p = o["product_name"]
            by_product[p] = by_product.get(p, 0) + 1

        return {
            "total_opportunities": len(all_opps),
            "by_product": by_product,
            "top_opportunities": all_opps[:limit],
        }
    finally:
        session.close()


@app.get("/api/analytics/reply-rates")
def get_reply_rates():
    """Reply rates broken down by segment, pipeline stage, and day of week."""
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        interactions = session.query(Interaction).filter(
            Interaction.date >= thirty_days_ago,
        ).all()

        # By segment
        segment_stats: dict = {}
        for i in interactions:
            c = session.query(Customer).filter_by(customer_id=i.customer_id).first()
            if not c:
                continue
            seg = c.segment or "unknown"
            if seg not in segment_stats:
                segment_stats[seg] = {"sent": 0, "replied": 0}
            segment_stats[seg]["sent"] += 1
            if i.response and i.response.strip():
                segment_stats[seg]["replied"] += 1

        segment_reply_rates = [
            {
                "segment": seg,
                "sent": stats["sent"],
                "replied": stats["replied"],
                "reply_rate": round(stats["replied"] / stats["sent"] * 100, 1) if stats["sent"] > 0 else 0,
            }
            for seg, stats in segment_stats.items()
        ]

        # By day of week
        dow_stats: dict = {}
        for i in interactions:
            if i.date:
                dow = i.date.strftime("%a")  # Mon, Tue, etc.
                if dow not in dow_stats:
                    dow_stats[dow] = {"sent": 0, "replied": 0}
                dow_stats[dow]["sent"] += 1
                if i.response and i.response.strip():
                    dow_stats[dow]["replied"] += 1

        day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        dow_reply_rates = [
            {
                "day": dow,
                "reply_rate": round(dow_stats.get(dow, {}).get("replied", 0) / max(dow_stats.get(dow, {}).get("sent", 1), 1) * 100, 1),
                "sent": dow_stats.get(dow, {}).get("sent", 0),
            }
            for dow in day_order
        ]

        # Overall stats
        total_sent = len(interactions)
        total_replied = sum(1 for i in interactions if i.response and i.response.strip())
        total_converted = sum(1 for i in interactions if i.converted)

        return {
            "period": "last_30_days",
            "overall": {
                "sent": total_sent,
                "replied": total_replied,
                "converted": total_converted,
                "reply_rate": round(total_replied / total_sent * 100, 1) if total_sent > 0 else 0,
                "conversion_rate": round(total_converted / total_replied * 100, 1) if total_replied > 0 else 0,
            },
            "by_segment": segment_reply_rates,
            "by_day_of_week": dow_reply_rates,
        }
    finally:
        session.close()


@app.get("/api/customers/{customer_id}/intelligence")
def get_customer_intelligence(customer_id: str):
    """Full customer intelligence: life events + churn signals + cross-sell opportunities + behavioral signals."""
    from src.tools.scoring_tool import detect_life_events, get_behavioral_signals, detect_churn_signals, detect_cross_sell_opportunities

    try:
        life_events = detect_life_events(customer_id)
        behavioral = get_behavioral_signals(customer_id)
        churn = detect_churn_signals(customer_id)
        cross_sell = detect_cross_sell_opportunities(customer_id)

        return {
            "customer_id": customer_id,
            "life_events": life_events,
            "behavioral_signals": behavioral,
            "churn": churn,
            "cross_sell_opportunities": cross_sell,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Audit Log ─────────────────────────────────────────────────────────────────

@app.get("/api/audit-log")
def get_audit_log(limit: int = Query(50, le=200), customer_id: Optional[str] = None):
    """Retrieve audit log entries."""
    session = SessionLocal()
    try:
        q = session.query(AuditLog).order_by(AuditLog.timestamp.desc())
        if customer_id:
            q = q.filter(AuditLog.customer_id == customer_id)
        entries = q.limit(limit).all()
        return {
            "entries": [
                {
                    "log_id": e.log_id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "action": e.action,
                    "actor": e.actor,
                    "customer_id": e.customer_id,
                    "product_id": e.product_id,
                    "channel": e.channel,
                    "details": e.details,
                    "outcome": e.outcome,
                }
                for e in entries
            ]
        }
    finally:
        session.close()


@app.get("/api/outreach/whatsapp-status")
def whatsapp_status():
    """
    Proxy to the WhatsApp Web JS service to get connection status + QR code.
    The frontend polls this every few seconds while setting up the session.
    """
    import urllib.request, urllib.error, json as _json
    base = settings.whatsapp_service_url.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/qr", timeout=3) as resp:
            return _json.loads(resp.read())
    except Exception as exc:
        return {"ready": False, "state": "SERVICE_DOWN", "error": str(exc)}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _customer_to_dict(c: Customer) -> dict:
    products_held = sum([c.has_credit_card, c.has_personal_loan, c.has_home_loan, c.has_fd])
    # Simple CLV score inline (avoid per-row DB queries)
    income_norm = min((c.annual_income or 0) / 5_000_000, 1.0)
    balance_norm = min((c.monthly_avg_balance or 0) / 1_000_000, 1.0)
    credit_norm = ((c.credit_score or 550) - 550) / 350
    score = round((income_norm * 0.3 + balance_norm * 0.3 + credit_norm * 0.4) * 100, 1)
    return {
        "customer_id": c.customer_id,
        "name": c.name,
        "age": c.age,
        "gender": c.gender,
        "city": c.city,
        "segment": c.segment,
        "occupation": c.occupation,
        "annual_income": c.annual_income,
        "monthly_avg_balance": c.monthly_avg_balance,
        "credit_score": c.credit_score,
        "relationship_years": c.relationship_years,
        "kyc_status": c.kyc_status,
        "has_credit_card": c.has_credit_card,
        "has_personal_loan": c.has_personal_loan,
        "has_home_loan": c.has_home_loan,
        "has_fd": c.has_fd,
        "clv_score": score,
        "products_held": products_held,
        "last_contact_date": c.last_contact_date.isoformat() if c.last_contact_date else None,
    }
