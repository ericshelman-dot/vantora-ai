import { useEffect, useState } from "react";
import { Plus, Trash2, CalendarCheck, Clock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Empty } from "@/dashboard/parts";

// Interpret a "YYYY-MM-DDTHH:mm" wall-clock value in the business time zone and return UTC ISO.
function localToUtc(value, tz) {
  const guess = new Date(value + ":00Z");
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
    .formatToParts(guess).map((p) => [p.type, p.value]));
  const asTz = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
  return new Date(guess.getTime() - (asTz - guess.getTime())).toISOString();
}

export default function Appointments() {
  const { business } = useAuth();
  const tz = business?.scheduling?.timezone || "America/New_York";
  const capacity = business?.scheduling?.capacity || 1;
  const [bookings, setBookings] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_name: "", service: "", datetime: "", notes: "", status: "confirmed" });

  const load = () => api.get("/bookings").then(({ data }) => setBookings(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.customer_name || !form.service || !form.datetime) return toast.error("Fill all fields");
    try {
      await api.post("/bookings", { ...form, datetime: localToUtc(form.datetime, tz) });
      toast.success("Appointment booked");
      setOpen(false); setForm({ customer_name: "", service: "", datetime: "", notes: "", status: "confirmed" });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "No appointment was created. Please try again.");
    }
  };
  const del = async (id) => { await api.delete(`/bookings/${id}`); toast.success("Appointment cancelled"); load(); };

  const upcoming = bookings.filter((b) => new Date(b.datetime) >= new Date());
  const past = bookings.filter((b) => new Date(b.datetime) < new Date());

  const Row = ({ b }) => (
    <div className="lux-card p-5 flex items-center justify-between gap-4" data-testid={`booking-${b.booking_id}`}>
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col items-center justify-center text-gold">
          <CalendarCheck className="w-5 h-5" />
        </div>
        <div>
          <div className="font-display font-semibold text-amber-100 flex items-center gap-2">{b.customer_name}
            {b.source === "ai_chat" && <span data-testid={`booking-ai-badge-${b.booking_id}`} className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-300">AI chat</span>}
          </div>
          <div className="text-sm text-slate-400">{b.service}{b.duration_min ? ` · ${b.duration_min} min` : ""}</div>
          <div className="text-xs text-slate-500 font-mono flex items-center gap-1 mt-1"><Clock className="w-3 h-3" />{new Date(b.datetime).toLocaleString([], { dateStyle: "medium", timeStyle: "short", timeZone: tz })} <span className="text-slate-600">({tz})</span></div>
          <div className="text-[10px] text-slate-600 font-mono mt-0.5" data-testid={`booking-id-${b.booking_id}`}>{b.booking_id}</div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs px-2 py-0.5 rounded-full border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">{b.status}</span>
        <Button data-testid={`booking-delete-${b.booking_id}`} onClick={() => del(b.booking_id)} size="sm" variant="outline" className="bg-transparent border-red-500/20 text-red-400 hover:bg-red-500/10 rounded-full"><Trash2 className="w-4 h-4" /></Button>
      </div>
    </div>
  );

  return (
    <div>
      <PageHeader eyebrow="Calendar" title="Appointments" desc={`Bookings captured by your AI assistant and added manually. Times shown in ${tz}. Up to ${capacity} overlapping appointment(s) allowed.`}
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="add-booking-button" className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full px-6"><Plus className="w-4 h-4 mr-2" /> New Appointment</Button></DialogTrigger>
            <DialogContent className="bg-[#13161D] border-amber-500/20 text-slate-100">
              <DialogHeader><DialogTitle className="font-serif text-2xl">Book Appointment</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div><Label>Customer name</Label><Input data-testid="booking-customer-input" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                <div><Label>Service</Label><Input data-testid="booking-service-input" value={form.service} onChange={(e) => setForm({ ...form, service: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                <div><Label>Date & time <span className="text-slate-500 text-xs">({tz})</span></Label><Input data-testid="booking-datetime-input" type="datetime-local" value={form.datetime} onChange={(e) => setForm({ ...form, datetime: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
              </div>
              <DialogFooter><Button data-testid="appointment-schedule-confirm-button" onClick={add} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full">Confirm Booking</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        } />
      <h3 className="font-display text-lg font-semibold mb-4 text-amber-100">Upcoming</h3>
      {upcoming.length === 0 ? <Empty text="No upcoming appointments." /> : <div className="space-y-3 mb-8">{upcoming.map((b) => <Row key={b.booking_id} b={b} />)}</div>}
      {past.length > 0 && <><h3 className="font-display text-lg font-semibold mb-4 mt-8 text-slate-400">Past</h3><div className="space-y-3 opacity-60">{past.map((b) => <Row key={b.booking_id} b={b} />)}</div></>}
    </div>
  );
}
