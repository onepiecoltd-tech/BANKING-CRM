import { Link, Outlet, useLocation } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Sparkles,
  Users,
  Send,
  MessagesSquare,
  Network,
  BarChart3,
  Settings,
  Search,
  Bell,
  Command,
  Rocket,
  Building2,
  User,
  Briefcase,
  Kanban,
  Languages,
  FileUp,
  ShieldCheck,
  UserCog,
  UserCheck,
  LogOut,
  KeyRound,
  ChevronDown,
  Menu,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { t, useI18n } from "@/lib/i18n";
import { useAuth, ChangePassword } from "@/lib/auth";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; badge?: string; adminOnly?: boolean };

function retailNav(): NavItem[] {
  return [
    { to: "/", label: t("Dashboard"), icon: LayoutDashboard },
    { to: "/workspace", label: t("RM AI Workspace"), icon: Sparkles, badge: "AI" },
    { to: "/customers", label: t("Customer Intelligence"), icon: Users },
    { to: "/outreach", label: t("Outreach Center"), icon: Send },
    { to: "/campaign", label: t("Campaign Builder"), icon: Rocket, badge: "NEW" },
    { to: "/conversations", label: t("Conversation Console"), icon: MessagesSquare },
    { to: "/reasoning", label: t("Reasoning & Trace"), icon: Network },
    { to: "/analytics", label: t("Analytics"), icon: BarChart3 },
    { to: "/settings", label: t("Admin & Settings"), icon: Settings, adminOnly: true },
  ];
}

function corpNav(): NavItem[] {
  return [
    { to: "/corp", label: t("Tổng quan DN", "Corporate overview"), icon: LayoutDashboard },
    { to: "/corp/customers", label: t("Khách hàng doanh nghiệp", "Corporate customers"), icon: Building2 },
    { to: "/corp/pipeline", label: t("Pipeline cơ hội", "Opportunity pipeline"), icon: Kanban },
    { to: "/corp/agent", label: t("Trợ lý AI cho RM", "RM AI assistant"), icon: Sparkles, badge: "AI" },
    { to: "/corp/outreach", label: t("Trung tâm tiếp cận", "Outreach center"), icon: Send },
    { to: "/corp/campaigns", label: t("Chiến dịch", "Campaigns"), icon: Rocket },
    { to: "/corp/conversations", label: t("Hội thoại khách hàng", "Conversations"), icon: MessagesSquare },
    { to: "/corp/reasoning", label: t("Lập luận & truy vết", "Reasoning & trace"), icon: Network },
    { to: "/corp/analytics", label: t("Phân tích số liệu", "Analytics"), icon: BarChart3 },
    { to: "/corp/import", label: t("Import dữ liệu", "Data import"), icon: FileUp },
    { to: "/corp/settings", label: t("Quản trị & Cài đặt", "Admin & settings"), icon: Settings, adminOnly: true },
  ];
}

function adminNav(): NavItem[] {
  return [
    { to: "/admin/users", label: t("Người dùng & phân quyền", "Users & roles"), icon: UserCog, adminOnly: true },
    { to: "/admin/assign", label: t("Phân công KH ↔ CBBH", "Assign customers ↔ RMs"), icon: UserCheck, adminOnly: true },
  ];
}

