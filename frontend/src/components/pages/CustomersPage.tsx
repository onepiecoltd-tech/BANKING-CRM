import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { customers as customersApi, type ApiCustomer } from "@/lib/api";
import { formatINR } from "@/lib/mockData";
import { PageHeader } from "./DashboardPage";
import {
  Search, Filter, Download, X, TrendingUp, AlertTriangle,
  Sparkles, MapPin, Briefcase, Loader2,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, Tooltip, RadialBarChart, RadialBar,
} from "recharts";
import { tooltipStyle } from "./DashboardPage";
import { t } from "@/lib/i18n";

const SEGMENT_FILTERS = ["All", "premium", "affluent", "mass"];
const SEGMENT_LABELS: Record<string, string> = { All: "All", premium: "Premium", affluent: "Affluent", mass: "Mass" };

export function CustomersPage() {
  const [search, setSearch] = useState("");
  const [seg, setSeg] = useState("All");
  const [active, setActive] = useState<ApiCustomer | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // debounce search input
  const handleSearch = (val: string) => {
    setSearch(val);
    clearTimeout((window as { _st?: ReturnType<typeof setTimeout> })._st);
    (window as { _st?: ReturnType<typeof setTimeout> })._st = setTimeout(() => setDebouncedSearch(val), 300);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["customers", seg, debouncedSearch],
    queryFn: () =>
      customersApi.list({
        segment: seg === "All" ? undefined : seg,
        search: debouncedSearch || undefined,
        limit: 60,
      }),
    staleTime: 30_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Customer Intelligence")}
        subtitle={`${total.toLocaleString()} customers · AI-scored for value and conversion.`}
        actions={
          <button className="text-xs px-3 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted/60 flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" /> Export
          </button>
        }
      />

      <div className="glass rounded-xl p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center shadow-card">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder={t("Search by name, city, or occupation…")}
            className="w-full bg-input/60 border border-border rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        </div>
        <div className="flex items-center gap-1 overflow-x-auto">
          <Filter className="w-3.5 h-3.5 text-muted-foreground mr-1" />
          {SEGMENT_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setSeg(s)}
              className={`text-xs px-2.5 py-1 rounded-md whitespace-nowrap transition ${
                seg === s ? "bg-primary/20 text-primary border border-primary/40" : "text-muted-foreground hover:bg-muted/60 border border-transparent"
              }`}
            >
              {SEGMENT_LABELS[s]}
            </button>
          ))}
        </div>
      </div>

      <div className="glass rounded-xl overflow-hidden shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border bg-card/40">
                <th className="px-4 py-2.5 font-medium">{t("Customer")}</th>
                <th className="px-4 py-2.5 font-medium">{t("Segment")}</th>
                <th className="px-4 py-2.5 font-medium">{t("City")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("Annual Income")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("Balance")}</th>
                <th className="px-4 py-2.5 font-medium text-center">{t("CLV Score")}</th>
                <th className="px-4 py-2.5 font-medium text-center">{t("Credit")}</th>
                <th className="px-4 py-2.5 font-medium">{t("Products")}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-muted-foreground">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Loading customers…
                  </td>
                </tr>
              ) : items.map((c) => (
                <tr
                  key={c.customer_id}
                  onClick={() => setActive(c)}
                  className="border-b border-border/50 hover:bg-muted/30 cursor-pointer transition"
                >
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary/40 to-accent/40 grid place-items-center text-[10px] font-semibold">
                        {c.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                      </div>
                      <div>
                        <div className="font-medium">{c.name}</div>
                        <div className="text-[10px] text-muted-foreground font-mono">{c.customer_id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5"><SegmentPill seg={c.segment} /></td>
                  <td className="px-4 py-2.5 text-muted-foreground">{c.city}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">{formatINR(c.annual_income)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">{formatINR(c.monthly_avg_balance)}</td>
                  <td className="px-4 py-2.5"><ScoreBar value={c.clv_score} /></td>
                  <td className="px-4 py-2.5 text-center text-xs font-mono">{c.credit_score ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {c.has_credit_card && <Pill>{t("CC")}</Pill>}
                      {c.has_personal_loan && <Pill>{t("PL")}</Pill>}
                      {c.has_home_loan && <Pill accent="accent">{t("HL")}</Pill>}
                      {c.has_fd && <Pill accent="warning">{t("FD")}</Pill>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-2.5 text-xs text-muted-foreground border-t border-border flex items-center justify-between">
          <span>Showing {items.length} of {total.toLocaleString()} customers</span>
          <span className="font-mono text-[10px]">{seg !== "All" ? SEGMENT_LABELS[seg] : "All segments"}</span>
        </div>
      </div>

      <AnimatePresence>
        {active && <CustomerDrawer customer={active} onClose={() => setActive(null)} />}
      </AnimatePresence>
    </div>
  );
}

function CustomerDrawer({ customer, onClose }: { customer: ApiCustomer; onClose: () => void }) {
  const { data: txns } = useQuery({
    queryKey: ["transactions", customer.customer_id],
    queryFn: () => customersApi.transactions(customer.customer_id, 90),
    staleTime: 60_000,
  });

  const { data: scoreData } = useQuery({
    queryKey: ["score", customer.customer_id],
    queryFn: () => customersApi.score(customer.customer_id),
    staleTime: 60_000,
  });

  const { data: recsData } = useQuery({
    queryKey: ["recommendations", customer.customer_id],
    queryFn: () => customersApi.recommendations(customer.customer_id),
    staleTime: 60_000,
  });

  // Spending breakdown from transactions
  const spendCategories = ["salary", "shopping", "healthcare", "travel", "dining", "entertainment"];
  const spend = spendCategories.map((cat) => ({
    name: cat.charAt(0).toUpperCase() + cat.slice(1),
    value: Math.round((txns ?? []).filter((t) => t.category?.toLowerCase() === cat).reduce((s, t) => s + t.amount, 0)),
  })).filter((s) => s.value > 0);

  const clvScore = scoreData?.score ?? customer.clv_score;
  const topRec = recsData?.recommendations?.[0];

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
      />
      <motion.div
        initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 28, stiffness: 220 }}
        className="fixed right-0 top-0 bottom-0 w-full max-w-xl glass-strong border-l border-border z-50 overflow-y-auto"
      >
        <div className="p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl gradient-primary grid place-items-center text-sm font-semibold text-primary-foreground">
                {customer.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
              </div>
              <div>
                <h2 className="font-display font-semibold text-lg">{customer.name}</h2>
                <div className="text-xs text-muted-foreground font-mono">{customer.customer_id}</div>
              </div>
            </div>
            <button onClick={onClose} className="w-8 h-8 grid place-items-center rounded-lg hover:bg-muted/60">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <Info icon={MapPin} label={t("City")} value={customer.city ?? "—"} />
            <Info icon={Briefcase} label={t("Occupation")} value={customer.occupation ?? "—"} />
            <InfoText label={t("Annual Income")} value={formatINR(customer.annual_income)} />
            <InfoText label={t("Avg Balance")} value={formatINR(customer.monthly_avg_balance)} />
          </div>

          <div className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/10 to-accent/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-primary" />
              <div className="text-xs font-semibold">{t("AI Summary")}</div>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {customer.name} is a <span className="text-foreground font-medium">{customer.segment}</span> customer
              in {customer.city} with annual income of {formatINR(customer.annual_income)}.
              CLV score is <span className="text-foreground font-medium">{clvScore.toFixed(0)}/100</span> — {
                clvScore > 75 ? "high value" : clvScore > 50 ? "medium value" : "standard"
              } tier.
              {topRec && <> Recommended next action: <span className="text-accent font-medium">{topRec.product_name}</span>.</>}
            </p>
          </div>

          {scoreData && (
            <div className="grid grid-cols-3 gap-3">
              <ScoreCard label={t("CLV Score")} value={Math.round(scoreData.score)} color="#5b8bff" />
              <ScoreCard label={t("Income")} value={Math.round(scoreData.factors.income_norm as number * 100)} color="#34d399" />
              <ScoreCard label={t("Credit")} value={Math.round(scoreData.factors.credit_score_norm as number * 100)} color="#a78bfa" />
            </div>
          )}

          {spend.length > 0 && (
            <div>
              <div className="text-xs font-semibold mb-2 flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-accent" /> Spending breakdown (90 days)
              </div>
              <div className="rounded-xl bg-muted/30 p-3">
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={spend}>
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {spend.map((_, i) => <Cell key={i} fill={["#5b8bff", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#22d3ee"][i % 6]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold mb-2">{t("Products held")}</div>
            <div className="flex flex-wrap gap-1.5">
              {customer.has_credit_card && <Pill>{t("Credit Card")}</Pill>}
              {customer.has_personal_loan && <Pill>{t("Personal Loan")}</Pill>}
              {customer.has_home_loan && <Pill accent="accent">{t("Home Loan")}</Pill>}
              {customer.has_fd && <Pill accent="warning">{t("Fixed Deposit")}</Pill>}
              {!customer.has_credit_card && !customer.has_personal_loan && !customer.has_home_loan && !customer.has_fd && (
                <span className="text-xs text-muted-foreground">{t("No products held")}</span>
              )}
            </div>
            {recsData?.recommendations?.[0] && (
              <div className="mt-3 p-3 rounded-lg border border-accent/30 bg-accent/5">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{t("AI-recommended next product")}</div>
                <div className="text-sm font-medium mt-0.5">{recsData.recommendations[0].product_name}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{recsData.recommendations[0].reasons[0]}</div>
              </div>
            )}
          </div>

          {txns && txns.length > 0 && (
            <div>
              <div className="text-xs font-semibold mb-2">{t("Recent transactions")}</div>
              <div className="rounded-xl border border-border overflow-hidden">
                {txns.slice(0, 8).map((t) => (
                  <div key={t.txn_id} className="flex items-center justify-between px-3 py-2 text-xs border-b border-border last:border-0 bg-card/40">
                    <div>
                      <div className="font-medium">{t.merchant ?? t.category}</div>
                      <div className="text-[10px] text-muted-foreground">{new Date(t.date).toLocaleDateString()} · {t.category}</div>
                    </div>
                    <div className="font-mono text-foreground">{formatINR(t.amount)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button className="flex-1 py-2 rounded-lg gradient-primary text-primary-foreground text-sm font-medium">
              {t("Generate Outreach")}
            </button>
            <button className="flex-1 py-2 rounded-lg border border-border bg-muted/40 text-sm font-medium hover:bg-muted/60">
              {t("Schedule Call")}
            </button>
          </div>
        </div>
      </motion.div>
    </>
  );
}

function Info({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30">
      <Icon className="w-3.5 h-3.5 text-muted-foreground" />
      <div className="min-w-0">
        <div className="text-[10px] text-muted-foreground">{label}</div>
        <div className="truncate">{value}</div>
      </div>
    </div>
  );
}

function InfoText({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30">
      <div className="min-w-0">
        <div className="text-[10px] text-muted-foreground">{label}</div>
        <div className="truncate font-mono">{value}</div>
      </div>
    </div>
  );
}

function ScoreCard({ label, value, color }: { label: string; value: number; color: string }) {
  const data = [{ name: label, value }];
  return (
    <div className="rounded-xl bg-muted/30 p-3 text-center">
      <ResponsiveContainer width="100%" height={80}>
        <RadialBarChart innerRadius="65%" outerRadius="100%" data={data} startAngle={90} endAngle={-270}>
          <RadialBar dataKey="value" cornerRadius={6} fill={color} background={{ fill: "#ffffff10" }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="text-lg font-display font-semibold -mt-7">{value}</div>
      <div className="text-[10px] text-muted-foreground mt-3">{label}</div>
    </div>
  );
}

function ScoreBar({ value }: { value: number }) {
  const color = value > 75 ? "bg-success" : value > 50 ? "bg-primary" : "bg-warning";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded">
        <div className={`h-full rounded ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-[10px] font-mono w-8 text-right">{value.toFixed(0)}</span>
    </div>
  );
}

function Pill({ children, accent = "default" }: { children: React.ReactNode; accent?: "default" | "accent" | "warning" }) {
  const cls = accent === "accent" ? "bg-accent/15 text-accent" : accent === "warning" ? "bg-warning/15 text-warning" : "bg-muted/60 text-muted-foreground";
  return <span className={`inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-md font-medium ${cls}`}>{children}</span>;
}

function SegmentPill({ seg }: { seg: string }) {
  const colors: Record<string, string> = {
    premium: "bg-accent/15 text-accent",
    affluent: "bg-primary/15 text-primary",
    mass: "bg-muted/60 text-muted-foreground",
  };
  return <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium capitalize ${colors[seg] ?? "bg-muted/60 text-muted-foreground"}`}>{seg}</span>;
}
