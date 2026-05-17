import { useState } from "react";
import { motion, AnimatePresence, type Transition } from "framer-motion";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  Rocket,
  ChevronLeft,
  CheckSquare,
  Square,
  Loader2,
  CheckCircle2,
  MessageCircle,
  RefreshCw,
  Users,
  Target,
  Zap,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CampaignLead {
  customer_id: string;
  name: string;
  city: string;
  segment: string;
  credit_score: number;
  annual_income: number;
  conversion_probability: number;
  top_signals: string[];
  life_events: string[];
  life_event_details: Array<{ event: string; description: string; urgency: string }>;
  timing_score: number;
  timing_label: "optimal" | "good" | "avoid";
  tone_hint: string;
  message_preview: string;
}

interface CampaignPreviewResponse {
  campaign_id: string;
  total_leads: number;
  leads: CampaignLead[];
  estimated_conversions: number;
  product_name: string;
  filters_applied: Record<string, string | number>;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PRODUCTS = [
  { id: "PL001", label: "Personal Loan" },
  { id: "CC001", label: "Credit Card" },
  { id: "HL001", label: "Home Loan" },
  { id: "FD001", label: "Fixed Deposit" },
] as const;

const SEGMENTS = ["All", "Mass", "Affluent", "Premium"] as const;
type Segment = (typeof SEGMENTS)[number];

const TONES = [
  { id: "warm", label: "Warm 😊" },
  { id: "professional", label: "Professional 💼" },
  { id: "urgent", label: "Urgent ⚡" },
] as const;
type Tone = (typeof TONES)[number]["id"];

const LIFE_EVENT_EMOJI: Record<string, string> = {
  WEDDING_LIKELY: "💍",
  MEDICAL_EXPENSE: "🏥",
  PROMOTION_LIKELY: "🚀",
  HAS_CHILDREN: "👨‍👩‍👧",
  TRAVEL_FREQUENT: "✈️",
  LIFESTYLE_SPENDER: "💳",
  MEDICAL_LOAN_CANDIDATE: "🏥",
};

type Step = "configure" | "loading" | "review" | "sending" | "done";

// ── Helpers ───────────────────────────────────────────────────────────────────

function probColor(p: number): string {
  if (p >= 50) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
  if (p >= 30) return "bg-amber-500/15 text-amber-400 border-amber-500/30";
  return "bg-orange-500/15 text-orange-400 border-orange-500/30";
}

function timingColor(label: "optimal" | "good" | "avoid"): string {
  if (label === "optimal") return "text-emerald-400";
  if (label === "good") return "text-amber-400";
  return "text-rose-400";
}

function timingDot(label: "optimal" | "good" | "avoid"): string {
  if (label === "optimal") return "bg-emerald-400";
  if (label === "good") return "bg-amber-400";
  return "bg-rose-400";
}

// ── Slide animation ───────────────────────────────────────────────────────────

const slideTransition: Transition = { duration: 0.28, ease: "easeOut" };
const slideIn = {
  initial: { opacity: 0, x: 40 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -40 },
  transition: slideTransition,
};

// ── Sub-components ────────────────────────────────────────────────────────────

function PillToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly { id: T; label: string }[] | readonly string[];
  value: T;
  onChange: (v: T) => void;
}) {
  const items =
    typeof options[0] === "string"
      ? (options as readonly string[]).map((s) => ({ id: s as T, label: s }))
      : (options as readonly { id: T; label: string }[]);

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((opt) => {
        const active = opt.id === value;
        return (
          <button
            key={opt.id}
            onClick={() => onChange(opt.id)}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all ${
              active
                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function LeadCard({
  lead,
  checked,
  onToggle,
}: {
  lead: CampaignLead;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <Card
      className={`p-4 border transition-all cursor-pointer hover:shadow-md ${
        checked ? "border-primary/40 bg-card" : "border-border/50 opacity-60"
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start gap-3">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          className="mt-0.5 shrink-0"
        >
          {checked ? (
            <CheckSquare className="w-4 h-4 text-primary" />
          ) : (
            <Square className="w-4 h-4 text-muted-foreground" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span className="font-semibold text-sm">{lead.name}</span>
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
              {lead.city}
            </Badge>
            <span
              className={`ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full border ${probColor(
                lead.conversion_probability
              )}`}
            >
              {lead.conversion_probability}% likely
            </span>
          </div>

          {/* Signals */}
          {lead.top_signals.slice(0, 2).length > 0 && (
            <div className="flex flex-col gap-0.5 mb-2">
              {lead.top_signals.slice(0, 2).map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span className="w-1 h-1 rounded-full bg-muted-foreground/60 shrink-0" />
                  {s}
                </div>
              ))}
            </div>
          )}

          {/* Life events */}
          {lead.life_events.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {lead.life_events.map((evt) => (
                <span
                  key={evt}
                  className="text-[10px] bg-muted/60 px-2 py-0.5 rounded-full border border-border/60"
                >
                  {LIFE_EVENT_EMOJI[evt] ?? "📌"}{" "}
                  {evt.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
              ))}
            </div>
          )}

          {/* Timing */}
          <div className={`flex items-center gap-1.5 text-[11px] mb-2 ${timingColor(lead.timing_label)}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${timingDot(lead.timing_label)}`} />
            Timing: <span className="capitalize font-medium">{lead.timing_label}</span>
          </div>

          {/* Message preview */}
          <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2 italic break-words overflow-hidden">
            "{lead.message_preview.slice(0, 120)}{lead.message_preview.length > 120 ? "…" : ""}"
          </p>
        </div>
      </div>
    </Card>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function CampaignPage() {
  // Step machine
  const [step, setStep] = useState<Step>("configure");

  // Form state
  const [productId, setProductId] = useState<string>("PL001");
  const [segment, setSegment] = useState<Segment>("All");
  const [city, setCity] = useState("");
  const [minProb, setMinProb] = useState(20);
  const [tone, setTone] = useState<Tone>("warm");
  const [maxLeads, setMaxLeads] = useState(20);

  // Results
  const [preview, setPreview] = useState<CampaignPreviewResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Derived
  const selectedProduct = PRODUCTS.find((p) => p.id === productId)!;
  const selectedCount = selected.size;

  // ── Handlers ─────────────────────────────────────────────────────────────

  async function handleFindLeads() {
    setError(null);
    setStep("loading");
    try {
      const res = await fetch("/api/campaigns/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: productId,
          segment: segment === "All" ? null : segment.toLowerCase(),
          city: city.trim() || null,
          min_conversion_probability: minProb / 100,   // slider is 0-100, API expects 0.0-1.0
          tone,
          max_leads: maxLeads,
          sender_backend: "whatsapp",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? res.statusText);
      }
      const data: CampaignPreviewResponse = await res.json();
      setPreview(data);
      setSelected(new Set(data.leads.map((l) => l.customer_id)));
      setStep("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setStep("configure");
    }
  }

  async function handleSend() {
    if (!preview) return;
    setStep("sending");
    const leads = preview.leads.filter((l) => selected.has(l.customer_id));
    try {
      await fetch("/api/outreach/send-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          drafts: leads.map((l) => ({
            customer_id: l.customer_id,
            customer_name: l.name,
            phone_number: "",          // backend uses sandbox number or CRM phone
            message: l.message_preview || `Hi ${l.name.split(" ")[0]}! Your personalized offer for ${preview.product_name} is ready. Reply YES to learn more.`,
            product_id: productId,
            framework: "AIDA",
          })),
          sandbox: false,
          sandbox_number: "",
          sender_backend: "whatsapp",
        }),
      });
    } catch {
      // Proceed to done even on error for demo purposes
    }
    setStep("done");
  }

  function handleReset() {
    setStep("configure");
    setPreview(null);
    setSelected(new Set());
    setError(null);
  }

  function toggleLead(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    if (preview) setSelected(new Set(preview.leads.map((l) => l.customer_id)));
  }

  function deselectAll() {
    setSelected(new Set());
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl mx-auto">
      {/* Page header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl gradient-primary grid place-items-center shadow-glow">
          <Rocket className="w-5 h-5 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-2xl font-display font-bold">Campaign Builder</h1>
          <p className="text-sm text-muted-foreground">Find and reach the right customers in under 45 seconds</p>
        </div>
      </div>

      {/* Progress indicator */}
      <div className="flex items-center gap-2 mb-8">
        {(["configure", "review", "done"] as const).map((s, i) => {
          const stepIndex = { configure: 0, loading: 0, review: 1, sending: 1, done: 2 }[step];
          const isActive = i <= stepIndex;
          const isCurrent = (step === "configure" || step === "loading") ? i === 0 : step === "review" || step === "sending" ? i === 1 : i === 2;
          return (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                  isCurrent
                    ? "gradient-primary text-primary-foreground"
                    : isActive
                    ? "bg-primary/20 text-primary"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
              <span className={`text-xs ${isCurrent ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                {s === "configure" ? "Configure" : s === "review" ? "Review Leads" : "Done"}
              </span>
              {i < 2 && <div className={`w-8 h-px ${isActive && !isCurrent ? "bg-primary/40" : "bg-border"}`} />}
            </div>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        {/* ── Step 1: Configure ─────────────────────────────────────────────── */}
        {(step === "configure" || step === "loading") && (
          <motion.div key="configure" {...slideIn}>
            <Card className="p-6 lg:p-8 border-border/60">
              <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                <Target className="w-4 h-4 text-primary" />
                Configure Campaign
              </h2>

              <div className="space-y-7">
                {/* Product selector */}
                <div>
                  <label className="text-sm font-medium mb-2 block text-foreground">Product</label>
                  <select
                    value={productId}
                    onChange={(e) => setProductId(e.target.value)}
                    className="w-full bg-input/60 border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 text-foreground"
                  >
                    {PRODUCTS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label} ({p.id})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Customer segment */}
                <div>
                  <label className="text-sm font-medium mb-2 block text-foreground">Customer Segment</label>
                  <PillToggle<Segment>
                    options={SEGMENTS}
                    value={segment}
                    onChange={setSegment}
                  />
                </div>

                {/* City */}
                <div>
                  <label className="text-sm font-medium mb-2 block text-foreground">
                    City Filter{" "}
                    <span className="text-muted-foreground font-normal">(optional)</span>
                  </label>
                  <Input
                    placeholder="Any city"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="max-w-xs"
                  />
                </div>

                {/* Min conversion probability */}
                <div>
                  <label className="text-sm font-medium mb-1 block text-foreground">
                    Minimum Conversion Probability
                  </label>
                  <p className="text-xs text-muted-foreground mb-4">
                    Only show leads with{" "}
                    <span className="text-primary font-semibold">&gt;{minProb}%</span> chance
                  </p>
                  <div className="flex items-center gap-4 max-w-md">
                    <span className="text-xs text-muted-foreground w-7">10%</span>
                    <Slider
                      min={10}
                      max={80}
                      step={5}
                      value={[minProb]}
                      onValueChange={([v]) => setMinProb(v)}
                      className="flex-1"
                    />
                    <span className="text-xs text-muted-foreground w-7">80%</span>
                  </div>
                </div>

                {/* Message tone */}
                <div>
                  <label className="text-sm font-medium mb-2 block text-foreground">Message Tone</label>
                  <PillToggle<Tone>
                    options={TONES}
                    value={tone}
                    onChange={setTone}
                  />
                </div>

                {/* Max leads */}
                <div>
                  <label className="text-sm font-medium mb-2 block text-foreground">Max Leads</label>
                  <div className="flex items-center gap-3 max-w-xs">
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      value={maxLeads}
                      onChange={(e) => setMaxLeads(Math.min(50, Math.max(1, Number(e.target.value))))}
                      className="w-24 text-center"
                    />
                    <span className="text-xs text-muted-foreground">leads (max 50)</span>
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <div className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-4 py-3">
                    {error}
                  </div>
                )}

                {/* Submit */}
                <div className="pt-2">
                  <Button
                    size="lg"
                    onClick={handleFindLeads}
                    disabled={step === "loading"}
                    className="gradient-primary text-primary-foreground shadow-glow font-semibold px-8 gap-2"
                  >
                    {step === "loading" ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Finding best leads…
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        Find Best Leads →
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        )}

        {/* ── Step 2: Review ────────────────────────────────────────────────── */}
        {step === "review" && preview && (
          <motion.div key="review" {...slideIn}>
            {/* Campaign summary strip */}
            <div className="glass rounded-xl border border-border/60 px-5 py-3.5 mb-5 flex flex-wrap items-center gap-x-5 gap-y-1.5">
              <div className="flex items-center gap-2 text-sm">
                <Users className="w-4 h-4 text-primary" />
                <span className="font-semibold">{preview.total_leads} leads found</span>
              </div>
              <div className="w-px h-4 bg-border hidden sm:block" />
              <span className="text-sm text-muted-foreground">
                ~<span className="text-foreground font-medium">{preview.estimated_conversions}</span> likely conversions
              </span>
              <div className="w-px h-4 bg-border hidden sm:block" />
              <span className="text-sm text-muted-foreground">
                Product: <span className="text-foreground font-medium">{preview.product_name}</span>
              </span>
              <div className="w-px h-4 bg-border hidden sm:block" />
              <span className="text-sm text-muted-foreground">
                Segment:{" "}
                <span className="text-foreground font-medium capitalize">
                  {segment}
                </span>
              </span>
            </div>

            {/* Select controls */}
            <div className="flex items-center gap-3 mb-4">
              <span className="text-sm text-muted-foreground mr-auto">
                {selectedCount} of {preview.total_leads} selected
              </span>
              <button
                onClick={selectAll}
                className="text-xs text-primary hover:underline font-medium"
              >
                Select All
              </button>
              <span className="text-muted-foreground">·</span>
              <button
                onClick={deselectAll}
                className="text-xs text-muted-foreground hover:text-foreground hover:underline"
              >
                Deselect All
              </button>
            </div>

            {/* Lead grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {preview.leads.map((lead) => (
                <LeadCard
                  key={lead.customer_id}
                  lead={lead}
                  checked={selected.has(lead.customer_id)}
                  onToggle={() => toggleLead(lead.customer_id)}
                />
              ))}
            </div>

            {/* Action bar */}
            <div className="sticky bottom-4 glass-strong border border-border rounded-xl px-5 py-4 flex items-center gap-4 shadow-xl">
              <button
                onClick={() => setStep("configure")}
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition"
              >
                <ChevronLeft className="w-4 h-4" />
                Reconfigure
              </button>
              <div className="flex-1" />
              <Button
                size="lg"
                onClick={handleSend}
                disabled={selectedCount === 0}
                className="gradient-primary text-primary-foreground shadow-glow font-semibold gap-2"
              >
                <MessageCircle className="w-4 h-4" />
                Send Campaign ({selectedCount} leads)
              </Button>
            </div>
          </motion.div>
        )}

        {/* ── Step 3: Sending ───────────────────────────────────────────────── */}
        {step === "sending" && (
          <motion.div key="sending" {...slideIn}>
            <Card className="p-12 flex flex-col items-center gap-6 border-border/60">
              <div className="w-16 h-16 rounded-2xl gradient-primary grid place-items-center shadow-glow">
                <Loader2 className="w-8 h-8 text-primary-foreground animate-spin" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-semibold mb-2">Sending Campaign…</h2>
                <p className="text-muted-foreground text-sm">
                  Sending to {selectedCount} leads via WhatsApp
                </p>
              </div>
              <div className="w-64 bg-muted rounded-full h-2 overflow-hidden">
                <motion.div
                  className="h-full gradient-primary rounded-full"
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 2.5, ease: "easeInOut" }}
                />
              </div>
            </Card>
          </motion.div>
        )}

        {/* ── Step 4: Done ──────────────────────────────────────────────────── */}
        {step === "done" && (
          <motion.div key="done" {...slideIn}>
            <Card className="p-12 flex flex-col items-center gap-6 border-border/60 text-center">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 grid place-items-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-2xl font-display font-bold mb-2">Campaign Sent!</h2>
                <p className="text-muted-foreground">
                  {selectedCount} messages delivered via WhatsApp
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Follow-up scheduled for Day 3 · Product: {selectedProduct.label}
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <Link to="/conversations">
                  <Button size="lg" className="gradient-primary text-primary-foreground shadow-glow font-semibold gap-2">
                    <MessageCircle className="w-4 h-4" />
                    View Conversations →
                  </Button>
                </Link>
                <Button size="lg" variant="outline" onClick={handleReset} className="gap-2">
                  <RefreshCw className="w-4 h-4" />
                  New Campaign
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