export function AppLayout() {
  const location = useLocation();
  const { lang, setLang } = useI18n();
  const corp = location.pathname === "/corp" || location.pathname.startsWith("/corp/");
  const { user, isAdmin, logout } = useAuth();
  const [menu, setMenu] = useState(false);
  const [pw, setPw] = useState(false);
  const [drawer, setDrawer] = useState(false);
  useEffect(() => { setDrawer(false); }, [location.pathname]);
  const NAV = (corp ? corpNav() : retailNav()).filter((i) => isAdmin || !i.adminOnly);
  const ADMIN = isAdmin ? adminNav() : [];
  const initials = (user?.full_name ?? "?").split(/\s+/).slice(-2).map((w) => w[0]?.toUpperCase()).join("");

  const renderItem = (item: NavItem, prefix = "nav") => {
    const active = location.pathname === item.to;
    const Icon = item.icon;
    return (
      <Link
        key={item.to}
        to={item.to as any}
        className={`group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${
          active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/60"
        }`}
      >
        {active && <motion.span layoutId={`${prefix}-indicator`} className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r gradient-primary" />}
        <Icon className={`w-4 h-4 ${active ? "text-primary" : "text-muted-foreground group-hover:text-foreground"}`} />
        <span className="flex-1">{item.label}</span>
        {item.badge && <span className="text-[9px] px-1.5 py-0.5 rounded-full gradient-primary text-primary-foreground font-semibold">{item.badge}</span>}
      </Link>
    );
  };

  const sidebarBody = (prefix: string) => (
    <>
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-sidebar-border">
          <div className="relative w-8 h-8 rounded-lg gradient-primary grid place-items-center shadow-glow">
            <span className="font-display font-bold text-primary-foreground text-sm">B</span>
          </div>
          <div className="leading-tight">
            <div className="font-display font-semibold text-sm">BankingRM</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{corp ? t("CRM Doanh nghiệp", "Corporate CRM") : "Agentic CRM"}</div>
          </div>
        </div>

        <div className="px-3 pt-3">
          <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-muted/40 border border-border">
            <Link
              to="/"
              className={`flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition ${!corp ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
            >
              <User className="w-3.5 h-3.5" /> {t("Cá nhân", "Retail")}
            </Link>
            <Link
              to="/corp"
              className={`flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition ${corp ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
            >
              <Briefcase className="w-3.5 h-3.5" /> {t("Doanh nghiệp", "Corporate")}
            </Link>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          <div className="px-2 pb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {t("Không gian làm việc", "Workspace")}
          </div>
          {NAV.map((item) => renderItem(item, prefix))}
          {ADMIN.length > 0 && (
            <>
              <div className="px-2 pt-4 pb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <ShieldCheck className="w-3 h-3" /> {t("Quản trị hệ thống", "System admin")}
              </div>
              {ADMIN.map((item) => renderItem(item, prefix))}
            </>
          )}
        </nav>

        <div className="px-3 py-3 border-t border-sidebar-border">
          <div className="glass rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-2 h-2 rounded-full bg-success pulse-dot" />
              <span className="text-xs font-medium">{t("Agent Online")}</span>
            </div>
            <div className="text-[10px] text-muted-foreground leading-relaxed">
              {t("Gemini 2.0 Flash · LangGraph v0.2 · 16 tools registered")}
            </div>
          </div>
        </div>
          </>
  );

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-64 flex-col border-r border-sidebar-border bg-sidebar/80 backdrop-blur-xl sticky top-0 h-screen">
        {sidebarBody("nav")}
      </aside>

      {/* Ngăn điều hướng trên điện thoại / máy tính bảng */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
          <div className="absolute left-0 top-0 bottom-0 w-72 max-w-[85vw] flex flex-col border-r border-sidebar-border bg-sidebar shadow-card" style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}>
            <button onClick={() => setDrawer(false)} aria-label={t("Đóng menu", "Close menu")} className="absolute right-2 top-3 w-9 h-9 grid place-items-center rounded-lg hover:bg-muted/60 z-10">
              <X className="w-5 h-5" />
            </button>
            {sidebarBody("drawer")}
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 glass-strong border-b border-border flex items-center px-3 sm:px-6 gap-2 sm:gap-4">
          <button onClick={() => setDrawer(true)} aria-label={t("Mở menu", "Open menu")} className="lg:hidden w-10 h-10 shrink-0 grid place-items-center rounded-lg hover:bg-muted/60 transition">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1 max-w-xl">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                placeholder={t("Ask the agent or search customers, products, campaigns…")}
                className="w-full bg-input/60 border border-border rounded-lg pl-9 pr-20 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
              <kbd className="absolute right-2 top-1/2 -translate-y-1/2 hidden md:flex items-center gap-1 text-[10px] text-muted-foreground bg-muted/60 border border-border px-1.5 py-0.5 rounded">
                <Command className="w-2.5 h-2.5" /> K
              </kbd>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button className="hidden sm:grid relative w-9 h-9 place-items-center rounded-lg hover:bg-muted/60 transition">
              <Bell className="w-4 h-4 text-muted-foreground" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-accent" />
            </button>
            <button
              onClick={() => setLang(lang === "vi" ? "en" : "vi")}
              className="flex items-center gap-1.5 h-9 px-2.5 rounded-lg border border-border hover:bg-muted/60 transition text-xs font-medium"
              title={t("Đổi ngôn ngữ", "Switch language")}
            >
              <Languages className="w-4 h-4 text-muted-foreground" />
              <span className={lang === "vi" ? "text-foreground" : "text-muted-foreground"}>VI</span>
              <span className="text-muted-foreground">/</span>
              <span className={lang === "en" ? "text-foreground" : "text-muted-foreground"}>EN</span>
            </button>
            <div className="hidden sm:block h-6 w-px bg-border" />
            <div className="relative">
              <button onClick={() => setMenu((m) => !m)} className="flex items-center gap-2.5 rounded-lg hover:bg-muted/60 px-1.5 py-1 transition">
                <div className="w-8 h-8 rounded-full gradient-primary grid place-items-center text-xs font-semibold text-primary-foreground">{initials || "RM"}</div>
                <div className="hidden md:block leading-tight text-left">
                  <div className="text-xs font-medium">{user?.full_name}</div>
                  <div className="text-[10px] text-muted-foreground">{isAdmin ? t("Quản lý (Admin)", "Manager (Admin)") : t("Cán bộ nhân viên", "Staff")}</div>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground hidden md:block" />
              </button>
              {menu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setMenu(false)} />
                  <div className="absolute right-0 top-11 z-50 w-56 glass-strong rounded-xl border border-border shadow-card p-1.5 text-sm">
                    <div className="px-3 py-2 text-[11px] text-muted-foreground border-b border-border mb-1">@{user?.username}</div>
                    <button onClick={() => { setMenu(false); setPw(true); }} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted/60 text-left"><KeyRound className="w-4 h-4" /> {t("Đổi mật khẩu", "Change password")}</button>
                    <button onClick={() => { setMenu(false); logout(); }} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted/60 text-left text-destructive"><LogOut className="w-4 h-4" /> {t("Đăng xuất", "Sign out")}</button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1600px] w-full mx-auto" style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}>
          <Outlet />
        </main>
        {pw && <ChangePassword onDone={() => setPw(false)} onCancel={() => setPw(false)} />}
      </div>
    </div>
  );
}
