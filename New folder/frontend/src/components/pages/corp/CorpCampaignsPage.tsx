import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Rocket, Plus, Copy, Check, Send, Trash2, ChevronLeft, CheckCircle2, PlayCircle } from "lucide-react";
import { corpX, type CampaignRow, type CampaignTarget } from "@/lib/corpApiExt";
import { t } from "@/lib/i18n";
import { PageHeader, Card, Btn, ErrBox, Pill, Spinner, Stat, inputCls, fmtDateTime, copyText, LANG_LABEL, CHANNEL_LABEL } from "./shared";

const ST_TONE: Record<string, "muted" | "success" | "warning" | "destructive" | "primary"> = {
  "Chưa liên hệ": "muted", "Đã liên hệ": "primary", "Phản hồi": "warning", "Quan tâm": "success", "Chuyển đổi": "success", "Từ chối": "destructive",
};
const FW_SHORT: Record<string, string> = { consultative: "Tư vấn", aida: "AIDA", spin: "SPIN" };

function Bar({ c }: { c: CampaignRow }) {
  const parts: [string, string][] = [["Chuyển đổi", "bg-success"], ["Quan tâm", "bg-success/60"], ["Phản hồi", "bg-warning"], ["Từ chối", "bg-destructive/70"], ["Đã liên hệ", "bg-primary/70"], ["Chưa liên hệ", "bg-muted"]];
  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-muted/40">
      {parts.map(([k, cls]) => (c.counts[k] ? <div key={k} className={cls} style={{ width: `${(c.counts[k] / Math.max(c.total, 1)) * 100}%` }} title={`${k}: ${c.counts[k]}`} /> : null))}
    </div>
  );
}

