/** API client — phần mở rộng của bản Doanh nghiệp: nhập liệu, tiếp cận, chiến dịch, hội thoại, lập luận, phân tích, cài đặt, import, người dùng. */
import { _get as j, _post as post, _patch as patch } from "./corpApi";
import type { CorpSummary } from "./corpApi";

const put = <T,>(path: string, body: unknown) =>
  j<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const del = <T,>(path: string) => j<T>(path, { method: "DELETE" });
const qs = (p: Record<string, string | number | boolean | undefined | null>) => {
  const u = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") u.set(k, String(v)); });
  const s = u.toString();
  return s ? `?${s}` : "";
};
// các endpoint ngoài /api/corp
async function raw<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}
const jsonInit = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// ── nhập liệu khách hàng ────────────────────────────────────────────────────
export interface CustomerForm {
  name: string; name_zh?: string | null; tax_code?: string | null; ownership: string; investor_country?: string | null; industry: string; province: string;
  industrial_zone?: string | null; employees: number; annual_revenue_bn: number; total_assets_bn: number; equity_bn: number; export_usd_m: number; import_usd_m: number;
  fx_exposure_usd_m: number; casa_balance_bn: number; deposit_bn: number; loan_outstanding_bn: number; credit_limit_bn: number; limit_expiry?: string | null;
  debt_group: number; relationship_years: number; products_held: string[]; rm_name?: string | null; contact_name?: string | null; contact_name_zh?: string | null;
  contact_title?: string | null; contact_phone?: string | null; contact_email?: string | null; preferred_language: string;
}

// ── tiếp cận / chiến dịch ───────────────────────────────────────────────────
export interface AudienceFilters { product: string; channel: string; segment?: string; ownership?: string; country?: string; industry?: string; province?: string; tier?: string; rm?: string; min_score?: number }
export interface AudienceRow extends CorpSummary { product_score: number; reasons: string[]; expected_amount_bn: number; suppress_code?: string; suppress_reason?: string }
export interface Audience {
  eligible: AudienceRow[]; eligible_total: number; suppressed: AudienceRow[]; suppressed_total: number; suppress_counts: Record<string, number>;
  rules: { freq_cap_days: number; max_debt_group: number; quiet: string };
}
export interface DraftOut { customer_id: string; customer_name: string; product: string; product_name: string; channel: string; language: string; subject: string | null; body: string; chars: number }
export interface CampaignRow {
  id: number; name: string; product: string; product_name: string; channel: string; language: string; framework: string; status: string; owner: string; owner_rm: string;
  created_at: string; total: number; counts: Record<string, number>; contacted_pct: number; reply_pct: number; interest_pct: number; conv_pct: number;
}
export interface CampaignTarget { id: number; customer_id: string; name: string; contact_name: string | null; segment: string; industry: string; rm_name: string; status: string; language: string; subject: string | null; body: string; sent_at: string | null }

// ── hội thoại ───────────────────────────────────────────────────────────────
export interface Thread {
  customer_id: string; name: string; contact_name: string | null; segment: string; rm_name: string; language: string; status: string; status_label: string; count: number; product: string | null;
  last: { direction: "in" | "out"; body: string; created_at: string; intent: string | null; intent_label: string | null };
}
export interface Msg { id: number; direction: "in" | "out"; channel: string; language: string | null; subject: string | null; body: string; intent: string | null; intent_label: string | null; product: string | null; created_by: string | null; created_at: string; campaign_id: number | null }
export interface Suggestion { intent: string; intent_label: string; language: string; product: string | null; text: string; llm_used?: boolean; llm_error?: string | null }
export interface ConvDetail {
  customer: Record<string, any>; status: string; status_label: string; messages: Msg[]; suggestion: Suggestion | null;
  opportunities: { id: number; product: string; product_name: string; stage: string }[]; opted_out: boolean; opt_reason: string | null; product_options: { code: string; vi: string }[];
}
export interface Followup { customer_id: string; name: string; days: number; step: number; product: string | null; language: string; text: string }

// ── lập luận ────────────────────────────────────────────────────────────────
export interface Explain {
  customer: Record<string, any>;
  inputs: { label: string; value: string }[]; metrics: { label: string; value: string }[];
  rules: { code: string; name: string; threshold: string; actual: string; fired: boolean }[];
  propensities: { code: string; name: string; score: number; held: boolean; reasons: string[] }[];
  priority: { score: number; wallet_bn: number; parts: { label: string; weight: number; value: number; contribution: number; note?: string }[] };
  decision: { product: string | null; name: string; why: string } | null;
  compliance: { name: string; ok: boolean; detail: string }[];
}
export interface AgentRunRow { id: number; username: string; query: string; total_matched: number; llm_used: boolean; llm_error: string | null; created_at: string; step_count: number }
export interface AgentRunFull extends AgentRunRow { filters: Record<string, any>; steps: { step: string; detail: string }[] }

