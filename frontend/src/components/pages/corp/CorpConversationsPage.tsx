import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { MessageSquare, Sparkles, Copy, Check, Send, BellRing, BanIcon, Search, ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { corpX, type Thread, type Suggestion } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { PageHeader, Btn, ErrBox, Pill, Spinner, inputCls, fmtDateTime, copyText, LANG_LABEL, CHANNEL_LABEL, useMeta, productName } from "./shared";

const STATUS_TONE: Record<string, "muted" | "success" | "warning" | "destructive" | "primary"> = {
  HOT: "success", OBJECTION: "warning", OPTOUT: "destructive", WAITING: "muted", REPLIED: "primary", ACK: "muted",
};
const INTENTS: [string, string][] = [
  ["interested", "Quan tâm"], ["meeting", "Hẹn gặp / gọi lại"], ["docs", "Hỏi hồ sơ / thủ tục"], ["approval", "Cần xin ý kiến cấp trên"],
  ["rate", "Lo ngại giá / phí"], ["competitor", "Đang dùng ngân hàng khác"], ["noneed", "Chưa có nhu cầu"], ["ack", "Xác nhận / cảm ơn"], ["other", "Khác"],
];

export function CorpConversationsPage({ customerId }: { customerId?: string }) {
  const nav = useNavigate();
  const { data: meta } = useMeta();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  const [showFollow, setShowFollow] = useState(false);
  useEffect(() => { const h = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(h); }, [q]);
  const list = useQuery({ queryKey: ["corp", "conversations", status, dq], queryFn: () => corpX.conversations({ status: status || undefined, q: dq || undefined }), refetchInterval: 20_000 });
  const follow = useQuery({ queryKey: ["corp", "followups"], queryFn: corpX.followups, refetchInterval: 60_000 });
  const open = (id: string) => nav({ to: "/corp/conversations", search: { customer: id } });
  const counts = list.data?.counts ?? {};
  const labels = list.data?.labels ?? {};

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("Hội thoại khách hàng doanh nghiệp", "Corporate conversations")}
        subtitle={t("Ghi nhận khách phản hồi → hệ thống phân loại ý định (Việt/Anh/Trung) và gợi ý câu trả lời. Gửi tin qua Zalo/Email/điện thoại rồi ghi lại tại đây.", "Log customer replies → the system classifies intent (VI/EN/ZH) and suggests a response. Send via Zalo/email/phone and record it here.")}
        right={
          <Btn onClick={() => setShowFollow((v) => !v)}>
            <BellRing className="w-3.5 h-3.5" /> {t("Cần theo dõi", "Follow-ups due")}
            {(follow.data?.total ?? 0) > 0 && <span className="ml-1 bg-warning/20 text-warning rounded px-1.5">{follow.data!.total}</span>}
          </Btn>
        }
      />

      {showFollow && (
        <div className="glass rounded-xl p-4 shadow-card">
          <div className="text-sm font-semibold mb-2">{t("Khách đã nhận tin nhưng chưa phản hồi (nhắc ở mốc 3 / 7 / 14 ngày)", "Contacted but no reply (reminders at 3 / 7 / 14 days)")}</div>
          {(follow.data?.items ?? []).length === 0 ? <div className="text-xs text-muted-foreground py-3">{t("Chưa có khách nào đến hạn nhắc.", "Nothing due.")}</div> : (
            <div className="divide-y divide-border/60 max-h-72 overflow-y-auto">
              {follow.data!.items.map((f) => (
                <div key={f.customer_id} className="py-2 flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{f.name} <Pill tone="warning">{t("sau", "after")} {f.days} {t("ngày", "days")} · {t("nhắc lần", "step")} {f.step}</Pill></div>
                    <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{f.text}</div>
                  </div>
                  <Btn onClick={() => copyText(f.text)}><Copy className="w-3.5 h-3.5" /></Btn>
                  <Btn onClick={() => open(f.customer_id)}>{t("Mở", "Open")}</Btn>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-[340px_1fr] gap-4 items-start">
        <div className="glass rounded-xl shadow-card overflow-hidden">
          <div className="p-3 border-b border-border space-y-2">
            <div className="relative"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" /><input className={`${inputCls} pl-8 w-full`} placeholder={t("Tìm khách hàng…", "Search customer…")} value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <div className="flex flex-wrap gap-1">
              <button onClick={() => setStatus("")} className={`text-[11px] px-2 py-1 rounded-lg ${status === "" ? "bg-primary/15" : "text-muted-foreground hover:bg-muted/50"}`}>{t("Tất cả", "All")} {list.data?.total ?? 0}</button>
              {Object.entries(labels).map(([k, l]) => (
                <button key={k} onClick={() => setStatus(k)} className={`text-[11px] px-2 py-1 rounded-lg ${status === k ? "bg-primary/15" : "text-muted-foreground hover:bg-muted/50"}`}>{l} {counts[k] ?? 0}</button>
              ))}
            </div>
          </div>
          <div className="max-h-[68vh] overflow-y-auto divide-y divide-border/60">
            {list.isLoading && <Spinner />}
            {(list.data?.items ?? []).map((th: Thread) => (
              <button key={th.customer_id} onClick={() => open(th.customer_id)} className={`w-full text-left px-3 py-2.5 hover:bg-muted/30 ${customerId === th.customer_id ? "bg-primary/10" : ""}`}>
                <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium truncate">{th.name}</span><Pill tone={STATUS_TONE[th.status] ?? "muted"}>{th.status_label}</Pill></div>
                <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1 truncate">
                  {th.last.direction === "in" ? <ArrowDownLeft className="w-3 h-3 text-success shrink-0" /> : <ArrowUpRight className="w-3 h-3 shrink-0" />}
                  <span className="truncate">{th.last.body}</span>
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{th.contact_name ?? "—"} · {th.rm_name} · {fmtDateTime(th.last.created_at)}{th.product ? ` · ${productName(meta, th.product)}` : ""}</div>
              </button>
            ))}
            {!list.isLoading && (list.data?.items ?? []).length === 0 && <div className="p-6 text-center text-sm text-muted-foreground">{t("Chưa có hội thoại. Ghi nhận tin đã gửi từ Trung tâm tiếp cận hoặc chiến dịch.", "No conversations yet. Log sent messages from Outreach or a campaign.")}</div>}
          </div>
        </div>

        {customerId ? <Thread_ id={customerId} /> : (
          <div className="glass rounded-xl shadow-card p-10 text-center text-sm text-muted-foreground"><MessageSquare className="w-8 h-8 mx-auto mb-2 text-primary/60" />{t("Chọn một khách hàng bên trái để xem hội thoại.", "Pick a customer on the left to see the conversation.")}</div>
        )}
      </div>
    </div>
  );
}

function Thread_({ id }: { id: string }) {
  const qc = useQueryClient();
  const { isAdmin } = useAuth();
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "conversation", id], queryFn: () => corpX.conversation(id) });
  const [dir, setDir] = useState<"in" | "out">("in");
  const [channel, setChannel] = useState("zalo");
  const [text, setText] = useState("");
  const [sug, setSug] = useState<Suggestion | null>(null);
  const [intent, setIntent] = useState("");
  const [lang, setLang] = useState("");
  const [effects, setEffects] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setSug(data?.suggestion ?? null); setIntent(data?.suggestion?.intent ?? ""); setLang(""); setEffects([]); }, [data]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [data?.messages.length]);
  const refresh = () => qc.invalidateQueries({ queryKey: ["corp"] });

  const add = useMutation({
    mutationFn: () => corpX.addMessage(id, { direction: dir, body: text.trim(), channel }),
    onSuccess: (r) => { setText(""); setEffects(r.effects); if (r.suggestion) { setSug(r.suggestion); setIntent(r.suggestion.intent); } refresh(); },
  });
  const suggest = useMutation({
    mutationFn: (use_llm: boolean) => corpX.suggest(id, { intent: intent || undefined, language: lang || undefined, use_llm }),
    onSuccess: setSug,
  });
  const optout = useMutation({ mutationFn: (v: boolean) => corpX.setOptOut(id, v), onSuccess: refresh });

  if (isLoading || !data) return <div className="glass rounded-xl p-6">{error ? <ErrBox error={error} /> : <Spinner />}</div>;
  const c = data.customer;

  return (
    <div className="glass rounded-xl shadow-card overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-semibold truncate">{c.name}</div>
          <div className="text-xs text-muted-foreground">{c.contact_name ?? "—"}{c.contact_title ? ` (${c.contact_title})` : ""} · {c.contact_phone ?? ""} {c.contact_email ?? ""} · {LANG_LABEL[c.preferred_language] ?? ""}</div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            <Pill tone={STATUS_TONE[data.status] ?? "muted"}>{data.status_label}</Pill>
            {data.opportunities.map((o) => <Pill key={o.id} tone="primary">{o.product_name}: {o.stage}</Pill>)}
            {data.opted_out && <Pill tone="destructive">{t("Đã từ chối nhận tin", "Opted out")}</Pill>}
          </div>
        </div>
        <div className="flex gap-2">
          <Link to="/corp/customers" search={{ open: c.customer_id }}><Btn>{t("Hồ sơ", "Profile")}</Btn></Link>
          {data.opted_out
            ? (isAdmin ? <Btn onClick={() => optout.mutate(false)}>{t("Gỡ từ chối", "Clear opt-out")}</Btn> : null)
            : <Btn kind="danger" onClick={() => { if (window.confirm(t("Ghi nhận khách hàng này từ chối nhận tin? Họ sẽ bị loại khỏi mọi chiến dịch.", "Mark this customer as opted out? They will be excluded from all outreach."))) optout.mutate(true); }}><BanIcon className="w-3.5 h-3.5" /> {t("Từ chối nhận tin", "Opt-out")}</Btn>}
        </div>
      </div>

      <div className="px-4 py-3 space-y-2.5 max-h-[38vh] overflow-y-auto bg-background/30">
        {data.messages.length === 0 && <div className="text-center text-sm text-muted-foreground py-6">{t("Chưa có tin nhắn.", "No messages yet.")}</div>}
        {data.messages.map((m) => (
          <div key={m.id} className={`flex ${m.direction === "out" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-sm ${m.direction === "out" ? "bg-primary/20 rounded-br-sm" : "bg-muted rounded-bl-sm"}`}>
              {m.subject && <div className="text-[11px] font-medium mb-0.5">{m.subject}</div>}
              <div className="whitespace-pre-wrap leading-relaxed">{m.body}</div>
              <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1.5 flex-wrap">
                <span>{CHANNEL_LABEL(m.channel)}</span><span>· {fmtDateTime(m.created_at)}</span>
                {m.direction === "out" && m.created_by && <span>· {m.created_by}</span>}
                {m.intent_label && <Pill tone="warning">{m.intent_label}</Pill>}
              </div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {sug && (
        <div className="px-4 py-3 border-t border-border bg-accent/5">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <Sparkles className="w-4 h-4 text-accent" /><span className="text-xs font-semibold">{t("Gợi ý trả lời", "Suggested reply")}</span>
            <Pill tone="warning">{sug.intent_label}</Pill>
            {sug.llm_used && <Pill tone="primary">AI</Pill>}
            <div className="flex-1" />
            <select className={`${inputCls} text-xs py-1`} value={intent} onChange={(e) => setIntent(e.target.value)} title={t("Đổi ý định nếu hệ thống hiểu sai", "Change intent if misread")}>
              {INTENTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <select className={`${inputCls} text-xs py-1`} value={lang} onChange={(e) => setLang(e.target.value)}><option value="">{t("Tự nhận ngôn ngữ", "Auto language")}</option>{Object.entries(LANG_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <Btn disabled={suggest.isPending} onClick={() => suggest.mutate(false)}>{t("Tạo lại", "Regenerate")}</Btn>
            <Btn disabled={suggest.isPending} onClick={() => suggest.mutate(true)}><Sparkles className="w-3.5 h-3.5" /> {t("Viết lại bằng AI", "Polish with AI")}</Btn>
          </div>
          <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed bg-card/60 rounded-lg p-3">{sug.text}</pre>
          {sug.llm_error && <div className="text-[11px] text-warning mt-1">{t("AI không phản hồi — dùng mẫu có sẵn:", "AI unavailable — using template:")} {sug.llm_error}</div>}
          <div className="mt-2 flex gap-2"><Btn onClick={() => { setDir("out"); setText(sug.text); }}>{t("Dùng làm tin gửi đi", "Use as outgoing message")}</Btn><Btn onClick={() => copyText(sug.text)}><Copy className="w-3.5 h-3.5" /> {t("Sao chép", "Copy")}</Btn></div>
        </div>
      )}

      <div className="px-4 py-3 border-t border-border">
        {effects.length > 0 && <div className="mb-2 text-xs text-success bg-success/10 rounded-lg px-3 py-1.5 flex gap-2"><Check className="w-3.5 h-3.5 mt-0.5 shrink-0" /><div>{effects.join(" · ")}</div></div>}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <div className="inline-flex rounded-lg border border-border overflow-hidden text-xs">
            <button onClick={() => setDir("in")} className={`px-3 py-1.5 inline-flex items-center gap-1 ${dir === "in" ? "bg-success/15" : "text-muted-foreground"}`}><ArrowDownLeft className="w-3 h-3" /> {t("Khách trả lời", "Customer replied")}</button>
            <button onClick={() => setDir("out")} className={`px-3 py-1.5 inline-flex items-center gap-1 ${dir === "out" ? "bg-primary/15" : "text-muted-foreground"}`}><ArrowUpRight className="w-3 h-3" /> {t("Tôi đã gửi", "I sent")}</button>
          </div>
          <select className={`${inputCls} text-xs py-1.5`} value={channel} onChange={(e) => setChannel(e.target.value)}><option value="zalo">Zalo</option><option value="email">Email</option><option value="call">{t("Điện thoại", "Phone")}</option></select>
          <span className="text-[11px] text-muted-foreground">{dir === "in" ? t("Dán nguyên văn tin khách nhắn — hệ thống tự phân loại ý định.", "Paste the customer's message — intent is classified automatically.") : t("Ghi lại tin bạn vừa gửi để tính nhịp theo dõi.", "Record what you sent to drive follow-ups.")}</span>
        </div>
        <div className="flex gap-2 items-end">
          <textarea className={`${inputCls} flex-1 min-h-[72px] text-sm`} value={text} onChange={(e) => setText(e.target.value)} placeholder={dir === "in" ? t("Nội dung khách phản hồi…", "Customer's reply…") : t("Nội dung bạn đã gửi…", "Message you sent…")} />
          <Btn kind="primary" disabled={!text.trim() || add.isPending} onClick={() => add.mutate()}><Send className="w-3.5 h-3.5" /> {t("Ghi nhận", "Log")}</Btn>
        </div>
        <div className="mt-1"><ErrBox error={add.error ?? suggest.error ?? optout.error} /></div>
      </div>
    </div>
  );
}