export function CorpCampaignsPage({ openId }: { openId?: number }) {
  const nav = useNavigate();
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "campaigns"], queryFn: corpX.campaigns });
  if (openId) return <CampaignDetail id={openId} onBack={() => nav({ to: "/corp/campaigns", search: {} })} />;
  const items = data?.items ?? [];
  const active = items.filter((c) => c.status === "Đang chạy").length;
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Chiến dịch tiếp cận", "Outreach campaigns")}
        subtitle={t("Theo dõi từng đợt tiếp cận: bao nhiêu khách đã liên hệ, phản hồi, quan tâm, chuyển đổi.", "Track each outreach wave: contacted, replied, interested, converted.")}
        right={<Link to="/corp/outreach"><Btn kind="primary"><Plus className="w-3.5 h-3.5" /> {t("Tạo chiến dịch mới", "New campaign")}</Btn></Link>}
      />
      <ErrBox error={error} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label={t("Tổng chiến dịch", "Campaigns")} value={items.length} />
        <Stat label={t("Đang chạy", "Running")} value={active} tone="primary" />
        <Stat label={t("Khách hàng được tiếp cận", "Customers targeted")} value={items.reduce((a, c) => a + c.total, 0)} />
        <Stat label={t("Chuyển đổi", "Converted")} value={items.reduce((a, c) => a + (c.counts["Chuyển đổi"] ?? 0), 0)} tone="success" />
      </div>
      {isLoading ? <Spinner /> : items.length === 0 ? (
        <Card><div className="py-10 text-center text-sm text-muted-foreground"><Rocket className="w-8 h-8 mx-auto mb-2 text-primary/60" />{t("Chưa có chiến dịch. Vào Trung tâm tiếp cận để lọc tệp khách hàng và tạo chiến dịch đầu tiên.", "No campaigns yet. Use the Outreach center to build an audience and start one.")}</div></Card>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4">
          {items.map((c) => (
            <button key={c.id} onClick={() => nav({ to: "/corp/campaigns", search: { open: c.id } })} className="glass rounded-xl p-5 shadow-card text-left hover:border-primary/40 border border-transparent transition">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0"><div className="font-semibold truncate">{c.name}</div><div className="text-xs text-muted-foreground mt-0.5">{c.product_name} · {CHANNEL_LABEL(c.channel)} · {FW_SHORT[c.framework] ?? c.framework} · {c.owner_rm ?? c.owner}</div></div>
                <Pill tone={c.status === "Đang chạy" ? "primary" : "success"}>{c.status}</Pill>
              </div>
              <div className="mt-3"><Bar c={c} /></div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                {[[t("Mục tiêu", "Targets"), c.total], [t("Đã liên hệ", "Contacted"), `${c.contacted_pct}%`], [t("Phản hồi", "Replied"), `${c.reply_pct}%`], [t("Chuyển đổi", "Converted"), `${c.conv_pct}%`]].map(([l, v]) => (
                  <div key={String(l)}><div className="text-lg font-display font-semibold tabular-nums">{v}</div><div className="text-[10px] text-muted-foreground">{l}</div></div>
                ))}
              </div>
              <div className="text-[11px] text-muted-foreground mt-2">{fmtDateTime(c.created_at)}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CampaignDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["corp", "campaign", id], queryFn: () => corpX.campaign(id) });
  const [open, setOpen] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const refresh = () => { qc.invalidateQueries({ queryKey: ["corp"] }); };
  const setStatus = useMutation({ mutationFn: ({ tid, status }: { tid: number; status: string }) => corpX.setTarget(id, tid, status), onSuccess: refresh });
  const sent = useMutation({ mutationFn: (tid: number) => corpX.targetSent(id, tid), onSuccess: refresh });
  const setCamp = useMutation({ mutationFn: (s: string) => corpX.setCampaign(id, s), onSuccess: refresh });
  const del = useMutation({ mutationFn: () => corpX.deleteCampaign(id), onSuccess: () => { refresh(); onBack(); } });

  if (isLoading || !data) return <div className="space-y-4"><Btn onClick={onBack}><ChevronLeft className="w-3.5 h-3.5" /> {t("Quay lại", "Back")}</Btn>{error ? <ErrBox error={error} /> : <Spinner />}</div>;
  const { campaign: c, targets, statuses } = data;
  const rows = targets.filter((x) => !filter || x.status === filter);

  const copy = async (tg: CampaignTarget) => { await copyText((tg.subject ? tg.subject + "\n\n" : "") + tg.body); setCopied(tg.id); setTimeout(() => setCopied(null), 1500); };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <Btn onClick={onBack}><ChevronLeft className="w-3.5 h-3.5" /></Btn>
          <div className="min-w-0"><h1 className="text-xl font-display font-semibold truncate">{c.name}</h1><div className="text-xs text-muted-foreground">{c.product_name} · {CHANNEL_LABEL(c.channel)} · {FW_SHORT[c.framework] ?? c.framework} · {t("tạo bởi", "by")} {c.owner_rm ?? c.owner} · {fmtDateTime(c.created_at)}</div></div>
        </div>
        <div className="flex gap-2">
          <Pill tone={c.status === "Đang chạy" ? "primary" : "success"}>{c.status}</Pill>
          {c.status === "Đang chạy" ? <Btn onClick={() => setCamp.mutate("Hoàn tất")}><CheckCircle2 className="w-3.5 h-3.5" /> {t("Hoàn tất", "Complete")}</Btn> : <Btn onClick={() => setCamp.mutate("Đang chạy")}><PlayCircle className="w-3.5 h-3.5" /> {t("Mở lại", "Reopen")}</Btn>}
          <Btn kind="danger" onClick={() => { if (window.confirm(t("Xóa chiến dịch này? (Lịch sử tin nhắn đã ghi vẫn được giữ)", "Delete this campaign? (Logged messages are kept)"))) del.mutate(); }}><Trash2 className="w-3.5 h-3.5" /></Btn>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label={t("Mục tiêu", "Targets")} value={c.total} />
        <Stat label={t("Đã liên hệ", "Contacted")} value={`${c.contacted_pct}%`} />
        <Stat label={t("Tỷ lệ phản hồi", "Reply rate")} value={`${c.reply_pct}%`} tone="warning" />
        <Stat label={t("Quan tâm", "Interested")} value={`${c.interest_pct}%`} tone="success" />
        <Stat label={t("Chuyển đổi", "Converted")} value={`${c.conv_pct}%`} tone="success" />
      </div>
      <Bar c={c} />

      <Card title={t("Danh sách khách hàng", "Targets")} right={
        <select className={`${inputCls} text-xs py-1`} value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">{t("Mọi trạng thái", "All statuses")}</option>{statuses.map((s) => <option key={s} value={s}>{s} ({c.counts[s] ?? 0})</option>)}</select>
      }>
        <ErrBox error={setStatus.error ?? sent.error ?? setCamp.error ?? del.error} />
        <div className="divide-y divide-border/60">
          {rows.map((tg) => (
            <div key={tg.id} className="py-2.5">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <button className="text-sm font-medium hover:underline text-left truncate max-w-full" onClick={() => setOpen(open === tg.id ? null : tg.id)}>{tg.name}</button>
                  <div className="text-[11px] text-muted-foreground">{tg.customer_id} · {tg.industry} · {tg.contact_name ?? "—"} · {LANG_LABEL[tg.language] ?? tg.language}{tg.sent_at ? ` · ${t("gửi", "sent")} ${fmtDateTime(tg.sent_at)}` : ""}</div>
                </div>
                <Pill tone={ST_TONE[tg.status] ?? "muted"}>{tg.status}</Pill>
                {tg.status === "Chưa liên hệ" && <Btn disabled={sent.isPending} onClick={() => sent.mutate(tg.id)}><Send className="w-3.5 h-3.5" /> {t("Đã gửi", "Sent")}</Btn>}
                <select className={`${inputCls} text-xs py-1`} value={tg.status} onChange={(e) => setStatus.mutate({ tid: tg.id, status: e.target.value })}>{statuses.map((s) => <option key={s} value={s}>{s}</option>)}</select>
                <Link to="/corp/conversations" search={{ customer: tg.customer_id }}><Btn>{t("Hội thoại", "Chat")}</Btn></Link>
              </div>
              {open === tg.id && (
                <div className="mt-2 rounded-lg bg-muted/30 p-3">
                  {tg.subject && <div className="text-xs mb-1"><span className="text-muted-foreground">{t("Tiêu đề", "Subject")}:</span> {tg.subject}</div>}
                  <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{tg.body}</pre>
                  <div className="mt-2"><Btn onClick={() => copy(tg)}>{copied === tg.id ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />} {t("Sao chép", "Copy")}</Btn></div>
                </div>
              )}
            </div>
          ))}
          {rows.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("Không có khách hàng ở trạng thái này.", "No targets in this status.")}</div>}
        </div>
      </Card>
    </div>
  );
}
