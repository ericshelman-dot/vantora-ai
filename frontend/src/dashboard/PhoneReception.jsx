import { useEffect, useState } from "react";
import { PhoneCall, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { PageHeader, SimBadge, Empty } from "@/dashboard/parts";

export default function PhoneReception() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = () => api.get("/call-logs").then(({ data }) => setCalls(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const simulate = async () => {
    setLoading(true);
    try {
      await api.post("/call-logs/simulate");
      toast.success("Simulated inbound call handled by AI");
      load();
    } catch { toast.error("Could not simulate call"); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Reception" title="AI Phone Reception"
        desc="Your AI receptionist answers inbound calls 24/7, books appointments, and captures caller details."
        action={<Button data-testid="simulate-call-button" onClick={simulate} disabled={loading} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full px-6"><Play className="w-4 h-4 mr-2" />{loading ? "Connecting…" : "Simulate Inbound Call"}</Button>} />
      <div className="lux-card p-5 mb-6 flex items-center gap-4">
        <span className="w-3 h-3 rounded-full bg-emerald-500 pulse-live" />
        <div className="flex-1"><div className="font-display font-semibold text-emerald-400">AI Phone Reception: Active</div><div className="text-xs text-slate-500">Answering on your behalf, around the clock.</div></div>
        <SimBadge text="Phone calls simulated in demo" />
      </div>
      {calls.length === 0 ? <Empty text="No calls yet. Simulate an inbound call to see your AI receptionist in action." /> : (
        <div className="space-y-4">
          {calls.map((c) => (
            <div key={c.call_id} className="lux-card p-6" data-testid={`call-log-${c.call_id}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3"><div className="w-9 h-9 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center"><PhoneCall className="w-4 h-4 text-gold" /></div><div><div className="font-medium text-sm">{c.caller}</div><div className="text-xs text-slate-500 font-mono">{new Date(c.created_at).toLocaleString()}</div></div></div>
                <SimBadge />
              </div>
              {c.summary && <div className="text-sm text-amber-100 mb-3 font-display">Summary: {c.summary}</div>}
              <pre className="text-sm text-slate-400 whitespace-pre-wrap leading-relaxed font-sans bg-black/20 rounded-lg p-4 border border-amber-500/10">{c.transcript}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
