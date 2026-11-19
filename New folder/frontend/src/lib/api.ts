/**
 * Typed API client — all calls go through the Vite proxy (/api → http://localhost:8000).
 * Each function throws on non-2xx so React Query can handle errors.
 */

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface ApiCustomer {
  customer_id: string;
  name: string;
  age: number;
  gender: string | null;
  city: string | null;
  segment: string; // mass | affluent | premium
  occupation: string | null;
  annual_income: number;
  monthly_avg_balance: number;
  credit_score: number | null;
  relationship_years: number;
  kyc_status: string;
  has_credit_card: boolean;
  has_personal_loan: boolean;
  has_home_loan: boolean;
  has_fd: boolean;
  clv_score: number;
  products_held: number;
  last_contact_date: string | null;
}

export interface CustomerListResponse {
  total: number;
  limit: number;
  offset: number;
  items: ApiCustomer[];
}

export interface Transaction {
  txn_id: string;
  date: string;
  amount: number;
  category: string | null;
  channel: string | null;
  merchant: string | null;
}

export interface ScoreResult {
  customer_id: string;
  score: number;
  tier: string;
  factors: Record<string, number | boolean>;
  weights: Record<string, number>;
}

export interface Recommendation {
  product_id: string;
  product_name: string;
  product_type: string;
  interest_rate: number | null;
  affinity_score: number;
  reasons: string[];
}

export interface RecommendationsResult {
  customer_id: string;
  total_recommendations: number;
  recommendations: Recommendation[];
}

export interface KPIs {
  totalCustomers: number;
  highValue: number;
  hotLeads: number;
  pipelineValue: number;
}

export interface ChartData {
  segmentBreakdown: { name: string; value: number }[];
  conversionTrend: { month: string; sent: number; responded: number; converted: number }[];
  pipelineStages: { stage: string; count: number }[];
  responseRateData: { channel: string; interactions: number }[];
}

export interface AgentStep {
  id: string;
  type: "plan" | "tool" | "reflect" | "respond";
  label: string;
  detail: string;
  toolCall?: {
    name: string;
    input: Record<string, unknown>;
    output: unknown;
    durationMs: number;
    status: string;
  };
  startedAt: number;
  endedAt: number;
}

export interface AgentResult {
  answer: string;
  steps: AgentStep[];
  customers: ApiCustomer[];
  drafts: {
    customer_id: string;
    customer_name: string;
    product_id: string;
    message: string;
    short_variant?: string;
    personalization_note?: string;
    offer_expiry?: string;
    framework: string;
    tone: string;
    conversion_probability?: number | null;
  }[];
  tool_call_count: number;
  task_plan: string[];
  error: string | null;
}

export interface Campaign {
  id: string;
  product: string | null;
  framework: string | null;
  channel: string | null;
  sent: number;
  converted: number;
  conversion_rate: number;
  started: string;
}

export interface ApiSettings {
  llm_backend: string;
  ollama_model: string;
  crm_backend: string;
  sender_backend: string;
  has_gemini_key: boolean;
  has_hubspot_key: boolean;
  has_twilio: boolean;
  whatsapp_service_url: string;
  whatsapp_sandbox: boolean;
  whatsapp_sandbox_number: string;
}

export interface WhatsAppStatus {
  ready: boolean;
  state: string;   // "INITIALIZING" | "QR_READY" | "AUTHENTICATED" | "READY" | "SERVICE_DOWN"
  qr?: string | null;
  error?: string;
}

// ── Customer endpoints ────────────────────────────────────────────────────────

