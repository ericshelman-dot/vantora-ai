import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Inbox } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";

export function DemoRequests() {
  const [items, setItems] = useState([]);
  const load = () => api.get("/admin/demo-requests").then(({ data }) => setItems(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const setStatus = async (id, status) => {
    await api.put(`/admin/demo-requests/${id}`, { status });
    toast.success("Request updated"); load();
  };

  return (
    <div className="mt-10" data-testid="admin-demo-requests">
      <h2 className="font-display text-xl font-semibold mb-1">Demo & Contact Requests</h2>
      <p className="text-xs text-slate-500 mb-4">Email alerts to the admin are simulated and logged — no email is actually sent.</p>
      <div className="lux-card divide-y divide-amber-500/10">
        {items.map((r) => (
          <div key={r.request_id} className="p-5 flex flex-col md:flex-row md:items-center gap-4" data-testid={`admin-demo-request-${r.request_id}`}>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-amber-100">{r.name}</span>
                <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-300">{r.kind}</span>
                <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border border-slate-500/30 text-slate-400">Alert: simulated</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">{r.email}{r.company && ` · ${r.company}`}{r.phone && ` · ${r.phone}`} · {new Date(r.created_at).toLocaleString()}</div>
              {r.message && <p className="text-sm text-slate-300 mt-2">{r.message}</p>}
            </div>
            <Select value={r.status} onValueChange={(v) => setStatus(r.request_id, v)}>
              <SelectTrigger data-testid={`admin-demo-status-${r.request_id}`} className="w-36 bg-[#171A21] border-amber-500/20 h-9"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#171A21] border-amber-500/20 text-slate-100">
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="contacted">Contacted</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ))}
        {items.length === 0 && <div className="p-10 text-center text-slate-500 text-sm flex flex-col items-center gap-2"><Inbox className="w-5 h-5" />No requests yet.</div>}
      </div>
    </div>
  );
}
