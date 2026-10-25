import { Logo } from "@/components/brand/Logo";
import { DemoBanner, SwitchToDemoButton } from "@/dashboard/DemoMode";
import { Outlet, NavLink, useNavigate, Link } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, PhoneCall, MessageSquare, Users, CalendarCheck, UserPlus,
  Settings as SettingsIcon, CreditCard, Sliders, LogOut, Sparkles, Menu, X, Shield, Bell
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

const nav = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, end: true, testid: "overview" },
  { to: "/dashboard/phone", label: "AI Phone Reception", icon: PhoneCall, testid: "phone" },
  { to: "/dashboard/chat", label: "Chat Assistant", icon: MessageSquare, testid: "chat" },
  { to: "/dashboard/leads", label: "Lead Follow-ups", icon: UserPlus, testid: "leads" },
  { to: "/dashboard/sales", label: "Sales & Marketing", icon: Sparkles, testid: "sales" },
  { to: "/dashboard/appointments", label: "Appointments", icon: CalendarCheck, testid: "appointments" },
  { to: "/dashboard/customers", label: "Customers", icon: Users, testid: "customers" },
  { to: "/dashboard/customization", label: "AI Customization", icon: Sliders, testid: "customization" },
  { to: "/dashboard/billing", label: "Billing", icon: CreditCard, testid: "billing" },
  { to: "/dashboard/settings", label: "Settings", icon: SettingsIcon, testid: "settings" },
];

export default function DashboardLayout() {
  const { user, business, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const SidebarInner = () => (
    <>
      <Link to="/" className="flex items-center gap-2 px-6 h-20 border-b border-amber-500/15">
        <Logo size="xl" sub="Console" />
      </Link>
      <div className="px-4 py-4">
        <div className="lux-card px-4 py-3">
          <div className="text-xs text-slate-500 font-mono uppercase tracking-wider flex items-center gap-2">Workspace{business?.is_demo && <span data-testid="sidebar-demo-badge" className="px-1.5 py-0.5 rounded bg-gold text-[#0B0D12] text-[9px] font-bold tracking-widest">DEMO</span>}</div>
          <div className="font-display font-semibold text-amber-100 truncate">{business?.name || "Platform Admin"}</div>
          {business ? (
            <div className="flex items-center gap-1.5 mt-1"><span className="w-2 h-2 rounded-full bg-emerald-500 pulse-live" /><span className="text-xs text-emerald-400">AI Active</span></div>
          ) : (
            <div data-testid="sidebar-no-workspace" className="text-xs text-slate-500 mt-1">No business workspace</div>
          )}
          {user?.role === "admin" && !user?.demo_mode && <SwitchToDemoButton className="w-full mt-3 h-8 text-xs" />}
        </div>
      </div>
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)} data-testid={`sidebar-${n.testid}-link`}
            className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-display transition-colors ${isActive ? "bg-amber-500/15 text-gold border border-amber-500/30" : "text-slate-400 hover:text-slate-100 hover:bg-white/5 border border-transparent"}`}>
            <n.icon className="w-4 h-4" /> {n.label}
          </NavLink>
        ))}
        {user?.role === "admin" && (
          <NavLink to="/admin" onClick={() => setOpen(false)} data-testid="sidebar-admin-link"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-display text-amber-300 hover:bg-amber-500/10">
            <Shield className="w-4 h-4" /> Admin Console
          </NavLink>
        )}
      </nav>
      <div className="p-4 border-t border-amber-500/15">
        <div className="flex items-center gap-3 mb-3 px-1">
          <div className="w-9 h-9 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-gold font-display font-semibold">{(user?.name || "U")[0]}</div>
          <div className="min-w-0"><div className="text-sm font-medium truncate">{user?.name}</div><div className="text-xs text-slate-500 truncate">{user?.email}</div></div>
        </div>
        <Button data-testid="logout-button" onClick={() => { logout(); navigate("/"); }} variant="outline" className="w-full bg-transparent border-amber-500/20 text-slate-300 hover:bg-red-500/10 hover:text-red-400 rounded-lg h-9 text-sm">
          <LogOut className="w-4 h-4 mr-2" /> Sign Out
        </Button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#0B0D12] text-slate-100 flex">
      <aside className="hidden lg:flex w-72 flex-col border-r border-amber-500/15 bg-[#0F1117] fixed inset-y-0">
        <SidebarInner />
      </aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="w-72 flex flex-col bg-[#0F1117] border-r border-amber-500/15"><SidebarInner /></div>
          <div className="flex-1 bg-black/60" onClick={() => setOpen(false)} />
        </div>
      )}
      <div className="flex-1 lg:ml-72">
        {business?.is_demo && <DemoBanner />}
        <header className="h-16 glass flex items-center justify-between px-4 sm:px-8 sticky top-0 z-40">
          <button className="lg:hidden text-slate-200" onClick={() => setOpen(true)} data-testid="dashboard-mobile-toggle"><Menu /></button>
          <div className="hidden lg:block text-sm text-slate-400 font-display">Business Command Center</div>
          <div className="flex items-center gap-4">
            <span className="hidden sm:inline-flex items-center gap-2 text-xs font-mono text-emerald-400"><span className="w-2 h-2 rounded-full bg-emerald-500 pulse-live" /> AI Online</span>
            <Bell className="w-5 h-5 text-slate-400" />
          </div>
        </header>
        <main className="p-4 sm:p-8 max-w-7xl mx-auto"><Outlet /></main>
      </div>
    </div>
  );
}
