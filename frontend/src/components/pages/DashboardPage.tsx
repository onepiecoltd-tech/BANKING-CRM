import { useQuery } from "@tanstack/react-query";
import { analytics as analyticsApi, customers as customersApi, type KPIs, type ChartData } from "@/lib/api";
import { kpis as mockKpis, customers as mockCustomers, segmentBreakdown as mockSegments, pipelineStages as mockPipeline, conversionTrend as mockTrend, formatINR } from "@/lib/mockData";
import { motion } from "framer-motion";
import {
  Users, TrendingUp, Flame, Wallet, Send, Activity,
  Sparkles, ArrowUpRight, ArrowRight, AlertTriangle,
} from "lucide-react";
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis,
  BarChart, Bar, PieChart, Pie, Cell, CartesianGrid,
} from "recharts";
import { t } from "@/lib/i18n";

const COLORS = ["#5b8bff", "#34d399", "#a78bfa", "#fbbf24", "#f472b6", "#22d3ee"];

export function DashboardPage() {
  const { data: kpiData } = useQuery({
    queryKey: ["kpis"],
    queryFn: analyticsApi.kpis,
    staleTime: 60_000,
  });

  const { data: chartData } = useQuery({
    queryKey: ["charts"],
    queryFn: analyticsApi.charts,
    staleTime: 60_000,
  });

  const { data: recentCustomers } = useQuery({
    queryKey: ["customers", "recent"],
    queryFn: () => customersApi.list({ limit: 6 }),
    staleTime: 60_000,
  });

  const { data: digestData } = useQuery({
    queryKey: ["morning-digest"],
    queryFn: () => fetch("http://localhost:8000/api/digest/morning").then(r => r.json()),
    staleTime: 300_000,
  });

  const { data: churnAlerts } = useQuery({
    queryKey: ["churn-alerts"],
    queryFn: () => fetch("http://localhost:8000/api/analytics/churn-signals?limit=5").then(r => r.json()),
    staleTime: 300_000,
  });

  const { data: crossSellData } = useQuery({
    queryKey: ["cross-sell-dashboard"],
    queryFn: () => fetch("http://localhost:8000/api/analytics/cross-sell?limit=4").then(r => r.json()),
    staleTime: 300_000,
  });

  const kpis = kpiData ?? mockKpis;
  const segmentBreakdown = chartData?.segmentBreakdown ?? mockSegments;
  const conversionTrend = chartData?.conversionTrend?.length ? chartData.conversionTrend : mockTrend;
  const pipelineStages = chartData?.pipelineStages?.length ? chartData.pipelineStages : mockPipeline;

  const cards = [
    { label: t("Total Customers"), value: kpis.totalCustomers.toLocaleString(), delta: "+4.2%", icon: Users, accent: "primary" },
    { label: t("High-Value Customers"), value: kpis.highValue.toLocaleString(), delta: "+8.1%", icon: TrendingUp, accent: "accent" },
    { label: t("Hot Leads (AI Scored)"), value: kpis.hotLeads.toLocaleString(), delta: "+22 today", icon: Flame, accent: "warning" },
    { label: t("Pipeline Value"), value: formatINR(kpis.pipelineValue), delta: "+12.4%", icon: Wallet, accent: "primary" },
  ];

  const recommendations = [
    { title: `${Math.round(kpis.hotLeads * 0.4)} customers ready for personal loan upsell`, confidence: 92, type: "Cross-sell" },
    { title: t("Re-engage dormant HNI clients in Mumbai"), confidence: 84, type: "Retention" },
    { title: `Pre-approved credit upgrade for salaried ${kpis.highValue > 0 ? `(${Math.round(kpis.highValue * 0.22)})` : ""}`, confidence: 78, type: "Campaign" },
  ];

  const activityCustomers = recentCustomers?.items ?? mockCustomers.slice(0, 6);
  const activity = activityCustomers.slice(0, 6).map((c, i) => ({
    name: c.name,
    action: ["replied to outreach", "qualified for loan", "opened campaign", "objection handled by AI", "scheduled call", "moved to CLOSING"][i],
    time: ["2m ago", "8m ago", "21m ago", "44m ago", "1h ago", "2h ago"][i],
    score: "clv_score" in c ? c.clv_score : (c as { conversionScore?: number }).conversionScore ?? 0,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Dashboard")}
        subtitle={t("Real-time view of your portfolio, AI campaigns, and conversion pipeline.")}
      />

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="relative glass rounded-xl p-5 overflow-hidden shadow-card group"
          >
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition" style={{ background: "var(--gradient-glow)" }} />
            <div className="relative flex items-start justify-between">
              <div>
                <div className="text-xs text-muted-foreground">{c.label}</div>
                <div className="mt-2 text-2xl font-display font-semibold tracking-tight">{c.value}</div>
                <div className="mt-1 inline-flex items-center gap-1 text-xs text-success">
                  <ArrowUpRight className="w-3 h-3" />
                  {c.delta}
                </div>
              </div>
              <div className={`w-10 h-10 rounded-lg grid place-items-center ${c.accent === "accent" ? "bg-accent/15 text-accent" : c.accent === "warning" ? "bg-warning/15 text-warning" : "bg-primary/15 text-primary"}`}>
                <c.icon className="w-5 h-5" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Morning Digest */}
      {digestData && (digestData.summary.overnight_replies > 0 || digestData.summary.callbacks_due > 0) && (
        <div className="glass rounded-xl p-5 shadow-card border border-warning/30">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">📋</span>
            <div className="text-sm font-semibold">{t("Morning Digest")}</div>
            <span className="text-[10px] text-muted-foreground ml-auto">{new Date().toLocaleTimeString()}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: t("Overnight Replies"), value: digestData.summary.overnight_replies, color: "text-primary", emoji: "💬" },
              { label: t("Callbacks Due"), value: digestData.summary.callbacks_due, color: "text-warning", emoji: "📞" },
              { label: t("Follow-ups Due"), value: digestData.summary.followups_due_today, color: "text-accent", emoji: "🔁" },
              { label: t("Hot Leads"), value: digestData.summary.hot_leads, color: "text-success", emoji: "🔥" },
            ].map(item => (
              <div key={item.label} className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="text-xl">{item.emoji}</div>
                <div className={`text-2xl font-bold mt-1 ${item.color}`}>{item.value}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{item.label}</div>
              </div>
            ))}
          </div>
          {digestData.callbacks_requested?.length > 0 && (
            <div className="mt-3 space-y-1">
              <div className="text-xs text-muted-foreground font-medium">{t("Pending callbacks:")}</div>
              {digestData.callbacks_requested.slice(0, 3).map((cb: { customer_id: string; name: string; city: string; pipeline_state: string }) => (
                <div key={cb.customer_id} className="flex items-center gap-2 text-xs py-1">
                  <span className="text-warning">📞</span>
                  <span className="font-medium">{cb.name}</span>
                  <span className="text-muted-foreground">{cb.city}</span>
                  <span className="ml-auto text-muted-foreground">{cb.pipeline_state}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 glass rounded-xl p-5 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold">{t("Conversion Pipeline · 12 months")}</div>
              <div className="text-xs text-muted-foreground">{t("Outreach sent vs responded vs converted")}</div>
            </div>
            <div className="flex gap-3 text-xs">
              <Legend dot="#5b8bff" label={t("Sent")} />
              <Legend dot="#a78bfa" label={t("Responded")} />
              <Legend dot="#34d399" label={t("Converted")} />
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={conversionTrend}>
              <defs>
                <linearGradient id="g1" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#5b8bff" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#5b8bff" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="g2" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#34d399" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="g3" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="sent" stroke="#5b8bff" fill="url(#g1)" strokeWidth={2} />
              <Area type="monotone" dataKey="responded" stroke="#a78bfa" fill="url(#g3)" strokeWidth={2} />
              <Area type="monotone" dataKey="converted" stroke="#34d399" fill="url(#g2)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="glass rounded-xl p-5 shadow-card">
          <div className="text-sm font-semibold mb-1">{t("Customer Segments")}</div>
          <div className="text-xs text-muted-foreground mb-3">{t("Portfolio distribution")}</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={segmentBreakdown} dataKey="value" innerRadius={50} outerRadius={80} paddingAngle={3}>
                {segmentBreakdown.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2 mt-3">
            {segmentBreakdown.map((s, i) => (
              <div key={s.name} className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
                <span className="truncate">{s.name}</span>
                <span className="ml-auto text-foreground font-medium">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Pipeline funnel + AI recommendations */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 glass rounded-xl p-5 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold">{t("Lifecycle Pipeline")}</div>
              <div className="text-xs text-muted-foreground">{t("Stage distribution across portfolio")}</div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pipelineStages}>
              <CartesianGrid stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="stage" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {pipelineStages.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="glass rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-primary" />
            <div className="text-sm font-semibold">{t("AI Recommendations")}</div>
          </div>
          <div className="space-y-2.5">
            {recommendations.map((r) => (
              <div key={r.title} className="p-3 rounded-lg bg-muted/40 border border-border hover:border-primary/40 transition cursor-pointer group">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-xs font-medium leading-snug">{r.title}</div>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary flex-shrink-0" />
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary font-medium">{r.type}</span>
                  <div className="flex-1 h-1 bg-muted rounded">
                    <div className="h-full rounded gradient-primary" style={{ width: `${r.confidence}%` }} />
                  </div>
                  <span className="text-[10px] text-muted-foreground">{r.confidence}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Churn Alerts + Cross-sell Opportunities */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

        {/* Churn Alerts */}
        {churnAlerts?.high_risk > 0 && (
          <div className="glass rounded-xl p-5 shadow-card border border-destructive/20">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-destructive" />
              <div className="text-sm font-semibold">{t("Churn Alerts")}</div>
              <span className="ml-2 text-xs bg-destructive/15 text-destructive px-2 py-0.5 rounded-full">{churnAlerts.high_risk} high risk</span>
            </div>
            <div className="space-y-2">
              {churnAlerts.customers
                ?.filter((c: { churn_risk: string }) => c.churn_risk === "high")
                .slice(0, 4)
                .map((c: { customer_id: string; risk_score: number; name: string; signals?: string[]; segment: string }) => (
                  <div key={c.customer_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-destructive/5 border border-destructive/10">
                    <div className="w-8 h-8 rounded-full bg-destructive/20 grid place-items-center text-xs font-bold text-destructive">
                      {c.risk_score}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium">{c.name}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{c.signals?.join(" · ")}</div>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-destructive/15 text-destructive">{c.segment}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Cross-sell Opportunities */}
        {crossSellData?.customers?.length > 0 && (
          <div className="glass rounded-xl p-5 shadow-card border border-primary/20">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-primary" />
              <div className="text-sm font-semibold">{t("Cross-sell Opportunities")}</div>
              {crossSellData.total_opportunities != null && (
                <span className="ml-2 text-xs bg-primary/15 text-primary px-2 py-0.5 rounded-full">{crossSellData.total_opportunities} total</span>
              )}
            </div>
            <div className="space-y-2">
              {crossSellData.customers
                .slice(0, 4)
                .map((opp: { customer_id: string; name: string; product: string; reason?: string; confidence?: number }) => (
                  <div key={opp.customer_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-primary/5 border border-primary/10">
                    <div className="w-8 h-8 rounded-full bg-primary/20 grid place-items-center text-[10px] font-bold text-primary shrink-0">
                      {opp.name.split(" ").map((p: string) => p[0]).slice(0, 2).join("")}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium">{opp.name}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{opp.reason ?? opp.product}</div>
                      {opp.confidence != null && (
                        <div className="mt-1 flex items-center gap-2">
                          <div className="flex-1 h-1 bg-muted rounded">
                            <div className="h-full rounded bg-primary" style={{ width: `${opp.confidence}%` }} />
                          </div>
                          <span className="text-[10px] text-muted-foreground">{opp.confidence}%</span>
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">{opp.product}</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Activity */}
      <div className="glass rounded-xl p-5 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-accent" />
          <div className="text-sm font-semibold">{t("Live Activity")}</div>
          <span className="ml-2 text-[10px] flex items-center gap-1 text-success">
            <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" /> Real-time
          </span>
        </div>
        <div className="divide-y divide-border">
          {activity.map((a) => (
            <div key={a.name + a.time} className="flex items-center gap-3 py-2.5 text-sm">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/30 to-accent/30 grid place-items-center text-[10px] font-semibold">
                {a.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
              </div>
              <div className="flex-1 min-w-0">
                <div className="truncate"><span className="font-medium">{a.name}</span> <span className="text-muted-foreground">{a.action}</span></div>
                <div className="text-[10px] text-muted-foreground">{a.time}</div>
              </div>
              <div className="hidden md:flex items-center gap-2">
                <div className="text-[10px] text-muted-foreground">{t("score")}</div>
                <span className={`text-xs font-semibold ${a.score > 75 ? "text-success" : a.score > 50 ? "text-warning" : "text-muted-foreground"}`}>{Math.round(a.score)}</span>
              </div>
              <Send className="w-4 h-4 text-muted-foreground" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 className="text-2xl font-display font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <span className="w-2 h-2 rounded-full" style={{ background: dot }} />
      {label}
    </span>
  );
}

export const tooltipStyle = {
  background: "rgba(20,25,40,0.92)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 8,
  fontSize: 12,
  color: "#fff",
  backdropFilter: "blur(8px)",
};
