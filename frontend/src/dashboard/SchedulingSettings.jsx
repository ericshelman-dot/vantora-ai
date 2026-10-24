import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const DAYS = [["mon", "Mon"], ["tue", "Tue"], ["wed", "Wed"], ["thu", "Thu"], ["fri", "Fri"], ["sat", "Sat"], ["sun", "Sun"]];
const ZONES = ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Kolkata", "Asia/Dubai", "Australia/Sydney", "UTC"];
const DEFAULT = { timezone: "America/New_York", capacity: 1, slot_minutes: 30, default_duration: 60,
  weekly: { mon: ["09:00", "18:00"], tue: ["09:00", "18:00"], wed: ["09:00", "18:00"], thu: ["09:00", "18:00"], fri: ["09:00", "18:00"], sat: null, sun: null } };
const cls = "bg-[#171A21] border-amber-500/20 h-9";

export function SchedulingSettings() {
  const { business, setBusiness } = useAuth();
  const [cfg, setCfg] = useState(DEFAULT);
  const [catalog, setCatalog] = useState([]);
  useEffect(() => {
    if (!business) return;
    setCfg({ ...DEFAULT, ...(business.scheduling || {}), weekly: { ...DEFAULT.weekly, ...(business.scheduling?.weekly || {}) } });
    setCatalog(business.service_catalog || []);
  }, [business]);

  const setDay = (d, i, v) => setCfg({ ...cfg, weekly: { ...cfg.weekly, [d]: Object.assign([...(cfg.weekly[d] || ["09:00", "18:00"])], { [i]: v }) } });
  const toggleDay = (d) => setCfg({ ...cfg, weekly: { ...cfg.weekly, [d]: cfg.weekly[d] ? null : ["09:00", "18:00"] } });
  const setSvc = (i, k, v) => setCatalog(catalog.map((s, j) => (j === i ? { ...s, [k]: v } : s)));

  const save = async () => {
    try {
      const { data } = await api.put("/business", {
        scheduling: { ...cfg, capacity: Number(cfg.capacity), slot_minutes: Number(cfg.slot_minutes), default_duration: Number(cfg.default_duration) },
        service_catalog: catalog.filter((s) => s.name).map((s) => ({ ...s, duration_min: Number(s.duration_min) })),
      });
      setBusiness(data);
      toast.success("Scheduling saved");
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error((Array.isArray(d) ? d[0]?.msg : d || "Could not save scheduling").replace(/^Value error, /, ""));
    }
  };

  return (
    <div className="lux-card p-6 mt-8" data-testid="scheduling-settings">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2"><CalendarClock className="w-5 h-5 text-gold" /><h3 className="font-display text-lg font-semibold">Scheduling & Availability</h3></div>
        <Button data-testid="scheduling-save-button" onClick={save} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-9 px-5">Save Scheduling</Button>
      </div>
      <div className="grid sm:grid-cols-4 gap-4 mb-6">
        <div className="sm:col-span-2"><Label className="text-slate-300 text-xs">Time zone</Label>
          <select data-testid="scheduling-timezone-select" value={cfg.timezone} onChange={(e) => setCfg({ ...cfg, timezone: e.target.value })} className={`mt-1 w-full rounded-md border px-3 text-sm ${cls}`}>
            {[...new Set([cfg.timezone, ...ZONES])].map((z) => <option key={z} value={z}>{z}</option>)}
          </select></div>
        <div><Label className="text-slate-300 text-xs">Simultaneous appointments</Label><Input data-testid="scheduling-capacity-input" type="number" min={1} max={50} value={cfg.capacity} onChange={(e) => setCfg({ ...cfg, capacity: e.target.value })} className={`mt-1 ${cls}`} /></div>
        <div><Label className="text-slate-300 text-xs">Default duration (min)</Label><Input data-testid="scheduling-duration-input" type="number" min={5} value={cfg.default_duration} onChange={(e) => setCfg({ ...cfg, default_duration: e.target.value })} className={`mt-1 ${cls}`} /></div>
      </div>
      <Label className="text-slate-300 text-xs">Opening hours</Label>
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3 mt-2 mb-6">
        {DAYS.map(([d, l]) => (
          <div key={d} className="flex items-center gap-2 rounded-lg border border-amber-500/10 p-2" data-testid={`scheduling-day-${d}`}>
            <button type="button" onClick={() => toggleDay(d)} className={`w-12 text-xs rounded px-1 py-1 ${cfg.weekly[d] ? "bg-amber-500/15 text-gold" : "text-slate-600 line-through"}`}>{l}</button>
            {cfg.weekly[d] ? (<>
              <Input type="time" value={cfg.weekly[d][0]} onChange={(e) => setDay(d, 0, e.target.value)} className={`${cls} px-2 text-xs`} />
              <Input type="time" value={cfg.weekly[d][1]} onChange={(e) => setDay(d, 1, e.target.value)} className={`${cls} px-2 text-xs`} />
            </>) : <span className="text-xs text-slate-600">Closed</span>}
          </div>
        ))}
      </div>
      <Label className="text-slate-300 text-xs">Bookable services</Label>
      <div className="space-y-2 mt-2">
        {catalog.map((s, i) => (
          <div key={i} className="flex gap-2" data-testid={`scheduling-service-${i}`}>
            <Input value={s.name} onChange={(e) => setSvc(i, "name", e.target.value)} placeholder="Service name" className={cls} />
            <Input type="number" value={s.duration_min} onChange={(e) => setSvc(i, "duration_min", e.target.value)} className={`${cls} w-28`} />
            <Input value={s.price || ""} onChange={(e) => setSvc(i, "price", e.target.value)} placeholder="Price" className={`${cls} w-28`} />
            <Button variant="outline" onClick={() => setCatalog(catalog.filter((_, j) => j !== i))} className="bg-transparent border-red-500/20 text-red-400 h-9"><Trash2 className="w-4 h-4" /></Button>
          </div>
        ))}
        <Button data-testid="scheduling-add-service" variant="outline" onClick={() => setCatalog([...catalog, { name: "", duration_min: 60, price: "" }])} className="bg-transparent border-amber-500/20 text-slate-300 h-9"><Plus className="w-4 h-4 mr-1" />Add service</Button>
      </div>
    </div>
  );
}
