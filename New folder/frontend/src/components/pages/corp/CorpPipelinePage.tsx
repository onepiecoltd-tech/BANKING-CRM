import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { corp } from "@/lib/corpApi";
import { t, fmtBn } from "@/lib/i18n";
import { PageHeader, fmtDate } from "./shared";

const STAGE_EN: Record<string, string> = {
  "Tiếp cận": "Prospecting", "Đang tư vấn": "Advising", "Thẩm định": "Appraisal", "Trình duyệt": "Approval", "Triển khai": "Execution", "Thất bại": "Lost",
};

export function CorpPipelinePage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["corp", "opps"], queryFn: corp.opportunities, staleTime: 15_000 });
  const move = useMutation({
    mutationFn: ({ id, stage }: { id: number; stage: string }) => corp.patchOpp(id, { stage }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["corp", "opps"] }); qc.invalidateQueries({ queryKey: ["corp", "kpis"] }); },
  });
  if (!data) return <div className="text-sm text-muted-foreground">{t("Đang tải…", "Loading…")}</div>;
  const stages = data.stages;
  const active = stages.slice(0, 5);
  const total = active.reduce((s, k) => s + (data.totals[k] ?? 0), 0);

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Pipeline cơ hội doanh nghiệp", "Corporate opportunity pipeline")}
        subtitle={`${t("Giá trị đang theo dõi", "Open value")}: ${fmtBn(total, 0)} · ${t("Dùng mũi tên để chuyển giai đoạn.", "Use the arrows to move a deal between stages.")}`}
      />
      <div className="grid gap-3 overflow-x-auto pb-2" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(230px, 1fr))` }}>
        {stages.map((st, si) => (
          <div key={st} className="rounded-xl bg-muted/20 border border-border p-3 min-h-[300px]">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-semibold">{t(st, STAGE_EN[st])} <span className="text-muted-foreground font-normal">({data.by_stage[st]?.length ?? 0})</span></div>
              <div className="text-[11px] text-muted-foreground">{fmtBn(data.totals[st] ?? 0, 0)}</div>
            </div>
            <div className="space-y-2">
              {(data.by_stage[st] ?? []).map((o) => (
                <div key={o.id} className="glass rounded-lg p-3 text-xs space-y-1.5">
                  <Link to="/corp/customers" search={{ open: o.customer_id }} className="font-medium text-[13px] leading-snug hover:text-primary block">{o.customer_name}</Link>
                  <div className="text-muted-foreground">{o.product_name}</div>
                  <div className="flex justify-between"><span className="font-semibold">{fmtBn(o.expected_amount_bn, 1)}</span><span className="text-muted-foreground">{o.probability}%</span></div>
                  {o.next_action && <div className="text-muted-foreground">→ {o.next_action}{o.due_date ? ` · ${fmtDate(o.due_date)}` : ""}</div>}
                  <div className="flex justify-between pt-1">
                    <button disabled={si === 0 || move.isPending} onClick={() => move.mutate({ id: o.id, stage: stages[si - 1] })} className="p-1 rounded hover:bg-muted/60 disabled:opacity-30"><ChevronLeft className="w-4 h-4" /></button>
                    <button disabled={si === stages.length - 1 || move.isPending} onClick={() => move.mutate({ id: o.id, stage: stages[si + 1] })} className="p-1 rounded hover:bg-muted/60 disabled:opacity-30"><ChevronRight className="w-4 h-4" /></button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
