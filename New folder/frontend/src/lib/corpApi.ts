/** API client for the corporate (Doanh nghiệp) edition — /api/corp/* (proxied by Vite to :8000). */

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/corp${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}
const post = <T,>(path: string, body: unknown) =>
  j<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const patch = <T,>(path: string, body: unknown) =>
  j<T>(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export interface RiskFlag { code: string; severity: "high" | "medium" | "low"; text: string }
export interface TopOpp { product: string; name: string; score: number; reasons: string[]; expected_amount_bn: number }
export interface Nba { product: string | null; name: string; why: string }

export interface CorpSummary {
  customer_id: string; name: string; name_zh: string | null; segment: string; ownership: string;
  investor_country: string | null; industry: string; province: string; industrial_zone: string | null;
  employees: number; annual_revenue_bn: number; loan_outstanding_bn: number; casa_balance_bn: number;
  debt_group: number; tier: "A" | "B" | "C"; priority_score: number; products_held: string[];
  preferred_language: "vi" | "zh" | "en"; contact_name: string | null; rm_name: string | null;
  risk_flags: RiskFlag[]; top_opportunities: TopOpp[]; next_best_action: Nba | null; headline: string | null;
  import_usd_m: number; export_usd_m: number; product_score?: number;
}

export interface CorpMeta {
  products: { code: string; vi: string; en: string; zh: string }[];
  stages: string[]; segments: string[]; industries: string[]; provinces: string[]; countries: string[];
  languages: Record<string, string>; bank_name: string; rm_names?: string[];
  lifecycles?: { code: string; name: string }[]; rm_options?: { username: string; full_name: string; role: string; rm_name: string; is_active: boolean }[];
}

export interface CorpKpis {
  total: number; fdi: number; loans_bn: number; casa_bn: number; deposit_bn: number; trade_usd_m: number;
  tier: Record<string, number>; segments: Record<string, number>; countries: Record<string, number>;
  industries: Record<string, number>; provinces: Record<string, number>;
  crosssell: { code: string; name: string; count: number }[]; flags: Record<string, number>;
  pipeline_count: number; pipeline_value_bn: number; pipeline_weighted_bn: number;
}

export interface SignalRow { customer_id: string; name: string; tier: string; severity: string; text: string; rm_name: string }
export type Signals = Record<"limit_expiry" | "inflow_drop" | "debt" | "high_util" | "casa_drop", { count: number; items: SignalRow[] }>;

export interface Monthly { month: string; inflow_bn: number; outflow_bn: number; trade_usd_m: number; avg_balance_bn: number }
export interface Propensity { score: number; held: boolean; reasons: string[] }
export interface Opportunity {
  id: number; customer_id: string; customer_name: string | null; product: string; product_name: string; stage: string;
  expected_amount_bn: number; probability: number; next_action: string | null; due_date: string | null;
}
export interface CorpDetail {
  customer: Record<string, any>;
  monthly: Monthly[];
  analysis: {
    tier: string; priority_score: number; wallet_share_pct: number; risk_flags: RiskFlag[];
    top_opportunities: TopOpp[]; next_best_action: Nba | null; propensities: Record<string, Propensity>;
    metrics: { avg_monthly_inflow_bn: number; inflow_trend_3m_pct: number; utilization: number | null; days_to_expiry: number | null; trade_usd_m: number };
  };
  interactions: { date: string; channel: string; summary: string; outcome: string | null }[];
  opportunities: Opportunity[];
}
export interface Draft {
  customer_id: string; product: string; product_name: string; channel: string; language: string;
  subject: string | null; body: string; chars: number; customer_name?: string;
}
export interface AgentResult {
  query: string; filters: Record<string, any>; steps: { step: string; detail: string }[]; total_matched: number;
  customers: CorpSummary[]; drafts: Draft[]; answer: string; llm_used: boolean; llm_error: string | null;
}

export const corp = {
  meta: () => j<CorpMeta>("/meta"),
  kpis: () => j<CorpKpis>("/kpis"),
  signals: () => j<Signals>("/signals"),
  customers: (p: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "") qs.set(k, String(v)); });
    return j<{ total: number; items: CorpSummary[] }>(`/customers?${qs}`);
  },
  customer: (id: string) => j<CorpDetail>(`/customers/${id}`),
  draft: (id: string, body: { product: string; channel: string; language?: string; rm_name?: string }) =>
    post<Draft>(`/customers/${id}/draft`, body),
  addInteraction: (id: string, body: { channel: string; summary: string; outcome?: string }) =>
    post<{ ok: boolean }>(`/customers/${id}/interactions`, body),
  opportunities: () => j<{ stages: string[]; by_stage: Record<string, Opportunity[]>; totals: Record<string, number> }>("/opportunities"),
  createOpp: (body: { customer_id: string; product: string }) => post<Opportunity>("/opportunities", body),
  patchOpp: (id: number, body: { stage?: string; next_action?: string }) => patch<Opportunity>(`/opportunities/${id}`, body),
  agent: (body: { query: string; use_llm: boolean; rm_name?: string }) => post<AgentResult>("/agent", body),
};

export { j as _get, post as _post, patch as _patch };
