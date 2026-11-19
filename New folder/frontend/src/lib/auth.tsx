import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Lock, User as UserIcon, KeyRound, ShieldCheck, Loader2, LogOut } from "lucide-react";
import { t } from "@/lib/i18n";

export type Role = "admin" | "staff";
export interface AuthUser { id: number; username: string; full_name: string; role: Role; rm_name: string | null; must_change_password: boolean }

const TOKEN_KEY = "crm-token";
export function getToken(): string | null {
  try { return typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null; } catch { return null; }
}
function setToken(tok: string | null) {
  try {
    if (tok) window.localStorage.setItem(TOKEN_KEY, tok); else window.localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable */ }
}

// ── Gắn token vào mọi request /api (kể cả các trang cũ gọi thẳng http://localhost:8000/api) ──
const API_RE = /^(https?:\/\/(localhost|127\.0\.0\.1):8000)?\/api\//;
const PUBLIC_RE = /\/api\/auth\/(login|setup|status)$/;
if (typeof window !== "undefined" && !(window as any).__crmFetchPatched) {
  (window as any).__crmFetchPatched = true;
  const orig = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    if (!API_RE.test(url)) return orig(input, init);
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    const tok = getToken();
    if (tok && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${tok}`);
    const res = await orig(input, { ...init, headers });
    if (res.status === 401 && !PUBLIC_RE.test(url.split("?")[0]) && tok) {
      setToken(null);
      window.dispatchEvent(new Event("crm-auth-expired"));
    }
    return res;
  };
}

async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

type Ctx = { user: AuthUser | null; isAdmin: boolean; logout: () => Promise<void>; refresh: () => Promise<void> };
const AuthCtx = createContext<Ctx>({ user: null, isAdmin: false, logout: async () => {}, refresh: async () => {} });
export const useAuth = () => useContext(AuthCtx);

type Phase = "loading" | "setup" | "login" | "authed" | "offline";

export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [phase, setPhase] = useState<Phase>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [needCode, setNeedCode] = useState(false);

  const boot = useCallback(async () => {
    try {
      const st = await api<{ initialized: boolean; setup_code_required?: boolean }>("/api/auth/status");
      setNeedCode(!!st.setup_code_required);
      if (!st.initialized) { setPhase("setup"); return; }
      if (getToken()) {
        try {
          const me = await api<AuthUser>("/api/auth/me");
          setUser(me); setPhase("authed"); return;
        } catch { setToken(null); }
      }
      setPhase("login");
    } catch {
      setPhase("offline");
    }
  }, []);

  useEffect(() => { boot(); }, [boot]);
  useEffect(() => {
    const h = () => { qc.clear(); setUser(null); setPhase("login"); };
    window.addEventListener("crm-auth-expired", h);
    return () => window.removeEventListener("crm-auth-expired", h);
  }, [qc]);

  const onAuthed = (token: string, u: AuthUser) => { setToken(token); qc.clear(); setUser(u); setPhase("authed"); };
  const logout = async () => {
    try { await api("/api/auth/logout", {}); } catch { /* ignore */ }
    setToken(null); qc.clear(); setUser(null); setPhase("login");
  };
  const refresh = async () => { try { setUser(await api<AuthUser>("/api/auth/me")); } catch { /* ignore */ } };

  if (phase === "loading") return <Centered><Loader2 className="w-6 h-6 animate-spin text-primary" /></Centered>;
  if (phase === "offline")
    return (
      <Centered>
        <div className="glass rounded-xl p-6 max-w-sm text-center space-y-3">
          <div className="text-sm font-semibold">{t("Không kết nối được máy chủ", "Cannot reach the server")}</div>
          <p className="text-xs text-muted-foreground">{t("Backend (cổng 8000) chưa chạy. Mở lại CRM.exe rồi tải lại trang.", "The backend (port 8000) is not running. Restart CRM.exe and reload.")}</p>
          <button onClick={() => { setPhase("loading"); boot(); }} className="text-xs px-3 py-1.5 rounded-lg gradient-primary text-primary-foreground font-medium">{t("Thử lại", "Retry")}</button>
        </div>
      </Centered>
    );
  if (phase === "setup") return <AuthCard mode="setup" needCode={needCode} onAuthed={onAuthed} />;
  if (phase === "login" || !user) return <AuthCard mode="login" onAuthed={onAuthed} />;
  if (user.must_change_password)
    return <ChangePassword forced onDone={async () => { await refresh(); }} onLogout={logout} />;
  return <AuthCtx.Provider value={{ user, isAdmin: user.role === "admin", logout, refresh }}>{children}</AuthCtx.Provider>;
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="min-h-screen grid place-items-center bg-background px-4">{children}</div>;
}

const inputCls = "w-full bg-input/60 border border-border rounded-lg pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40";

function Field({ icon: Icon, ...p }: { icon: React.ElementType } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
      <input {...p} className={inputCls} />
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center justify-center gap-2.5 mb-5">
      <div className="w-10 h-10 rounded-xl gradient-primary grid place-items-center shadow-glow">
        <span className="font-display font-bold text-primary-foreground">B</span>
      </div>
      <div className="leading-tight text-left">
        <div className="font-display font-semibold">BankingRM</div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">CRM Doanh nghiệp & Cá nhân</div>
      </div>
    </div>
  );
}

function AuthCard({ mode, needCode, onAuthed }: { mode: "login" | "setup"; needCode?: boolean; onAuthed: (token: string, u: AuthUser) => void }) {
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const setup = mode === "setup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (setup && password !== confirm) { setErr(t("Mật khẩu nhập lại không khớp", "Passwords do not match")); return; }
    setBusy(true);
    try {
      const r = await api<{ token: string; user: AuthUser }>(setup ? "/api/auth/setup" : "/api/auth/login",
        setup ? { username, full_name: fullName, password, setup_code: code } : { username, password });
      onAuthed(r.token, r.user);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <Centered>
      <form onSubmit={submit} className="glass rounded-2xl p-7 w-full max-w-sm shadow-card space-y-3">
        <Brand />
        <div className="text-center mb-2">
          <div className="text-base font-semibold">{setup ? t("Thiết lập lần đầu", "First-time setup") : t("Đăng nhập", "Sign in")}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {setup ? t("Tạo tài khoản Quản lý (Admin). Tài khoản này sẽ tạo và phân quyền cho cán bộ nhân viên.", "Create the manager (Admin) account. It will create and manage staff accounts.")
              : t("Dùng tài khoản do Quản lý cấp.", "Use the account issued by your manager.")}
          </p>
        </div>
        <Field icon={UserIcon} placeholder={t("Tên đăng nhập", "Username")} value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" required />
        {setup && <Field icon={ShieldCheck} placeholder={t("Họ và tên", "Full name")} value={fullName} onChange={(e) => setFullName(e.target.value)} required />}
        <Field icon={Lock} type="password" placeholder={t("Mật khẩu", "Password")} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={setup ? "new-password" : "current-password"} required />
        {setup && <Field icon={Lock} type="password" placeholder={t("Nhập lại mật khẩu", "Confirm password")} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />}
        {setup && needCode && <Field icon={ShieldCheck} placeholder={t("Mã thiết lập (CRM_SETUP_CODE trên máy chủ)", "Setup code (CRM_SETUP_CODE on the server)")} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" required />}
        {setup && <p className="text-[11px] text-muted-foreground">{t("Tối thiểu 8 ký tự, gồm cả chữ và số.", "At least 8 characters, letters and digits.")}</p>}
        {err && <div className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">{err}</div>}
        <button disabled={busy} className="w-full py-2.5 rounded-lg gradient-primary text-primary-foreground text-sm font-medium disabled:opacity-60 flex items-center justify-center gap-2">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} {setup ? t("Tạo tài khoản Admin", "Create Admin account") : t("Đăng nhập", "Sign in")}
        </button>
      </form>
    </Centered>
  );
}

export function ChangePassword({ forced, onDone, onLogout, onCancel }: { forced?: boolean; onDone: () => void; onLogout?: () => void; onCancel?: () => void }) {
  const [oldP, setOld] = useState("");
  const [newP, setNew] = useState("");
  const [conf, setConf] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (newP !== conf) { setErr(t("Mật khẩu nhập lại không khớp", "Passwords do not match")); return; }
    setBusy(true);
    try {
      await api("/api/auth/change-password", { old_password: oldP, new_password: newP });
      onDone();
    } catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  };
  const body = (
    <form onSubmit={submit} className="glass-strong rounded-2xl p-7 w-full max-w-sm shadow-card space-y-3">
      <div className="text-center mb-1">
        <KeyRound className="w-6 h-6 mx-auto text-primary mb-2" />
        <div className="text-base font-semibold">{forced ? t("Đặt mật khẩu mới", "Set a new password") : t("Đổi mật khẩu", "Change password")}</div>
        {forced && <p className="text-xs text-muted-foreground mt-1">{t("Đây là lần đăng nhập đầu (hoặc mật khẩu vừa được Quản lý đặt lại). Hãy đổi sang mật khẩu của riêng bạn.", "First sign-in or your password was reset. Please choose your own password.")}</p>}
      </div>
      <Field icon={Lock} type="password" placeholder={t("Mật khẩu hiện tại", "Current password")} value={oldP} onChange={(e) => setOld(e.target.value)} autoComplete="current-password" required />
      <Field icon={Lock} type="password" placeholder={t("Mật khẩu mới (≥ 8 ký tự, chữ + số)", "New password (≥ 8 chars, letters + digits)")} value={newP} onChange={(e) => setNew(e.target.value)} autoComplete="new-password" required />
      <Field icon={Lock} type="password" placeholder={t("Nhập lại mật khẩu mới", "Confirm new password")} value={conf} onChange={(e) => setConf(e.target.value)} autoComplete="new-password" required />
      {err && <div className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">{err}</div>}
      <div className="flex gap-2">
        <button disabled={busy} className="flex-1 py-2.5 rounded-lg gradient-primary text-primary-foreground text-sm font-medium disabled:opacity-60">{t("Lưu mật khẩu", "Save")}</button>
        {forced ? (
          <button type="button" onClick={onLogout} className="px-3 py-2.5 rounded-lg border border-border text-sm hover:bg-muted/60 flex items-center gap-1.5"><LogOut className="w-4 h-4" /></button>
        ) : (
          <button type="button" onClick={onCancel} className="px-4 py-2.5 rounded-lg border border-border text-sm hover:bg-muted/60">{t("Hủy", "Cancel")}</button>
        )}
      </div>
    </form>
  );
  return forced ? <Centered>{body}</Centered> : <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center px-4">{body}</div>;
}
