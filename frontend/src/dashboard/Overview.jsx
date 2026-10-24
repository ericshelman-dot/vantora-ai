import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { UserPlus, CalendarCheck, Users, PhoneCall, MessageSquare, TrendingUp, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/dashboard/parts";

export default function Overview() {
  const { business } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [leads, setLeads] = useState([]);

  useEffect(() => {
    api.get("/stats").then(({ data }) => setStats(data)).catch(() => {});
    api.get("/bookings").then(({ data }) => setBookings(data.slice(0, 4))).catch(() => {});
    api.get("/leads").then(({ data }) => setLeads(data.slice(0, 4))).catch(() => {});
  }, []);

  const cards = [
    { label: "Total Leads", value: stats?.leads, icon: UserPlus, sub: `${stats?.new_leads || 0} new`, to: "/dashboard/leads" },
    { label: "Appointments", value: stats?.bookings, icon: CalendarCheck, sub: "upcoming", to: "/dashboard/appointments" },
    { label: "Customers", value: stats?.customers, icon: Users, sub: "records", to: "/dashboard/customers" },
    { label: "AI Calls", value: stats?.calls, icon: PhoneCall, sub: "handled", to: "/dashboard/phone" },
    { label: "Chat Messages", value: stats?.chats, icon: MessageSquare, sub: "from customers", to: "/dashboard/chat" },
  ];

  return (
    <div>
      <PageHeader eyebrow="Dashboard" title={`Welcome, ${business?.name || "there"}`} desc="Your AI assistant is answering calls, chatting with customers, and capturing leads — here's the pulse of your business." />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {cards.map((c, i) => (
          <motion.button key={c.label} onClick={() => navigate(c.to)} data-testid={`stat-${c.label.toLowerCase().replace(/ /g,'-')}`}
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
            className="lux-card p-5 text-left hover:scale-[1.02] transition-transform">
            <c.icon className="w-5 h-5 text-gold mb-3" />
            <div className="font-serif text-3xl gold-gradient-text">{c.value ?? "—"}</div>
            <div className="text-sm text-slate-300 mt-1">{c.label}</div>
            <div className="text-xs text-slate-500">{c.sub}</div>
          </motion.button>
        ))}
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="lux-card p-6">
          <div className="flex items-center justify-between mb-4"><h3 className="font-display text-lg font-semibold">Upcoming Appointments</h3><button onClick={() => navigate("/dashboard/appointments")} className="text-xs text-gold flex items-center gap-1">View all <ArrowRight className="w-3 h-3" /></button></div>
          <div className="space-y-3">
            {bookings.length === 0 && <p className="text-sm text-slate-500">No appointments yet.</p>}
            {bookings.map((b) => (
              <div key={b.booking_id} className="flex items-center justify-between border-b border-amber-500/10 pb-3">
                <div><div className="text-sm font-medium">{b.customer_name}</div><div className="text-xs text-slate-500">{b.service}</div></div>
                <div className="text-xs text-slate-400 font-mono">{new Date(b.datetime).toLocaleString([], { dateStyle: "medium", timeStyle: "short", timeZone: business?.scheduling?.timezone || b.timezone || undefined })}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="lux-card p-6">
          <div className="flex items-center justify-between mb-4"><h3 className="font-display text-lg font-semibold">Recent Leads</h3><button onClick={() => navigate("/dashboard/leads")} className="text-xs text-gold flex items-center gap-1">View all <ArrowRight className="w-3 h-3" /></button></div>
          <div className="space-y-3">
            {leads.length === 0 && <p className="text-sm text-slate-500">No leads yet.</p>}
            {leads.map((l) => (
              <div key={l.lead_id} className="flex items-center justify-between border-b border-amber-500/10 pb-3">
                <div><div className="text-sm font-medium">{l.name}</div><div className="text-xs text-slate-500">{l.source}</div></div>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${l.status === "new" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" : "bg-amber-500/10 text-amber-300 border-amber-500/30"}`}>{l.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
