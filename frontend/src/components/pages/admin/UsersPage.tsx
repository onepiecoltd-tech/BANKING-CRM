import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, KeyRound, ShieldCheck, UserCog, Lock, Unlock, ScrollText } from "lucide-react";
import { accountsApi, type UserRow } from "@/lib/corpApiExt";
import { useAuth } from "@/lib/auth";
import { t } from "@/lib/i18n";
import { PageHeader, Card, Btn, ErrBox, Pill, Modal, Spinner, inputCls, fmtDateTime } from "@/components/pages/corp/shared";

function genPassword() {
  const a = "abcdefghijkmnpqrstuvwxyz", b = "ABCDEFGHJKLMNPQRSTUVWXYZ", c = "23456789";
  const pick = (s: string, n: number) => Array.from(crypto.getRandomValues(new Uint32Array(n))).map((x) => s[x % s.length]).join("");
  return pick(a, 4) + pick(b, 3) + pick(c, 3) + "-" + pick(a, 2) + pick(c, 2);
}

export function UsersPage() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="glass rounded-xl p-10 text-center shadow-card">
        <div className="text-lg font-semibold">{t("Chỉ dành cho Admin (Quản lý)", "Admin (manager) only")}</div>
        <p className="text-sm text-muted-foreground mt-1">{t("Tài khoản của bạn không có quyền quản lý người dùng.", "Your account cannot manage users.")}</p>
      </div>
    );
  }
  return <UsersInner />;
}

