import { motion } from "framer-motion";
import { PhoneCall, MessageSquare, CalendarCheck, Send, LayoutDashboard, ShieldCheck, TrendingUp, Clock, Layers } from "lucide-react";

export const fade = { initial: { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true }, transition: { duration: 0.6 } };

export function Eyebrow({ children }) {
  return <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.32em] text-gold font-sans font-medium mb-5"><span className="h-px w-8 bg-gold/60" />{children}</p>;
}

export function StatusBadge({ status }) {
  const live = status === "Live";
  return (
    <span data-testid={`status-badge-${status.toLowerCase().replace(/\W+/g, "-")}`}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] tracking-[0.16em] uppercase font-medium border ${live ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" : "text-amber-300 border-amber-500/30 bg-amber-500/10"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${live ? "bg-emerald-500" : "bg-amber-400"}`} />{status}
    </span>
  );
}

const feed = [
  { icon: MessageSquare, label: "Website chat", text: "Booked a Signature Facial for Friday, 3pm", tag: "Live" },
  { icon: Send, label: "Follow-up", text: "Email draft approved for James C. (opted in)", tag: "Simulated" },
  { icon: PhoneCall, label: "AI reception", text: "Captured caller details · membership inquiry", tag: "Simulated" },
];

export function HeroConsole() {
  return (
    <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 0.15 }} className="relative min-w-0" data-testid="hero-console-preview">
      <div className="lux-card p-6 gold-glow">
        <div className="flex items-center justify-between mb-6">
          <span className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Eazy’s Business AI Console</span>
          <span className="flex items-center gap-1.5 text-xs text-emerald-400"><span className="w-2 h-2 rounded-full bg-emerald-500 pulse-live" />AI Online</span>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-6">
          {[["Conversations", "128"], ["New leads", "34"], ["Bookings", "21"]].map(([l, v]) => (
            <div key={l} className="rounded-xl bg-[#0B0D12] border border-amber-500/10 p-4">
              <div className="font-serif text-3xl text-slate-100">{v}</div><div className="text-[11px] text-slate-500 mt-1">{l}</div>
            </div>
          ))}
        </div>
        <div className="space-y-2.5">
          {feed.map((f) => (
            <div key={f.text} className="flex items-center gap-3 rounded-xl bg-[#0B0D12]/70 border border-amber-500/10 px-4 py-3">
              <f.icon className="w-4 h-4 text-gold shrink-0" />
              <div className="min-w-0 flex-1"><div className="text-[11px] text-slate-500">{f.label}</div><div className="text-sm text-slate-200 truncate">{f.text}</div></div>
              <StatusBadge status={f.tag} />
            </div>
          ))}
        </div>
        <p className="text-[10px] text-slate-600 mt-4 tracking-wide">Illustrative preview with sample data.</p>
      </div>
    </motion.div>
  );
}

const benefits = [
  { icon: Clock, title: "Always available", desc: "Respond to customers around the clock without growing your front desk." },
  { icon: TrendingUp, title: "More captured revenue", desc: "Every conversation becomes a tracked lead with a clear next step." },
  { icon: Layers, title: "One command center", desc: "Conversations, leads, bookings and follow-ups — unified in a single console." },
  { icon: ShieldCheck, title: "Private by design", desc: "Each business runs in an isolated workspace with its own customer records." },
];

export function Benefits() {
  return (
    <section id="features" className="py-24 lg:py-32 px-4 sm:px-8 border-t border-amber-500/10">
      <div className="max-w-7xl mx-auto">
        <motion.div {...fade} className="mb-16 max-w-2xl">
          <Eyebrow>Core Benefits</Eyebrow>
          <h2 className="font-serif text-3xl lg:text-5xl font-medium">Built for businesses that intend to lead.</h2>
        </motion.div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {benefits.map((b, i) => (
            <motion.div key={b.title} {...fade} transition={{ duration: 0.5, delay: i * 0.08 }} className="lux-card p-7 transition-[border-color,transform] duration-300 hover:-translate-y-1" data-testid={`benefit-card-${i}`}>
              <b.icon className="w-5 h-5 text-gold mb-6" />
              <h3 className="font-display text-lg font-semibold text-slate-100 mb-2">{b.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{b.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

const capabilities = [
  { icon: PhoneCall, title: "AI Reception", status: "Simulated", desc: "An AI receptionist greets callers in your brand voice, answers common questions and captures caller details.", points: ["Custom greeting and tone", "Call summaries in your console", "Live telephony connection in development"] },
  { icon: MessageSquare, title: "AI Website Chat", status: "Live", desc: "An embeddable assistant that answers from your services, hours and FAQs — and remembers the conversation.", points: ["One-line install on any website", "Trained on your business details", "Every chat saved to your console"] },
  { icon: CalendarCheck, title: "Smart Appointment Scheduling", status: "Live", desc: "Create, confirm and manage appointments in one calendar view built for busy teams.", points: ["Booking status at a glance", "Customer notes on every visit", "External calendar sync in development"] },
  { icon: Send, title: "Automated Lead Follow-Ups", status: "Simulated", desc: "Permission-based email and SMS follow-ups, with AI-drafted messages that sound like you.", points: ["Consent-aware by default", "AI-written drafts", "Sends logged, not yet delivered"] },
  { icon: LayoutDashboard, title: "Business Owner Dashboard", status: "Live", desc: "The Eazy’s Business AI Console brings conversations, leads, bookings and customers into one refined view.", points: ["Performance overview", "Customer and lead records", "Assistant customization"] },
];

export function Capabilities() {
  return (
    <section className="pb-24 lg:pb-32 px-4 sm:px-8">
      <div className="max-w-7xl mx-auto">
        <motion.div {...fade} className="mb-16 max-w-2xl">
          <Eyebrow>The Platform</Eyebrow>
          <h2 className="font-serif text-3xl lg:text-5xl font-medium">Five capabilities. One intelligent system.</h2>
          <p className="text-slate-500 text-sm mt-4">Capabilities marked <span className="text-amber-300">Simulated</span> are in development: activity is generated and logged, but not yet connected to real phone or messaging networks.</p>
        </motion.div>
        <div className="divide-y divide-amber-500/10 border-y border-amber-500/10">
          {capabilities.map((c, i) => (
            <motion.div key={c.title} {...fade} className="grid lg:grid-cols-[80px_1fr_1fr] gap-6 lg:gap-12 py-10 items-start" data-testid={`capability-${i}`}>
              <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center"><c.icon className="w-6 h-6 text-gold" /></div>
              <div>
                <div className="flex flex-wrap items-center gap-3 mb-3"><h3 className="font-serif text-2xl lg:text-3xl font-medium text-slate-100">{c.title}</h3><StatusBadge status={c.status} /></div>
                <p className="text-slate-400 leading-relaxed max-w-lg">{c.desc}</p>
              </div>
              <ul className="space-y-2.5 lg:pt-2">
                {c.points.map((p) => <li key={p} className="flex items-center gap-3 text-sm text-slate-300"><span className="w-1 h-1 rotate-45 bg-gold" />{p}</li>)}
              </ul>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
