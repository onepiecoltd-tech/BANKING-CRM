import { useState } from "react";
import { PageHeader } from "./DashboardPage";
import { Sparkles, Database, Send, Shield, FileText, CheckCircle2 } from "lucide-react";
import { t } from "@/lib/i18n";

export function SettingsPage() {
  const [llm, setLlm] = useState("gemini");
  const [crm, setCrm] = useState("sqlite");
  const [sender, setSender] = useState("mock");

  return (
    <div className="space-y-5">
      <PageHeader title="Admin & Settings" subtitle={t("Pluggable architecture — swap providers without code changes.")} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ProviderCard
          icon={Sparkles} title={t("LLM Provider")}
          options={[
            { id: "gemini", name: "Gemini 2.0 Flash", desc: t("Google · default · multimodal") },
            { id: "ollama", name: "Ollama qwen2.5:7b", desc: t("Local · private · offline") },
          ]}
          value={llm} onChange={setLlm}
        />
        <ProviderCard
          icon={Database} title={t("CRM Backend")}
          options={[
            { id: "sqlite", name: "SQLite", desc: t("Built-in · zero setup") },
            { id: "hubspot", name: "HubSpot", desc: t("Adapter · live sync") },
          ]}
          value={crm} onChange={setCrm}
        />
        <ProviderCard
          icon={Send} title={t("Outreach Sender")}
          options={[
            { id: "mock", name: "Mock Sender", desc: t("Demo · dry-run only") },
            { id: "twilio", name: "Twilio WhatsApp", desc: t("Production · live sends") },
          ]}
          value={sender} onChange={setSender}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-success" />
            <div className="text-sm font-semibold">Compliance & Suppressions</div>
          </div>
          <div className="space-y-2 text-xs">
            {[
              ["DND registry sync", "Every 4h"],
              ["Quiet hours filter", "9 PM – 9 AM IST"],
              ["Frequency cap", "1 message / 14 days"],
              ["PII scrubbing in prompts", "Enabled"],
              ["Audit log retention", "365 days"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between p-2 rounded bg-muted/30">
                <span className="text-muted-foreground">{k}</span>
                <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-success" />{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-accent" /><div className="text-sm font-semibold">{t("Audit Log")}</div>
          </div>
          <div className="space-y-1.5 text-[11px] font-mono max-h-72 overflow-y-auto pr-1">
            {[
              "10:49:12  agent.send_outreach  audience=14  status=ok",
              "10:48:55  classify_intent  customer=CUST-10024  intent=qualified",
              "10:42:01  handle_objection  framework=cialdini  conf=0.89",
              "10:41:32  classify_intent  intent=objection_pricing",
              "10:32:00  campaign.start  id=mumbai_hni_loan",
              "09:14:08  llm.switch  from=gemini  to=ollama  by=admin",
              "08:00:01  cron.score_customers  scored=520  ms=2410",
            ].map((l, i) => (
              <div key={i} className="px-2 py-1 rounded bg-muted/30">
                <span className="text-muted-foreground">{l.slice(0, 10)}</span>{" "}
                <span>{l.slice(10)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProviderCard({ icon: Icon, title, options, value, onChange }: {
  icon: React.ElementType; title: string;
  options: { id: string; name: string; desc: string }[];
  value: string; onChange: (v: string) => void;
}) {
  return (
    <div className="glass rounded-xl p-5 shadow-card">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-primary" />
        <div className="text-sm font-semibold">{title}</div>
      </div>
      <div className="space-y-2">
        {options.map((o) => {
          const active = value === o.id;
          return (
            <button key={o.id} onClick={() => onChange(o.id)}
              className={`w-full text-left p-3 rounded-lg border transition ${
                active ? "border-primary/50 bg-primary/10 ring-glow" : "border-border bg-muted/30 hover:bg-muted/50"
              }`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{o.name}</div>
                  <div className="text-[10px] text-muted-foreground">{o.desc}</div>
                </div>
                {active && <CheckCircle2 className="w-4 h-4 text-primary" />}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