function UsersInner() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"users" | "audit">("users");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [resetting, setResetting] = useState<UserRow | null>(null);
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: accountsApi.users });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin"] });
  const toggle = useMutation({ mutationFn: (u: UserRow) => accountsApi.patchUser(u.id, { is_active: !u.is_active }), onSuccess: refresh });
  const rows = users.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Người dùng & phân quyền", "Users & roles")}
        subtitle={t("Quản lý (Admin) tạo tài khoản cho cán bộ nhân viên. Nhân viên chỉ thấy và nhập khách hàng của chính mình; Admin thấy toàn bộ và có quyền duyệt, cài đặt, xóa.", "Admins create accounts for staff. Staff only see and enter their own customers; admins see everything and can approve, configure and delete.")}
        right={<Btn kind="primary" onClick={() => setCreating(true)}><UserPlus className="w-3.5 h-3.5" /> {t("Thêm người dùng", "Add user")}</Btn>}
      />

      <div className="grid md:grid-cols-2 gap-4">
        <div className="glass rounded-xl p-4 shadow-card">
          <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="w-4 h-4 text-primary" /> Admin ({t("Quản lý", "Manager")})</div>
          <ul className="mt-2 text-xs text-muted-foreground space-y-1 list-disc pl-4">
            <li>{t("Xem toàn bộ khách hàng, sửa/xóa/chuyển cán bộ phụ trách", "See all customers; edit, delete, reassign RM")}</li>
            <li>{t("Duyệt hoặc từ chối lô import của nhân viên", "Approve or reject staff imports")}</li>
            <li>{t("Tạo/khóa người dùng, đặt lại mật khẩu, xem nhật ký thao tác", "Manage users, reset passwords, view audit log")}</li>
            <li>{t("Cài đặt hệ thống, bật OCR đám mây, xóa dữ liệu mẫu", "System settings, cloud OCR, clear demo data")}</li>
          </ul>
        </div>
        <div className="glass rounded-xl p-4 shadow-card">
          <div className="flex items-center gap-2 text-sm font-semibold"><UserCog className="w-4 h-4 text-accent" /> {t("Nhân viên (CBQH)", "Staff (RM)")}</div>
          <ul className="mt-2 text-xs text-muted-foreground space-y-1 list-disc pl-4">
            <li>{t("Chỉ thấy khách hàng có 'Cán bộ phụ trách' trùng tên CBQH của mình", "Only sees customers whose RM matches their RM name")}</li>
            <li>{t("Thêm mới, sửa hồ sơ, ghi tương tác, soạn tin, tiếp cận khách hàng của mình", "Add, edit, log interactions, draft and reach out to own customers")}</li>
            <li>{t("Import Excel/PDF/OCR — lô import chờ quản lý duyệt (có thể tắt)", "Import Excel/PDF/OCR — batches wait for admin approval (configurable)")}</li>
            <li>{t("Không xóa khách hàng, không đổi cán bộ phụ trách, không vào Cài đặt", "Cannot delete, reassign or open settings")}</li>
          </ul>
        </div>
      </div>

      <div className="flex gap-1 border-b border-border">
        {([["users", t("Người dùng", "Users")], ["audit", t("Nhật ký thao tác", "Audit log")]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === k ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>{l}</button>
        ))}
      </div>

      {tab === "users" && (
        <Card>
          {users.isLoading ? <Spinner /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3 font-medium">{t("Tài khoản", "Account")}</th><th className="pr-3 font-medium">{t("Họ tên", "Name")}</th><th className="pr-3 font-medium">{t("Vai trò", "Role")}</th>
                  <th className="pr-3 font-medium">{t("Tên CBQH", "RM name")}</th><th className="pr-3 font-medium">{t("Đăng nhập gần nhất", "Last login")}</th><th className="pr-3 font-medium">{t("Trạng thái", "Status")}</th><th />
                </tr></thead>
                <tbody>
                  {rows.map((u) => (
                    <tr key={u.id} className="border-b border-border/60 hover:bg-muted/20">
                      <td className="py-2.5 pr-3 font-mono text-xs">{u.username}{u.id === me?.id && <span className="ml-1 text-muted-foreground">({t("bạn", "you")})</span>}</td>
                      <td className="pr-3">{u.full_name}</td>
                      <td className="pr-3"><Pill tone={u.role === "admin" ? "primary" : "muted"}>{u.role === "admin" ? "Admin" : t("Nhân viên", "Staff")}</Pill></td>
                      <td className="pr-3 text-muted-foreground">{u.rm_name ?? "—"}</td>
                      <td className="pr-3 text-xs text-muted-foreground whitespace-nowrap">{fmtDateTime(u.last_login)}</td>
                      <td className="pr-3">
                        {!u.is_active ? <Pill tone="destructive">{t("Đã khóa", "Disabled")}</Pill> : u.must_change_password ? <Pill tone="warning">{t("Chờ đổi mật khẩu", "Must change password")}</Pill> : <Pill tone="success">{t("Hoạt động", "Active")}</Pill>}
                      </td>
                      <td className="text-right whitespace-nowrap">
                        <div className="inline-flex gap-1">
                          <Btn onClick={() => setEditing(u)}>{t("Sửa", "Edit")}</Btn>
                          <Btn title={t("Đặt lại mật khẩu", "Reset password")} onClick={() => setResetting(u)}><KeyRound className="w-3.5 h-3.5" /></Btn>
                          {u.id !== me?.id && <Btn title={u.is_active ? t("Khóa tài khoản", "Disable") : t("Mở khóa", "Enable")} onClick={() => toggle.mutate(u)}>{u.is_active ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}</Btn>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-2"><ErrBox error={users.error ?? toggle.error} /></div>
        </Card>
      )}
      {tab === "audit" && <AuditPanel />}

      {creating && <UserDialog onClose={() => setCreating(false)} onDone={() => { setCreating(false); refresh(); }} />}
      {editing && <UserDialog user={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); refresh(); }} />}
      {resetting && <ResetDialog user={resetting} onClose={() => setResetting(null)} onDone={() => { setResetting(null); refresh(); }} />}
    </div>
  );
}

function UserDialog({ user, onClose, onDone }: { user?: UserRow; onClose: () => void; onDone: () => void }) {
  const [username, setUsername] = useState(user?.username ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [rm, setRm] = useState(user?.rm_name ?? "");
  const [role, setRole] = useState<string>(user?.role ?? "staff");
  const [pw, setPw] = useState(user ? "" : genPassword());
  const [created, setCreated] = useState<{ u: string; p: string } | null>(null);
  const m = useMutation({
    mutationFn: () => user
      ? accountsApi.patchUser(user.id, { full_name: fullName, role, rm_name: rm })
      : accountsApi.createUser({ username, full_name: fullName, role, rm_name: rm || fullName, password: pw }),
    onSuccess: () => { if (user) onDone(); else setCreated({ u: username.trim().toLowerCase(), p: pw }); },
  });
  if (created) {
    return (
      <Modal title={t("Đã tạo tài khoản", "Account created")} onClose={onDone} footer={<Btn kind="primary" onClick={onDone}>{t("Xong", "Done")}</Btn>}>
        <p className="text-sm">{t("Gửi thông tin này cho nhân viên. Họ sẽ phải đổi mật khẩu ở lần đăng nhập đầu tiên.", "Send these details to the staff member. They must change the password at first sign-in.")}</p>
        <div className="mt-3 rounded-lg bg-muted/40 p-3 font-mono text-sm space-y-1">
          <div>{t("Tài khoản", "Username")}: <b>{created.u}</b></div>
          <div>{t("Mật khẩu tạm", "Temporary password")}: <b>{created.p}</b></div>
        </div>
        <p className="text-[11px] text-warning mt-2">{t("Mật khẩu chỉ hiển thị một lần.", "The password is shown only once.")}</p>
      </Modal>
    );
  }
  const ok = (user || (username.trim().length >= 3 && pw.length >= 8)) && fullName.trim().length >= 2;
  return (
    <Modal title={user ? t("Sửa người dùng", "Edit user") : t("Thêm người dùng", "Add user")} onClose={onClose}
      footer={<><ErrBox error={m.error} /><Btn onClick={onClose}>{t("Hủy", "Cancel")}</Btn><Btn kind="primary" disabled={!ok || m.isPending} onClick={() => m.mutate()}>{t("Lưu", "Save")}</Btn></>}>
      <div className="grid grid-cols-2 gap-3">
        <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Tên đăng nhập", "Username")}</span>
          <input disabled={!!user} className={`${inputCls} w-full disabled:opacity-50`} value={username} onChange={(e) => setUsername(e.target.value)} placeholder="nguyen.van.a" /></label>
        <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Họ và tên", "Full name")}</span>
          <input className={`${inputCls} w-full`} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Nguyễn Văn A" /></label>
        <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Vai trò", "Role")}</span>
          <select className={`${inputCls} w-full`} value={role} onChange={(e) => setRole(e.target.value)}><option value="staff">{t("Nhân viên (nhập dữ liệu)", "Staff (data entry)")}</option><option value="admin">Admin ({t("Quản lý", "Manager")})</option></select></label>
        <label className="block"><span className="block text-[11px] text-muted-foreground mb-1">{t("Tên CBQH (khớp với 'Cán bộ phụ trách')", "RM name (matches 'Relationship manager')")}</span>
          <input className={`${inputCls} w-full`} value={rm} onChange={(e) => setRm(e.target.value)} placeholder={fullName || "Nguyễn Văn A"} /></label>
        {!user && (
          <label className="block col-span-2"><span className="block text-[11px] text-muted-foreground mb-1">{t("Mật khẩu tạm (≥ 8 ký tự, có chữ và số)", "Temporary password (≥ 8 chars, letters and digits)")}</span>
            <div className="flex gap-2"><input className={`${inputCls} flex-1 font-mono`} value={pw} onChange={(e) => setPw(e.target.value)} /><Btn onClick={() => setPw(genPassword())}>{t("Tạo ngẫu nhiên", "Generate")}</Btn></div></label>
        )}
      </div>
      {role === "admin" && <p className="text-[11px] text-warning mt-3">{t("Admin có toàn quyền như quản lý. Chỉ cấp cho người thật sự cần.", "Admins have full manager rights. Grant sparingly.")}</p>}
    </Modal>
  );
}

function ResetDialog({ user, onClose, onDone }: { user: UserRow; onClose: () => void; onDone: () => void }) {
  const [pw, setPw] = useState(genPassword());
  const [shown, setShown] = useState(false);
  const m = useMutation({ mutationFn: () => accountsApi.patchUser(user.id, { new_password: pw }), onSuccess: () => setShown(true) });
  return (
    <Modal title={`${t("Đặt lại mật khẩu", "Reset password")} — ${user.username}`} onClose={shown ? onDone : onClose}
      footer={shown ? <Btn kind="primary" onClick={onDone}>{t("Xong", "Done")}</Btn> : <><ErrBox error={m.error} /><Btn onClick={onClose}>{t("Hủy", "Cancel")}</Btn><Btn kind="primary" disabled={pw.length < 8 || m.isPending} onClick={() => m.mutate()}>{t("Đặt lại", "Reset")}</Btn></>}>
      {shown ? (
        <>
          <p className="text-sm">{t("Đã đặt lại. Mọi phiên đăng nhập cũ của người này bị đăng xuất.", "Password reset. All of this user's sessions were signed out.")}</p>
          <div className="mt-3 rounded-lg bg-muted/40 p-3 font-mono text-sm">{t("Mật khẩu tạm", "Temporary password")}: <b>{pw}</b></div>
        </>
      ) : (
        <div className="flex gap-2"><input className={`${inputCls} flex-1 font-mono`} value={pw} onChange={(e) => setPw(e.target.value)} /><Btn onClick={() => setPw(genPassword())}>{t("Tạo ngẫu nhiên", "Generate")}</Btn></div>
      )}
    </Modal>
  );
}

const ACTION_GROUPS: [string, string, string][] = [
  ["", "Tất cả", "All"], ["login", "Đăng nhập sai", "Failed sign-ins"], ["user", "Người dùng", "Users"], ["customer", "Khách hàng", "Customers"], ["import", "Import", "Import"], ["campaign", "Chiến dịch", "Campaigns"], ["outreach", "Tiếp cận", "Outreach"], ["settings", "Cài đặt", "Settings"],
];

function AuditPanel() {
  const [group, setGroup] = useState("");
  const [username, setUsername] = useState("");
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "audit", group, username], queryFn: () => accountsApi.audit({ limit: 200, action: group || undefined, username: username || undefined }) });
  return (
    <Card title={t("Nhật ký thao tác", "Audit log")} right={<ScrollText className="w-4 h-4 text-muted-foreground" />}>
      <div className="flex flex-wrap gap-2 mb-3">
        <select className={inputCls} value={group} onChange={(e) => setGroup(e.target.value)}>{ACTION_GROUPS.map(([v, vi, en]) => <option key={v} value={v}>{t(vi, en)}</option>)}</select>
        <input className={`${inputCls} w-40`} placeholder={t("Lọc theo tài khoản", "Filter by user")} value={username} onChange={(e) => setUsername(e.target.value.trim())} />
      </div>
      {isLoading ? <Spinner /> : (
        <div className="overflow-x-auto max-h-[28rem] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card"><tr className="text-left text-muted-foreground border-b border-border">
              <th className="py-2 pr-3 font-medium">{t("Thời gian", "Time")}</th><th className="pr-3 font-medium">{t("Tài khoản", "User")}</th><th className="pr-3 font-medium">{t("Hành động", "Action")}</th><th className="pr-3 font-medium">{t("Đối tượng", "Entity")}</th><th className="pr-3 font-medium">{t("Chi tiết", "Detail")}</th><th className="font-medium">IP</th>
            </tr></thead>
            <tbody>
              {(data?.items ?? []).map((e) => (
                <tr key={e.id} className="border-b border-border/50 align-top">
                  <td className="py-1.5 pr-3 whitespace-nowrap text-muted-foreground">{fmtDateTime(e.ts)}</td>
                  <td className="pr-3 whitespace-nowrap">{e.username ?? "—"}</td>
                  <td className="pr-3 font-mono whitespace-nowrap">{e.action}</td>
                  <td className="pr-3 whitespace-nowrap">{e.entity ? `${e.entity}${e.entity_id ? ` #${e.entity_id}` : ""}` : "—"}</td>
                  <td className="pr-3 max-w-[360px] break-words text-muted-foreground">{e.detail}</td>
                  <td className="text-muted-foreground">{e.ip}</td>
                </tr>
              ))}
              {(data?.items ?? []).length === 0 && <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">{t("Không có bản ghi.", "No records.")}</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-2"><ErrBox error={error} /></div>
    </Card>
  );
}
