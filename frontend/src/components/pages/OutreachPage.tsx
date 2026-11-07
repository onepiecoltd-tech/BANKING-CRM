import { useState } from "react";
import { motion } from "framer-motion";
import { PageHeader, tooltipStyle } from "./DashboardPage";
import { customers, formatINR } from "@/lib/mockData";
import {
  Sparkles, Send, Calendar, Shield, Copy, ThumbsUp, ThumbsDown,
  Zap, MessageSquare, ArrowRight,
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { t } from "@/lib/i18n";

const FRAMEWORKS = [
  { id: "AIDA", name: "AIDA", desc: t("Attention · Interest · Desire · Action"), color: "primary" },
  { id: "SPIN", name: "SPIN", desc: t("Situation · Problem · Implication · Need"), color: "accent" },
  { id: "CIALDINI", name: "Cialdini", desc: t("Authority · Scarcity · Social Proof"), color: "warning" },
];

const VARIANTS = [
  {
    id: "A", framework: "AIDA · Authority",
    text: `Hi {{name}}, this is Rohan from your relationship desk. I noticed your FD matures next week and wanted to share a pre-approved Personal Loan of ₹12L at 10.49% — fully digital, with funds in 2 hours. Would 3 mins on call work tomorrow?`,
    hooks: ["FD maturity", "Pre-approved", "10.49%"],
    estConv: 71, estResponse: 44,
  },
  {
    id: "B", framework: "Cialdini · Social Proof",
    text: `Hi {{name}} 👋 — quick heads-up: based on your relationship with us, you're pre-approved for ₹12L Personal Loan at 10.49% (no docs). Many {{city}} clients use it to consolidate higher-cost EMIs. Reply YES and I'll share the offer letter.`,
    hooks: ["Personalized city", "Social proof", "Soft CTA"],
    estConv: 68, estResponse: 51,
  },
];

export function OutreachPage() {
  const [framework, setFramework] = useState("AIDA");
  const [selected, setSelected] = useState("A");
  const eligible = 14;
  const suppressed = 4;

  const audienceData = customers.slice(0, 8).map((c) => ({
    name: c.name.split(" ")[0],
    score: c.conversionScore,
  }));

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Outreach Center")}
        subtitle={t("AI-generated personalized WhatsApp campaigns with A/B testing, persuasion frameworks, and compliance suppression.")}
        actions={
          <button className="text-xs px-3 py-1.5 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center gap-1.5 hover:opacity-90">
            <Send className="w-3.5 h-3.5" /> New Campaign
          </button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Audience */}
        <div className="glass rounded-xl p-5 shadow-card space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" /> Audience
          </div>
          <div className="text-xs text-muted-foreground">{t("High-value, loan-eligible · Mumbai")}</div>

          <div className="grid grid-cols-2 gap-2 text-center">
            <Stat label={t("Eligible")} value={eligible} accent="success" />
            <Stat label={t("Suppressed")} value={suppressed} accent="warning" />
          </div>

          <div className="rounded-lg bg-muted/30 p-3">
            <div className="text-[10px] text-muted-foreground mb-2 flex items-center gap-1.5">
              <Shield className="w-3 h-3" /> Suppression checks (last 24h)
            </div>
            <ul className="space-y-1 text-[11px]">
              <li className="flex justify-between"><span>{t("DND list")}</span><span className="text-warning font-mono">{t("2 blocked")}</span></li>
              <li className="flex justify-between"><span>{t("Frequency cap (14d)")}</span><span className="text-warning font-mono">{t("1 blocked")}</span></li>
              <li className="flex justify-between"><span>{t("Opt-out registry")}</span><span className="text-warning font-mono">{t("1 blocked")}</span></li>
              <li className="flex justify-between"><span>{t("Quiet hours filter")}</span><span className="text-success font-mono">{t("passed")}</span></li>
            </ul>
          </div>

          <div>
            <div className="text-[10px] text-muted-foreground mb-1">{t("Top scored audience")}</div>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={audienceData}>
                <CartesianGrid stroke="#ffffff08" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#ffffff08" }} />
                <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                  {audienceData.map((d, i) => (
                    <Cell key={i} fill={d.score > 75 ? "#34d399" : d.score > 50 ? "#5b8bff" : "#fbbf24"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Composer */}
        <div className="lg:col-span-2 glass rounded-xl p-5 shadow-card space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary" /> AI Message Composer
            </div>
            <div className="text-[10px] text-muted-foreground">{t("Personalization tokens active")}</div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">{t("Persuasion Framework")}</div>
            <div className="grid grid-cols-3 gap-2">
              {FRAMEWORKS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setFramework(f.id)}
                  className={`text-left p-2.5 rounded-lg border transition ${
                    framework === f.id ? "border-primary/50 bg-primary/10" : "border-border bg-muted/30 hover:bg-muted/50"
                  }`}
                >
                  <div className="text-xs font-semibold">{f.name}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{f.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-3">
            {VARIANTS.map((v) => (
              <motion.div
                key={v.id}
                onClick={() => setSelected(v.id)}
                whileHover={{ y: -2 }}
                className={`relative rounded-xl p-4 cursor-pointer border transition ${
                  selected === v.id ? "border-primary/50 bg-primary/5 ring-glow" : "border-border bg-muted/30"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-card text-foreground font-mono font-semibold">
                      Variant {v.id}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{v.framework}</span>
                  </div>
                  <button className="text-muted-foreground hover:text-foreground"><Copy className="w-3 h-3" /></button>
                </div>
                <div className="text-xs leading-relaxed text-foreground/90">
                  {v.text.split(/(\{\{[^}]+\}\})/g).map((part, i) =>
                    part.startsWith("{{") ? (
                      <span key={i} className="text-primary font-medium">{part.replace(/[{}]/g, "")}</span>
                    ) : <span key={i}>{part}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1 mt-2.5">
                  {v.hooks.map((h) => (
                    <span key={h} className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">{h}</span>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-border">
                  <Mini label={t("Est. response")} value={`${v.estResponse}%`} />
                  <Mini label={t("Est. conversion")} value={`${v.estConv}%`} />
                </div>
                <div className="flex gap-1 mt-2">
                  <button className="flex-1 text-[10px] py-1 rounded bg-muted/60 hover:bg-muted flex items-center justify-center gap-1">
                    <ThumbsUp className="w-3 h-3" /> Approve
                  </button>
                  <button className="flex-1 text-[10px] py-1 rounded bg-muted/60 hover:bg-muted flex items-center justify-center gap-1">
                    <ThumbsDown className="w-3 h-3" /> Regenerate
                  </button>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="rounded-lg border border-border bg-card/40 p-3 flex items-center gap-3">
            <Calendar className="w-4 h-4 text-accent" />
            <div className="flex-1">
              <div className="text-xs font-medium">{t("Send-time optimization")}</div>
              <div className="text-[10px] text-muted-foreground">{t("AI predicted optimal window:")} <span className="text-foreground">{t("Tue 11:30 AM IST")}</span> {t("(+38% open vs. baseline)")}</div>
            </div>
            <button className="text-xs px-3 py-1.5 rounded-lg gradient-primary text-primary-foreground font-medium flex items-center gap-1">
              Schedule <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Active campaigns */}
      <div className="glass rounded-xl p-5 shadow-card">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-semibold flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-accent" /> Active Campaigns
          </div>
          <div className="text-[10px] text-muted-foreground">{t("14 running · 2 paused")}</div>
        </div>
        <div className="space-y-2">
          {[
            { name: "Mumbai HNI · Personal Loan", sent: 412, opened: 268, replied: 91, conv: 18, value: 21000000 },
            { name: "Pan-India · Pre-approved Credit", sent: 1840, opened: 980, replied: 312, conv: 67, value: 4500000 },
            { name: "Bengaluru · Mutual Funds Cross-sell", sent: 624, opened: 401, replied: 145, conv: 22, value: 12000000 },
            { name: "Delhi · FD Renewal Reminder", sent: 1102, opened: 712, replied: 198, conv: 41, value: 8800000 },
          ].map((c) => (
            <div key={c.name} className="grid grid-cols-12 items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border hover:border-primary/30 transition">
              <div className="col-span-12 md:col-span-3 text-sm font-medium">{c.name}</div>
              <Cell2 label={t("Sent")} value={c.sent} />
              <Cell2 label={t("Opened")} value={c.opened} />
              <Cell2 label={t("Replied")} value={c.replied} />
              <Cell2 label={t("Converted")} value={c.conv} accent />
              <Cell2 label={t("Value")} value={formatINR(c.value)} />
              <div className="col-span-12 md:col-span-1 flex justify-end">
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-success/15 text-success font-medium">{t("Live")}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent: "success" | "warning" }) {
  const cls = accent === "success" ? "text-success" : "text-warning";
  return (
    <div className="rounded-lg bg-muted/30 p-3">
      <div className={`text-2xl font-display font-semibold ${cls}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}
function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="text-xs font-semibold">{value}</div>
    </div>
  );
}
function Cell2({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="col-span-6 md:col-span-2">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={`text-sm font-mono ${accent ? "text-accent font-semibold" : ""}`}>{value}</div>
    </div>
  );
}