// ── phân tích ───────────────────────────────────────────────────────────────
export interface Rate { name: string; contacted: number; replied: number; rate: number }
export interface Analytics {
  kpis: { customers: number; contacted: number; replied: number; reply_rate: number; interested: number; converted: number; conv_rate: number; at_risk: number; crosssell: number; win_rate: number };
  reply_by_segment: Rate[]; reply_by_country: Rate[]; reply_by_industry: Rate[];
  reply_by_weekday: { name: string; sent: number; replied: number; rate: number }[];
  funnel: { stage: string; value: number }[]; risk: { name: string; value: number }[]; flags: { code: string; value: number }[];
  crosssell: { code: string; name: string; value: number }[];
  pipeline: { stage: string; count: number; value_bn: number }[]; activity: { month: string; interactions: number }[]; campaigns: CampaignRow[];
  rm_performance?: { rm: string; customers: number; loan_bn: number; casa_bn: number; tier_a: number; risk_high: number; pipeline_bn: number; weighted_bn: number; touches_30d: number }[];
}

// ── cài đặt / người dùng / audit ────────────────────────────────────────────
export interface CorpSettings {
  bank_name: string; freq_cap_days: number; max_debt_group_outreach: number; quiet_start: string; quiet_end: string;
  import_requires_approval: boolean; allow_cloud_ocr: boolean; llm_enabled: boolean;
}
export interface SettingsResp { settings: Partial<CorpSettings>; system: { llm_backend?: string; has_gemini_key?: boolean; sender_backend?: string; ocr_local?: boolean; database?: string; corp_customers?: number; demo_customers?: number; backup?: { file: string; bytes: number; at: string; count: number } | null; backup_auto?: boolean } }
export interface UserRow { id: number; username: string; full_name: string; role: "admin" | "staff"; rm_name: string | null; is_active: boolean; must_change_password: boolean; created_at: string | null; last_login: string | null; created_by: string | null }
export interface AuditRow { id: number; ts: string; username: string | null; role: string | null; action: string; entity: string | null; entity_id: string | null; detail: string | null; ip: string | null }

// ── import ──────────────────────────────────────────────────────────────────
export interface ImportBatch {
  id: number; filename: string; kind: string; method: string | null; target: "customers" | "monthly"; status: string; created_by: string; created_rm: string | null; created_at: string;
  reviewed_by: string | null; reviewed_at: string | null; summary: Record<string, any>; note: string | null; row_count: number; columns?: string[]; mapping?: Record<string, string>;
}
export interface ImportUpload {
  batch: ImportBatch; sheets: string[]; sheet: string | null; sample: Record<string, string>[]; warnings: string[]; fields: { key: string; label: string; required: boolean }[]; requires_approval: boolean;
}
export interface ImportPreview {
  stats: { create: number; update: number; skip: number; error: number; warn: number }; total: number;
  problems: { row: number; action: string; name: string; errors: string[]; warnings: string[] }[];
  ok_sample: { row: number; action: string; name: string; errors: string[]; warnings: string[] }[]; unmapped: string[];
}

