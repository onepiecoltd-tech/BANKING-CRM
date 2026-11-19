import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { corpX, type AssignResult } from "@/lib/corpApiExt";
import { t } from "@/lib/i18n";
import { Modal, Btn, ErrBox, Spinner, inputCls, useRmOptions } from "./shared";

export type AssignSelection = { ids?: string[]; filters?: Record<string, string>; label: string };

/** Hộp thoại gán khách hàng cho CBBH: chọn người nhận, xem trước số lượng thay đổi, rồi xác nhận. */
export function AssignDialog({ selection, defaultTo, excludeRm, onClose, onDone }: {
  selection: AssignSelection; defaultTo?: string; excludeRm?: string; onClose: () => void; onDone?: (r: AssignResult, to: string) => void;
}) {
  const qc = useQueryClient();
  const opts = useRmOptions(true);
  const people = (opts.data?.accounts ?? []).filter((a) => a.is_active && a.rm_name !== excludeRm);
  const [to, setTo] = useState(defaultTo ?? "");
  const body = { customer_ids: selection.ids, filters: selection.filters };
  const preview = useQuery({
    queryKey: ["corp", "assign-preview", to, JSON.stringify(body)],
    enabled: !!to,
    queryFn: () => corpX.assign({ ...body, to_rm: to, dry_run: true }),
  });
  const run = useMutation({
    mutationFn: () => corpX.assign({ ...body, to_rm: to }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["corp"] }); qc.invalidateQueries({ queryKey: ["admin"] }); onDone?.(r, to); onClose(); },
  });
  const p = preview.data;
  return (
    <Modal title={t("Gán khách hàng cho CBBH", "Assign customers to RM")} onClose={onClose}
      footer={<>
        <Btn onClick={onClose}>{t("Hủy", "Cancel")}</Btn>
        <Btn kind="primary" disabled={!to || !p || p.moved === 0 || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? t("Đang gán…", "Assigning…") : p && p.moved > 0 ? t(`Gán ${p.moved} khách hàng`, `Assign ${p.moved} customers`) : t("Gán", "Assign")}
        </Btn>
      </>}>
      <div className="space-y-4">
        <div className="text-sm">{selection.label}</div>
        <label className="block text-xs text-muted-foreground">
          {t("Cán bộ bán hàng (CBBH) nhận", "Receiving RM")}
          <select className={`${inputCls} w-full mt-1 text-foreground`} value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">{t("— Chọn CBBH —", "— Select RM —")}</option>
            {people.map((a) => (
              <option key={a.username} value={a.rm_name}>{a.rm_name} ({a.username}) · {a.total} KH</option>
            ))}
          </select>
        </label>
        {opts.isLoading && <Spinner />}
        {!opts.isLoading && people.length === 0 && (
          <div className="text-xs text-warning">{t("Chưa có tài khoản nào để nhận. Tạo tài khoản nhân viên ở Quản trị → Người dùng trước.", "No active accounts. Create staff accounts under Admin → Users first.")}</div>
        )}
        {to && preview.isLoading && <div className="text-xs text-muted-foreground">{t("Đang tính…", "Calculating…")}</div>}
        {p && (
          <div className="rounded-lg bg-muted/40 px-3 py-2.5 text-xs space-y-1">
            <div>
              {p.matched === 0
                ? t("Không có khách hàng nào khớp.", "No matching customers.")
                : <>{t("Sẽ chuyển", "Will move")} <b className="text-foreground">{p.moved}</b> {t("khách hàng", "customers")}{p.already > 0 && <> · {p.already} {t("đã thuộc người này nên giữ nguyên", "already belong to this RM")}</>}.</>}
            </div>
            {p.from.length > 0 && (
              <div className="text-muted-foreground">
                {t("Đang thuộc:", "Currently with:")} {p.from.map((x) => `${x.rm_name || t("(chưa phân công)", "(unassigned)")} (${x.count})`).join(" · ")}
              </div>
            )}
            <div className="text-muted-foreground">{t("Có hiệu lực ngay: CBBH nhận thấy khách hàng này, người cũ không còn thấy. Có ghi nhật ký thao tác.", "Takes effect immediately; logged in the audit trail.")}</div>
          </div>
        )}
        <ErrBox error={preview.error ?? run.error} />
      </div>
    </Modal>
  );
}
