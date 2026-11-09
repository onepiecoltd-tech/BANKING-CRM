import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRightLeft, UserCheck, AlertTriangle } from "lucide-react";
import { corp } from "@/lib/corpApi";
import { corpX, NO_RM, type AssignResult } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { PageHeader, Card, Btn, Pill, Spinner, ErrBox, Stat, inputCls, useMeta } from "@/components/pages/corp/shared";
import { AssignDialog, type AssignSelection } from "@/components/pages/corp/AssignDialog";

export function AssignPage() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="glass rounded-xl p-10 text-center shadow-card">
        <div className="text-lg font-semibold">{t("Chỉ dành cho Admin (Quản lý)", "Admin (manager) only")}</div>
        <p className="text-sm text-muted-foreground mt-1">{t("Tài khoản của bạn không có quyền phân công khách hàng.", "Your account cannot assign customers.")}</p>
      </div>
    );
  }
  return <Inner />;
}

type Dlg = { selection: AssignSelection; defaultTo?: string; excludeRm?: string };
const EMPTY = { rm: "", lifecycle: "", province: "", industry: "", ownership: "", q: "" };

function Inner() {
  const sum = useQuery({ queryKey: ["admin", "assignment"], queryFn: corpX.assignment });
  const { data: meta } = useMeta();
  const [dlg, setDlg] = useState<Dlg | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [flt, setFlt] = useState(EMPTY);
  const active = Object.fromEntries(Object.entries(flt).filter(([, v]) => v)) as Record<string, string>;
  const hasFilter = Object.keys(active).length > 0;
  const match = useQuery({
    queryKey: ["corp", "assign-count", active],
    enabled: hasFilter,
    queryFn: () => corp.customers({ ...active, limit: 1 }),
  });
  const d = sum.data;
  const lcName = (c: string) => meta?.lifecycles?.find((x) => x.code === c)?.name ?? c;
  const label = (rm: string) => (rm === NO_RM ? t("(chưa phân công)", "(unassigned)") : rm);
  const describe = () => [
    flt.q && `“${flt.q}”`, flt.rm && `${t("đang thuộc", "with")} ${label(flt.rm)}`, flt.lifecycle && lcName(flt.lifecycle),
    flt.ownership, flt.province, flt.industry,
  ].filter(Boolean).join(" · ");
  const onDone = (r: AssignResult, to: string) => setDone(t(`Đã gán ${r.moved} khách hàng cho ${to}.`, `Assigned ${r.moved} customers to ${to}.`));
  const setF = (k: keyof typeof EMPTY) => (v: string) => setFlt((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Phân công khách hàng ↔ CBBH", "Assign customers ↔ RMs")}
        subtitle={t("CBBH (cán bộ bán hàng) chỉ thấy khách hàng đang gán cho tên của mình. Gán lại có hiệu lực ngay và được ghi vào nhật ký thao tác.", "Each RM only sees customers assigned to their name. Reassignment is immediate and audited.")}
      />
      {done && <div className="text-sm rounded-lg bg-success/10 text-success px-3 py-2">{done}</div>}
      <ErrBox error={sum.error} />
      {sum.isLoading && <Spinner />}

      {d && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat label={t("Tổng khách hàng", "Total customers")} value={d.total} />
            <Stat label={t("CBBH đang hoạt động", "Active RMs")} value={d.accounts.filter((a) => a.is_active).length} />
            <Stat label={t("Chưa phân công", "Unassigned")} value={d.unassigned.total} tone={d.unassigned.total ? "warning" : undefined} sub={t("chỉ Admin thấy", "only admins see these")} />
            <Stat label={t("Gán cho tên chưa có tài khoản", "Assigned to unknown names")} value={d.unmatched_total} tone={d.unmatched_total ? "warning" : undefined} sub={t("không CBBH nào thấy", "no RM can see these")} />
          </div>

          {(d.unassigned.total > 0 || d.unmatched.length > 0) && (
            <Card title={t("Cần xử lý", "Needs attention")}>
              <div className="flex items-start gap-2 text-xs text-muted-foreground mb-3">
                <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                {t("Các khách hàng dưới đây chưa thuộc về CBBH nào có tài khoản đang hoạt động, nên chỉ Admin nhìn thấy. Gán cho CBBH để họ bắt đầu chăm sóc.", "These customers belong to no active RM account, so only admins can see them. Assign them to an RM.")}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <th className="py-2 pr-3">{t("Đang ghi", "Currently")}</th><th className="pr-3 text-right">{t("Tổng", "Total")}</th><th className="pr-3 text-right">{t("KH mới", "New")}</th><th className="pr-3 text-right">{t("Hiện hữu", "Existing")}</th><th />
                  </tr></thead>
                  <tbody>
                    {d.unassigned.total > 0 && (
                      <Row name={<span className="font-medium">{t("(Chưa phân công)", "(Unassigned)")}</span>} load={d.unassigned}
                        action={<Btn onClick={() => setDlg({ selection: { filters: { rm: NO_RM }, label: t(`${d.unassigned.total} khách hàng chưa phân công`, `${d.unassigned.total} unassigned customers`) } })}><UserCheck className="w-3.5 h-3.5" /> {t("Gán cho…", "Assign to…")}</Btn>} />
                    )}
                    {d.unmatched.map((u) => (
                      <Row key={u.rm_name} name={<><span className="font-medium">{u.rm_name}</span> <Pill tone="warning">{u.inactive_user ? t(`tài khoản ${u.inactive_user} đã khóa`, `account ${u.inactive_user} locked`) : t("chưa có tài khoản", "no account")}</Pill></>} load={u}
                        action={<Btn onClick={() => setDlg({ selection: { filters: { rm: u.rm_name }, label: t(`Toàn bộ ${u.total} khách hàng đang ghi tên “${u.rm_name}”`, `All ${u.total} customers listed under “${u.rm_name}”`) } })}><UserCheck className="w-3.5 h-3.5" /> {t("Gán cho…", "Assign to…")}</Btn>} />
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <Card title={t("Khối lượng theo CBBH", "Workload by RM")}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">CBBH</th><th className="pr-3">{t("Vai trò", "Role")}</th><th className="pr-3 text-right">{t("Tổng", "Total")}</th><th className="pr-3 text-right">{t("KH mới", "New")}</th><th className="pr-3 text-right">{t("Hiện hữu", "Existing")}</th><th />
                </tr></thead>
                <tbody>
                  {d.accounts.map((a) => (
                    <Row key={a.username}
                      name={<>
                        <span className="font-medium">{a.full_name}</span> <span className="text-xs text-muted-foreground">@{a.username}</span>
                        {!a.is_active && <> <Pill tone="destructive">{t("đã khóa", "locked")}</Pill></>}
                        {a.rm_name !== a.full_name && <div className="text-[11px] text-muted-foreground">{t("Tên trên danh mục:", "Listed as:")} {a.rm_name}</div>}
                      </>}
                      extra={<td className="pr-3"><Pill tone={a.role === "admin" ? "primary" : "muted"}>{a.role === "admin" ? "Admin" : t("Nhân viên", "Staff")}</Pill></td>}
                      load={a}
                      action={a.total > 0 ? <Btn onClick={() => setDlg({ excludeRm: a.rm_name, selection: { filters: { rm: a.rm_name }, label: t(`Chuyển toàn bộ ${a.total} khách hàng của ${a.rm_name}`, `Move all ${a.total} customers of ${a.rm_name}`) } })}><ArrowRightLeft className="w-3.5 h-3.5" /> {t("Chuyển toàn bộ…", "Move all…")}</Btn> : null} />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">{t("Muốn chuyển từng khách hoặc chọn nhiều khách: vào Khách hàng, tick ô chọn rồi bấm “Gán cho CBBH”.", "To move individual customers, tick them on the Customers page and use “Assign to RM”.")}</p>
          </Card>

          <Card title={t("Gán theo điều kiện", "Assign by criteria")}>
            <p className="text-xs text-muted-foreground mb-3">{t("Ví dụ: toàn bộ KH mới ở Bình Dương gán cho một CBBH. Chọn ít nhất một điều kiện, hệ thống đếm số khách khớp rồi bạn xem trước và xác nhận.", "Example: all new customers in Binh Duong to one RM. Pick at least one criterion; you can preview before confirming.")}</p>
            <div className="flex flex-wrap gap-2 items-center">
              <input className={`${inputCls} w-52`} placeholder={t("Tên DN, MST, mã KH…", "Name, tax code, ID…")} value={flt.q} onChange={(e) => setF("q")(e.target.value)} />
              <Sel value={flt.rm} onChange={setF("rm")} ph={t("Đang thuộc (tất cả)", "Currently with (any)")} opts={[{ v: NO_RM, l: t("(Chưa phân công)", "(Unassigned)") }, ...(meta?.rm_names ?? []).map((x) => ({ v: x, l: x }))]} />
              <Sel value={flt.lifecycle} onChange={setF("lifecycle")} ph={t("Loại KH", "Lifecycle")} opts={(meta?.lifecycles ?? []).map((x) => ({ v: x.code, l: x.name }))} />
              <Sel value={flt.ownership} onChange={setF("ownership")} ph={t("Loại hình", "Ownership")} opts={[{ v: "FDI", l: "FDI" }, { v: "Nội địa", l: t("Nội địa", "Domestic") }]} />
              <Sel value={flt.province} onChange={setF("province")} ph={t("Tỉnh/TP", "Province")} opts={(meta?.provinces ?? []).map((x) => ({ v: x, l: x }))} />
              <Sel value={flt.industry} onChange={setF("industry")} ph={t("Ngành", "Industry")} opts={(meta?.industries ?? []).map((x) => ({ v: x, l: x }))} />
              {hasFilter && <button className="text-xs text-muted-foreground hover:text-foreground underline" onClick={() => setFlt(EMPTY)}>{t("Xóa điều kiện", "Clear")}</button>}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <Btn kind="primary" disabled={!hasFilter || !match.data?.total}
                onClick={() => setDlg({ selection: { filters: active, label: t(`${match.data?.total ?? 0} khách hàng khớp: ${describe()}`, `${match.data?.total ?? 0} matching customers: ${describe()}`) } })}>
                <UserCheck className="w-3.5 h-3.5" /> {t("Xem trước & gán…", "Preview & assign…")}
              </Btn>
              <span className="text-xs text-muted-foreground">{hasFilter ? (match.isLoading ? t("Đang đếm…", "Counting…") : t(`${match.data?.total ?? 0} khách hàng khớp`, `${match.data?.total ?? 0} matching`)) : t("Chưa chọn điều kiện", "No criteria yet")}</span>
            </div>
          </Card>
        </>
      )}
      {dlg && <AssignDialog {...dlg} onClose={() => setDlg(null)} onDone={onDone} />}
    </div>
  );
}

function Row({ name, load, action, extra }: { name: ReactNode; load: { total: number; prospect: number; existing: number }; action?: ReactNode; extra?: ReactNode }) {
  return (
    <tr className="border-b border-border/50">
      <td className="py-2.5 pr-3">{name}</td>
      {extra}
      <td className="pr-3 text-right tabular-nums font-semibold">{load.total}</td>
      <td className="pr-3 text-right tabular-nums">{load.prospect}</td>
      <td className="pr-3 text-right tabular-nums">{load.existing}</td>
      <td className="text-right">{action}</td>
    </tr>
  );
}

function Sel({ value, onChange, ph, opts }: { value: string; onChange: (v: string) => void; ph: string; opts: { v: string; l: string }[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={`${inputCls} max-w-[200px]`}>
      <option value="">{ph}</option>
      {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
    </select>
  );
}