export const customers = {
  list: (params: {
    segment?: string;
    city?: string;
    min_income?: number;
    max_income?: number;
    min_credit_score?: number;
    min_balance?: number;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    return get<CustomerListResponse>(`/api/customers?${qs}`);
  },

  get: (id: string) => get<ApiCustomer>(`/api/customers/${id}`),

  transactions: (id: string, days = 90) =>
    get<Transaction[]>(`/api/customers/${id}/transactions?days=${days}`),

  score: (id: string) => get<ScoreResult>(`/api/customers/${id}/score`),

  recommendations: (id: string) =>
    get<RecommendationsResult>(`/api/customers/${id}/recommendations`),
};

// ── Analytics endpoints ───────────────────────────────────────────────────────

export const analytics = {
  kpis: () => get<KPIs>("/api/analytics/kpis"),
  charts: () => get<ChartData>("/api/analytics/charts"),
  campaigns: () => get<Campaign[]>("/api/analytics/campaigns"),
};

// ── Agent endpoint ────────────────────────────────────────────────────────────

export interface ModelConfig {
  llm_backend: string;
  planner_backend?: string;
  executor_backend?: string;
  ollama_model?: string;
  nvidia_model?: string;
}

export const agent = {
  run: (query: string, config: ModelConfig | string = "ollama") => {
    const body = typeof config === "string"
      ? { query, llm_backend: config }
      : { query, ...config };
    return post<AgentResult>("/api/agent/run", body);
  },
};

// ── Outreach endpoints ────────────────────────────────────────────────────────

export interface SendBatchItem {
  customer_id: string;
  customer_name: string;
  product_id: string;
  message: string;
  phone_number: string;
  framework?: string;
}

export interface SendBatchResult {
  customer_id: string;
  customer_name: string;
  intended_phone: string;   // customer's actual CRM number
  sent_to: string;          // number actually messaged (sandbox may differ)
  sandbox: boolean;
  status: string;
  backend: string;
  sid?: string;
  messageId?: string;
  preview?: string;
  error?: string;
  interaction_id?: string;
}

export interface SendBatchResponse {
  sent: number;
  sandbox: boolean;
  sandbox_number: string | null;
  backend: string;
  results: SendBatchResult[];
}

export const outreach = {
  draft: (body: { customer_name: string; product_id: string; framework?: string; tone?: string }) =>
    post("/api/outreach/draft", body),

  campaigns: () => get<Campaign[]>("/api/outreach/campaigns"),

  phone: (customer_id: string) =>
    get<{ customer_id: string; phone: string | null }>(`/api/outreach/phone/${customer_id}`),

  sendBatch: (drafts: SendBatchItem[], sandbox: boolean, sandboxNumber: string, senderBackend?: string) =>
    post<SendBatchResponse>("/api/outreach/send-batch", {
      drafts,
      sandbox,
      sandbox_number: sandboxNumber,
      ...(senderBackend ? { sender_backend: senderBackend } : {}),
    }),

  whatsappStatus: () =>
    get<WhatsAppStatus>("/api/outreach/whatsapp-status"),
};

// ── Settings endpoint ─────────────────────────────────────────────────────────

export const apiSettings = {
  get: () => get<ApiSettings>("/api/settings"),
};

// ── Pipeline / Inbox endpoints ────────────────────────────────────────────────

export interface PipelineFunnelStage {
  stage: string;
  count: number;
}

export interface ConversationTurn {
  role: "rm" | "customer";
  content: string;
  date: string | null;
  type: "outreach" | "reply" | "ai_response";
}

export interface PipelineReply {
  customer_id: string;
  customer_name: string;
  response: string;
  pipeline_state: string;
  product: string | null;
  product_offered: string | null;
  date: string;
  converted: boolean;
  ai_reply?: string | null;
  outreach_message?: string | null;
  conversation_thread?: ConversationTurn[];
  intent?: string | null;
}

export interface PipelineData {
  funnel: PipelineFunnelStage[];
  total_contacted: number;
  total_replied: number;
  total_converted: number;
  recent_replies: PipelineReply[];
}

export const pipeline = {
  get: () => get<PipelineData>("/api/outreach/pipeline"),
};

// ── Health ────────────────────────────────────────────────────────────────────

export const health = () => get<{ status: string }>("/api/health");
