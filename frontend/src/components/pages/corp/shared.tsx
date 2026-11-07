import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { corp } from "@/lib/corpApi";
import { t, getLang } from "@/lib/i18n";

export const COLORS = ["#5b8bff", "#34d399", "#a78bfa", "#fbbf24", "#f472b6", "#22d3ee", "#fb7185"];

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 className="text-2xl font-display font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Card({ title, right, children, className = "" }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`glass rounded-xl p-5 shadow-card ${className}`}>
      {(title || right) && (
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">{title}</div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  const cls = tier === "A" ? "bg-success/15 text-success" : tier === "B" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground";
  return <span className={`inline-block shrink-0 whitespace-nowrap text-[10px] font-semibold px-1.5 py-0.5 rounded ${cls}`}>{t("Hạng", "Tier")} {tier}</span>;
}

export function FlagBadge({ severity, text }: { severity: string; text: string }) {
  const cls = severity === "high" ? "bg-destructive/15 text-destructive" : "bg-warning/15 text-warning";
  return <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded ${cls}`}>{text}</span>;
}

export function useMeta() {
  return useQuery({ queryKey: ["corp", "meta"], queryFn: corp.meta, staleTime: 5 * 60_000 });
}

export function productName(meta: { products: { code: string; vi: string; en: string }[] } | undefined, code: string | null | undefined) {
  if (!code) return "—";
  const p = meta?.products.find((x) => x.code === code);
  if (!p) return code;
  return getLang() === "vi" ? p.vi : p.en;
}

export function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(getLang() === "vi" ? "vi-VN" : "en-GB");
}

export const FLAG_LABEL: Record<string, [string, string]> = {
  HET_HAN_MUC: ["Hạn mức sắp hết hạn", "Limit expiring"],
  DOANH_SO_GIAM: ["Doanh số qua TK giảm", "Inflow decline"],
  NHOM_NO: ["Nợ nhóm ≥ 2", "Debt group ≥ 2"],
  SU_DUNG_CAO: ["Sử dụng hạn mức cao", "High utilisation"],
  CASA_GIAM: ["CASA giảm", "CASA decline"],
};
export const LANG_LABEL: Record<string, string> = { vi: "Tiếng Việt", zh: "中文", en: "English" };
export const CHANNEL_LABEL = (c: string) => (c === "zalo" ? "Zalo" : c === "email" ? "Email" : t("Kịch bản gọi", "Call script"));

export function Select({ value, onChange, options, placeholder }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; placeholder: string }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-input/60 border border-border rounded-lg px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 max-w-[190px]"
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// ── thành phần dùng chung cho các trang DN mới ──────────────────────────────
import { useEffect, useState } from "react";
import { X, Loader2, Search } from "lucide-react";

export function Modal({ title, onClose, children, wide, footer }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className={`relative glass-strong rounded-2xl border border-border shadow-2xl w-full ${wide ? "max-w-4xl" : "max-w-xl"} max-h-[90vh] flex flex-col`}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="font-semibold text-sm">{title}</div>
          <button onClick={onClose} className="w-8 h-8 grid place-items-center rounded-lg hover:bg-muted/60"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 overflow-y-auto flex-1">{children}</div>
        {footer && <div className="px-5 py-3 border-t border-border flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: string; tone?: "success" | "warning" | "destructive" | "primary" }) {
  const c = tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : tone === "destructive" ? "text-destructive" : tone === "primary" ? "text-primary" : "";
  return (
    <div className="glass rounded-xl p-4 shadow-card">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`text-2xl font-display font-semibold mt-1 tabular-nums ${c}`}>{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

export function Spinner() {
  return <div className="py-10 grid place-items-center"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>;
}

export function ErrBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">{(error as Error).message ?? String(error)}</div>;
}

export function Btn({ children, onClick, disabled, kind = "ghost", className = "", type = "button", title }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; kind?: "primary" | "ghost" | "danger"; className?: string; type?: "button" | "submit"; title?: string;
}) {
  const base = "text-xs px-3 py-1.5 rounded-lg font-medium inline-flex items-center gap-1.5 transition disabled:opacity-50 disabled:cursor-not-allowed";
  const k = kind === "primary" ? "gradient-primary text-primary-foreground hover:opacity-90" : kind === "danger" ? "bg-destructive/15 text-destructive hover:bg-destructive/25" : "border border-border hover:bg-muted/50";
  return <button type={type} title={title} onClick={onClick} disabled={disabled} className={`${base} ${k} ${className}`}>{children}</button>;
}

export const inputCls = "bg-input/60 border border-border rounded-lg px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40";

export function Pill({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "success" | "warning" | "destructive" | "primary" }) {
  const cls = { muted: "bg-muted text-muted-foreground", success: "bg-success/15 text-success", warning: "bg-warning/15 text-warning", destructive: "bg-destructive/15 text-destructive", primary: "bg-primary/15 text-primary" }[tone];
  return <span className={`inline-block whitespace-nowrap text-[10px] font-medium px-1.5 py-0.5 rounded ${cls}`}>{children}</span>;
}

export function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(getLang() === "vi" ? "vi-VN" : "en-GB", { dateStyle: "short", timeStyle: "short" });
}

/** Ô tìm khách hàng (theo tên / MST / mã) → trả về mã KH đã chọn. */
export function CustomerPicker({ onPick, placeholder }: { onPick: (id: string, name: string) => void; placeholder?: string }) {
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => { const h = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(h); }, [q]);
  const { data } = useQuery({ queryKey: ["corp", "pick", dq], queryFn: () => corp.customers({ q: dq, limit: 8 }), enabled: dq.length >= 2, staleTime: 30_000 });
  return (
    <div className="relative">
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
      <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        placeholder={placeholder ?? t("Tìm khách hàng (tên, MST, mã)…", "Find customer (name, tax code, ID)…")}
        className={`${inputCls} pl-8 w-full`} />
      {open && dq.length >= 2 && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute z-40 mt-1 w-full glass-strong rounded-lg border border-border shadow-card max-h-64 overflow-y-auto">
            {(data?.items ?? []).length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">{t("Không tìm thấy", "No results")}</div>}
            {(data?.items ?? []).map((c) => (
              <button key={c.customer_id} onClick={() => { onPick(c.customer_id, c.name); setQ(""); setOpen(false); }} className="w-full text-left px-3 py-2 hover:bg-muted/50 text-sm">
                <div className="truncate">{c.name}</div>
                <div className="text-[11px] text-muted-foreground">{c.customer_id} · {c.industry}</div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
