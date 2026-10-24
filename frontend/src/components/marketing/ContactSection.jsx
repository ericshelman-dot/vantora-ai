import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { CheckCircle2, Mail, CalendarCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { fade, Eyebrow } from "@/components/marketing/Sections";

const empty = { name: "", email: "", company: "", phone: "", message: "" };
const field = "mt-1.5 bg-[#171A21] border-amber-500/20 h-11";

export function ContactSection() {
  const [kind, setKind] = useState("demo");
  const [form, setForm] = useState(empty);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/demo-requests", { ...form, kind });
      setSent(true); setForm(empty);
      toast.success(kind === "demo" ? "Demo request received" : "Message received");
    } catch (err) {
      const d = err.response?.data?.detail;
      const field = Array.isArray(d) ? d[0]?.loc?.slice(-1)[0] : null;
      const msgs = { email: "Please enter a valid email address.", name: "Please enter your name." };
      toast.error(typeof d === "string" ? d : msgs[field] || "Please check your details and try again.");
    } finally { setSending(false); }
  };

  return (
    <section id="contact" className="py-24 lg:py-32 px-4 sm:px-8">
      <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16">
        <motion.div {...fade}>
          <Eyebrow>Contact & Demo</Eyebrow>
          <h2 className="font-serif text-3xl lg:text-5xl font-medium mb-6">See Vantora AI command your business.</h2>
          <p className="text-slate-400 leading-relaxed max-w-md mb-10">Request a guided walkthrough, or send us a question. Our team reviews every request personally.</p>
          <div className="space-y-4 text-sm text-slate-300">
            <div className="flex items-center gap-3"><CalendarCheck className="w-4 h-4 text-gold" /> 30-minute guided demo of the Console</div>
            <div className="flex items-center gap-3"><Mail className="w-4 h-4 text-gold" /> hello@vantora.ai</div>
          </div>
        </motion.div>
        <motion.div {...fade} className="lux-card p-8 lg:p-10">
          {sent ? (
            <div data-testid="contact-success" className="text-center py-12">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-4" />
              <h3 className="font-serif text-2xl mb-2">Thank you.</h3>
              <p className="text-slate-400 text-sm mb-6">Your request has been received. Our team will be in touch shortly.</p>
              <Button data-testid="contact-send-another" variant="outline" onClick={() => setSent(false)} className="bg-transparent border-amber-500/30 text-slate-200 hover:bg-amber-500/10 rounded-full">Send another</Button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4" data-testid="contact-form">
              <div className="inline-flex p-1 rounded-full bg-[#0B0D12] border border-amber-500/15 mb-2">
                {[["demo", "Request a demo"], ["contact", "General inquiry"]].map(([k, l]) => (
                  <button type="button" key={k} data-testid={`contact-kind-${k}`} onClick={() => setKind(k)}
                    className={`px-4 py-1.5 rounded-full text-sm transition-colors ${kind === k ? "bg-gold text-[#0B0D12]" : "text-slate-400 hover:text-slate-100"}`}>{l}</button>
                ))}
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><Label className="text-slate-300">Full name</Label><Input data-testid="contact-name-input" required value={form.name} onChange={set("name")} className={field} /></div>
                <div><Label className="text-slate-300">Work email</Label><Input data-testid="contact-email-input" type="email" required value={form.email} onChange={set("email")} className={field} /></div>
                <div><Label className="text-slate-300">Company</Label><Input data-testid="contact-company-input" value={form.company} onChange={set("company")} className={field} /></div>
                <div><Label className="text-slate-300">Phone</Label><Input data-testid="contact-phone-input" value={form.phone} onChange={set("phone")} className={field} /></div>
              </div>
              <div><Label className="text-slate-300">How can we help?</Label><Textarea data-testid="contact-message-input" value={form.message} onChange={set("message")} rows={4} className="mt-1.5 bg-[#171A21] border-amber-500/20" /></div>
              <Button data-testid="contact-submit-button" disabled={sending} className="w-full bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-12 font-medium">
                {sending ? "Sending…" : kind === "demo" ? "Request Demo" : "Send Message"}
              </Button>
            </form>
          )}
        </motion.div>
      </div>
    </section>
  );
}