export const corpX = {
  // khách hàng
  createCustomer: (b: CustomerForm) => post<{ customer_id: string }>("/customers", b),
  updateCustomer: (id: string, b: CustomerForm) => put<{ ok: boolean }>(`/customers/${id}`, b),
  deleteCustomer: (id: string) => del<{ ok: boolean }>(`/customers/${id}`),
  reassign: (b: { customer_ids?: string[]; from_rm?: string; to_rm: string }) => post<{ moved: number }>("/customers/reassign", b),
  // tiếp cận
  audience: (f: AudienceFilters) => post<Audience>("/outreach/audience", f),
  drafts: (b: { product: string; channel: string; language: string; framework: string; customer_ids: string[] }) => post<{ drafts: DraftOut[]; frameworks: Record<string, Record<string, string>> }>("/outreach/drafts", b),
  logSent: (items: { customer_id: string; product?: string; channel: string; language?: string; subject?: string | null; body: string }[]) =>
    post<{ logged: number; blocked: { customer_id: string; reason: string }[] }>("/outreach/log", { items, create_opportunity: true }),
  // chiến dịch
  campaigns: () => j<{ items: CampaignRow[] }>("/campaigns"),
  campaign: (id: number) => j<{ campaign: CampaignRow; targets: CampaignTarget[]; statuses: string[] }>(`/campaigns/${id}`),
  createCampaign: (b: AudienceFilters & { name: string; language: string; framework: string; customer_ids?: string[] }) => post<{ id: number; targets: number; skipped: number }>("/campaigns", b),
  setTarget: (cid: number, tid: number, status: string) => patch<{ ok: boolean }>(`/campaigns/${cid}/targets/${tid}`, { status }),
  targetSent: (cid: number, tid: number) => post<{ logged: number }>(`/campaigns/${cid}/targets/${tid}/sent`, {}),
  setCampaign: (id: number, status: string) => patch<{ ok: boolean }>(`/campaigns/${id}`, { status }),
  deleteCampaign: (id: number) => del<{ ok: boolean }>(`/campaigns/${id}`),
  // hội thoại
  conversations: (p: { status?: string; q?: string }) => j<{ items: Thread[]; counts: Record<string, number>; labels: Record<string, string>; total: number; contacted: number }>(`/conversations${qs(p)}`),
  conversation: (id: string) => j<ConvDetail>(`/conversations/${id}`),
  addMessage: (id: string, b: { direction: "in" | "out"; body: string; channel: string; product?: string }) => post<{ message: Msg; effects: string[]; suggestion: Suggestion | null }>(`/conversations/${id}/messages`, b),
  suggest: (id: string, b: { intent?: string; language?: string; use_llm?: boolean }) => post<Suggestion>(`/conversations/${id}/suggest`, b),
  setOptOut: (id: string, opt_out: boolean) => post<{ ok: boolean }>(`/conversations/${id}/optout`, { opt_out }),
  followups: () => j<{ items: Followup[]; total: number }>("/followups/due"),
  // lập luận
  explain: (id: string) => j<Explain>(`/reasoning/customer/${id}`),
  runs: () => j<{ items: AgentRunRow[] }>("/reasoning/runs"),
  run: (id: number) => j<AgentRunFull>(`/reasoning/runs/${id}`),
  // phân tích
  analytics: () => j<Analytics>("/analytics"),
  // cài đặt
  settings: () => j<SettingsResp>("/settings"),
  saveSettings: (b: Partial<CorpSettings>) => put<{ settings: CorpSettings }>("/settings", b),
  clearDemo: () => post<{ deleted: number }>("/admin/clear-demo", {}),
  /** Tải bản sao lưu CSDL (Admin). Dùng fetch → blob vì cần header Authorization. */
  downloadBackup: async () => {
    const res = await fetch("/api/corp/admin/backup");
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
    }
    const cd = res.headers.get("content-disposition") ?? "";
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    const name = m ? decodeURIComponent(m[1]) : `banking_crm-${new Date().toISOString().slice(0, 10)}.db`;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    return name;
  },
  // import
  importBatches: () => j<{ items: ImportBatch[]; pending: number }>("/import/batches"),
  importUpload: async (file: File, target: string, ocr: string, sheet?: string): Promise<ImportUpload> => {
    const res = await fetch(`/api/corp/import/upload${qs({ filename: file.name, target, ocr, sheet })}`, { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
    }
    return res.json();
  },
  importPreview: (id: number, b: { mapping: Record<string, string>; update_existing: boolean; default_rm?: string }) => post<ImportPreview>(`/import/${id}/preview`, b),
  importCommit: (id: number, b: { mapping: Record<string, string>; update_existing: boolean; default_rm?: string; note?: string }) => post<{ status: string; created?: number; updated?: number; stats: any }>(`/import/${id}/commit`, b),
  importDetail: (id: number) => j<{ batch: ImportBatch; sample: Record<string, string>[] }>(`/import/${id}`),
  importApprove: (id: number) => post<{ created: number; updated: number }>(`/import/${id}/approve`, {}),
  importReject: (id: number, note: string) => post<{ status: string }>(`/import/${id}/reject`, { note }),
  importCancel: (id: number) => del<{ ok: boolean }>(`/import/${id}`),
  downloadTemplate: async (target: string) => {
    const res = await fetch(`/api/corp/import/template?target=${target}`);
    if (!res.ok) throw new Error("Không tải được file mẫu");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = target === "monthly" ? "mau_import_dong_tien_thang.xlsx" : "mau_import_khach_hang_dn.xlsx";
    a.click();
    URL.revokeObjectURL(a.href);
  },
};

export const accountsApi = {
  users: () => raw<{ items: UserRow[] }>("/api/admin/users"),
  createUser: (b: { username: string; full_name: string; role: string; rm_name?: string; password: string }) => raw<UserRow>("/api/admin/users", jsonInit("POST", b)),
  patchUser: (id: number, b: Partial<{ full_name: string; role: string; rm_name: string; is_active: boolean; new_password: string }>) => raw<UserRow>(`/api/admin/users/${id}`, jsonInit("PATCH", b)),
  audit: (p: { limit?: number; username?: string; action?: string }) => raw<{ items: AuditRow[] }>(`/api/admin/audit${qs(p)}`),
};
