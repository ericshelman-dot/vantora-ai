import { Logo } from "@/components/brand/Logo";
import { DemoRequests } from "@/admin/DemoRequests";
import { SwitchToDemoButton } from "@/dashboard/DemoMode";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, Building2, TrendingUp, Users, LogOut, Save, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [plans, setPlans] = useState([]);

  const load = () => {
    api.get("/admin/stats").then(({ data }) => setStats(data)).catch(() => {});
    api.get("/admin/businesses").then(({ data }) => setBusinesses(data)).catch(() => {});
    api.get("/plans").then(({ data }) => setPlans(data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const setStatus = async (bid, status) => {
    await api.put(`/admin/businesses/${bid}/status`, { subscription_status: status });
    toast.success("Subscription status updated"); load();
  };
  const savePlan = async (p) => {
    await api.put(`/admin/plans/${p.plan_id}`, { name: p.name, setup_fee: Number(p.setup_fee), monthly_fee: Number(p.monthly_fee), features: p.features });
    toast.success(`${p.name} pricing saved`);
  };

  const cards = [
    { label: "Total Businesses", value: stats?.total_businesses, icon: Building2 },
    { label: "Active Subscriptions", value: stats?.active_subscriptions, icon: Users },
    { label: "Trialing", value: stats?.trialing, icon: Users },
    { label: "Estimated MRR", value: stats ? `$${stats.estimated_mrr.toLocaleString()}` : "—", icon: TrendingUp },
  ];

  return (
    <div className="min-h-screen bg-[#0B0D12] text-slate-100">
      <header className="glass h-20 flex items-center justify-between px-4 sm:px-8 sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Logo size="xl" sub="Console" />
          <span className="ml-2 px-2.5 py-1 rounded-full text-[11px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">ADMIN</span>
        </div>
        <div className="flex items-center gap-3">
          <SwitchToDemoButton />
          <Link to="/dashboard" className="hidden sm:flex text-sm text-slate-400 hover:text-gold items-center gap-1"><ArrowLeft className="w-4 h-4" /> Console</Link>
          <Button data-testid="admin-logout-button" onClick={() => { logout(); navigate("/"); }} variant="outline" className="bg-transparent border-amber-500/20 text-slate-300 hover:bg-red-500/10 hover:text-red-400 rounded-full h-9"><LogOut className="w-4 h-4 mr-2" /> Sign Out</Button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-4 sm:p-8">
        <div className="mb-8">
          <p className="text-xs uppercase tracking-[0.25em] text-gold font-mono mb-2">Platform</p>
          <h1 className="font-serif text-3xl lg:text-4xl font-medium">Administrator Dashboard</h1>
          <p className="text-slate-400 text-sm mt-2">Manage subscribing businesses, plans, and billing across the platform.</p>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {cards.map((c) => (
            <div key={c.label} className="lux-card p-5" data-testid={`admin-stat-${c.label.toLowerCase().replace(/ /g,'-')}`}>
              <c.icon className="w-5 h-5 text-gold mb-3" />
              <div className="font-serif text-3xl gold-gradient-text">{c.value ?? "—"}</div>
              <div className="text-sm text-slate-400 mt-1">{c.label}</div>
            </div>
          ))}
        </div>
        {stats && <p data-testid="admin-stats-demo-note" className="text-xs text-slate-500 -mt-7 mb-10">Revenue and subscription metrics exclude {stats.demo_workspaces} demo workspace(s).</p>}
        <div className="grid md:grid-cols-3 gap-5 mb-10">
          {plans.map((p, i) => (
            <PlanEditor key={p.plan_id} plan={p} onSave={savePlan} index={i} />
          ))}
        </div>

        <h2 className="font-display text-xl font-semibold mb-4">Subscribing Businesses</h2>
        <div className="lux-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-amber-500/15 text-left text-slate-400 font-display">
                <th className="px-5 py-3">Business</th><th className="px-5 py-3">Owner</th><th className="px-5 py-3">Leads</th><th className="px-5 py-3">Bookings</th><th className="px-5 py-3">Status</th>
              </tr></thead>
              <tbody>
                {businesses.map((b) => (
                  <tr key={b.business_id} className="border-b border-amber-500/10" data-testid={`admin-business-row-${b.business_id}`}>
                    <td className="px-5 py-4 font-medium text-amber-100">{b.name}{b.is_demo && <span data-testid={`admin-demo-badge-${b.business_id}`} className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-widest bg-gold text-[#0B0D12]">DEMO</span>}</td>
                    <td className="px-5 py-4 text-slate-400">{b.owner_name}<div className="text-xs text-slate-600">{b.owner_email}</div></td>
                    <td className="px-5 py-4 text-slate-300">{b.leads_count}</td>
                    <td className="px-5 py-4 text-slate-300">{b.bookings_count}</td>
                    <td className="px-5 py-4">
                      <Select value={b.subscription_status} onValueChange={(v) => setStatus(b.business_id, v)}>
                        <SelectTrigger data-testid={`admin-status-select-${b.business_id}`} className="w-36 bg-[#171A21] border-amber-500/20 h-9"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#171A21] border-amber-500/20 text-slate-100">
                          <SelectItem value="trialing">Trialing</SelectItem>
                          <SelectItem value="active">Active</SelectItem>
                          <SelectItem value="past_due">Past Due</SelectItem>
                          <SelectItem value="canceled">Canceled</SelectItem>
                        </SelectContent>
                      </Select>
                    </td>
                  </tr>
                ))}
                {businesses.length === 0 && <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-500">No businesses yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <DemoRequests />
      </main>
    </div>
  );
}

function PlanEditor({ plan, onSave, index }) {
  const [p, setP] = useState(plan);
  useEffect(() => { setP(plan); }, [plan]);
  return (
    <div className="lux-card p-5" data-testid={`admin-plan-editor-${index}`}>
      <Input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} className="bg-[#171A21] border-amber-500/20 font-display font-semibold mb-3" />
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div><Label className="text-xs text-slate-400">Setup fee</Label><Input data-testid={`admin-plan-setup-${index}`} type="number" value={p.setup_fee} onChange={(e) => setP({ ...p, setup_fee: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
        <div><Label className="text-xs text-slate-400">Monthly</Label><Input data-testid={`admin-plan-monthly-${index}`} type="number" value={p.monthly_fee} onChange={(e) => setP({ ...p, monthly_fee: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
      </div>
      <Button data-testid={`admin-plan-save-${index}`} onClick={() => onSave(p)} className="w-full bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-9"><Save className="w-4 h-4 mr-2" /> Save Pricing</Button>
    </div>
  );
}
