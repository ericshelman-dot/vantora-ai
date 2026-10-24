import { useEffect, useState } from "react";
import { Check, CreditCard, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, SimBadge } from "@/dashboard/parts";

export default function Billing() {
  const { business } = useAuth();
  const [plans, setPlans] = useState([]);
  useEffect(() => { api.get("/plans").then(({ data }) => setPlans(data)).catch(() => {}); }, []);

  const current = plans.find((p) => p.plan_id === business?.plan_id) || plans[0];
  const statusColor = business?.subscription_status === "active" ? "text-emerald-400" : "text-amber-300";

  return (
    <div>
      <PageHeader eyebrow="Account" title="Billing & Subscription" desc="Manage your Vantora AI plan. No real payments are processed — billing is simulated until a payment provider is connected." />
      <div className="lux-card p-6 mb-8">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-gold font-mono mb-1">Current Plan</div>
            <div className="font-serif text-3xl">{current?.name || "—"}</div>
            <div className="text-sm text-slate-400 mt-1">Status: <span className={statusColor}>{business?.subscription_status}</span> · Setup fee {business?.setup_fee_paid ? "paid" : "pending"}</div>
          </div>
          <div className="text-right">
            <div className="font-serif text-4xl gold-gradient-text">${current?.monthly_fee ?? "—"}<span className="text-base text-slate-500">/mo</span></div>
            <div className="text-xs text-slate-500">+ ${current?.setup_fee ?? "—"} setup</div>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-4"><Sparkles className="w-4 h-4 text-gold" /><h3 className="font-display text-lg font-semibold">Available Plans</h3><SimBadge text="payments simulated" /></div>
      <div className="grid md:grid-cols-3 gap-6">
        {plans.map((p, i) => {
          const isCurrent = p.plan_id === current?.plan_id;
          return (
            <div key={p.plan_id} className={`lux-card p-7 flex flex-col ${isCurrent ? "border-amber-500/50 gold-glow" : ""}`} data-testid={`billing-plan-${i}`}>
              <h3 className="font-display text-xl font-semibold text-amber-100">{p.name}</h3>
              <div className="mt-3 mb-1"><span className="font-serif text-4xl gold-gradient-text">${p.monthly_fee}</span><span className="text-slate-500">/mo</span></div>
              <div className="text-xs text-slate-500 mb-5">+ ${p.setup_fee} one-time setup</div>
              <ul className="space-y-2 flex-1 mb-5">
                {p.features.map((f) => <li key={f} className="flex items-start gap-2 text-sm text-slate-300"><Check className="w-4 h-4 text-gold mt-0.5 shrink-0" /> {f}</li>)}
              </ul>
              <Button data-testid={`billing-upgrade-plan-button-${i}`} disabled={isCurrent}
                onClick={() => toast.success(`Plan change to ${p.name} requested (simulated)`)}
                className={isCurrent ? "bg-transparent border border-amber-500/30 text-slate-400 rounded-full w-full" : "bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full w-full"}>
                <CreditCard className="w-4 h-4 mr-2" />{isCurrent ? "Current Plan" : "Switch Plan"}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
