import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Navbar, Footer } from "@/components/marketing/Nav";
import { HeroConsole, Benefits, Capabilities, fade, Eyebrow } from "@/components/marketing/Sections";
import { ContactSection } from "@/components/marketing/ContactSection";
import { api } from "@/lib/api";

const steps = [
  { n: "01", title: "Onboard your business", desc: "Create a secure workspace and add your services, hours, FAQs and brand voice." },
  { n: "02", title: "Train your AI", desc: "Tune tone and knowledge. Your website chat starts answering customers immediately." },
  { n: "03", title: "Command every opportunity", desc: "Conversations, leads and bookings flow into the Eazy’s Business AI Console with follow-ups queued." },
];

const faqs = [
  { q: "What is live today, and what is simulated?", a: "AI Website Chat runs on a live AI model. Appointment scheduling, lead management and the dashboard are fully functional. AI phone reception and email/SMS follow-up delivery are simulated in this stage — calls and sends are generated and logged in your console, but no real calls are answered and no messages leave the platform." },
  { q: "Is my customer data separated from other businesses?", a: "Yes. Every business operates in an isolated workspace. Owners can only access their own customers, leads, bookings and conversations." },
  { q: "How is Eazy’s Business AI priced?", a: "A one-time setup fee plus a monthly subscription. Plans are shown below. Online payment is not yet connected, so no card is charged — our team activates subscriptions manually." },
  { q: "Can I customize the AI assistant?", a: "Yes. Set your business name, services, hours, FAQs, contact details and tone. The assistant answers in your brand's voice." },
  { q: "Are follow-ups permission-based?", a: "Yes. Follow-ups only run when consent is enabled for your business, and every send is logged against the lead." },
];

export default function Home() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  useEffect(() => { api.get("/plans").then(({ data }) => setPlans(data)).catch(() => {}); }, []);

  return (
    <div className="bg-[#0B0D12] text-slate-100 overflow-x-hidden">
      <Navbar />

      <section className="relative pt-36 pb-24 lg:pb-32 px-4 sm:px-8">
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_left,rgba(214,183,108,0.10),transparent_55%)]" />
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-16 items-center relative">
          <motion.div {...fade} className="min-w-0">
            <Eyebrow>Your Business. Always Ahead.</Eyebrow>
            <h1 data-testid="hero-headline" className="font-serif text-4xl sm:text-5xl lg:text-6xl font-medium leading-[1.05] tracking-tight mb-7">
              Every Call. Every Chat.<br /><span className="gold-gradient-text">Every Opportunity.</span>
            </h1>
            <p className="text-base sm:text-lg text-slate-400 leading-relaxed max-w-xl mb-10">
              Meet Eazy’s Business AI, the intelligent business command center that helps you manage conversations, capture leads, schedule appointments, and automate follow-ups—all from one powerful platform.
            </p>
            <div className="flex flex-wrap gap-4">
              <Button data-testid="hero-cta-button" onClick={() => navigate("/signup")}
                className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] font-medium rounded-full px-8 h-12 text-base transition-[background-color,transform] hover:-translate-y-0.5">
                Get Started <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
              <Button data-testid="hero-explore-button" variant="outline" onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
                className="border-amber-500/30 text-slate-200 hover:bg-amber-500/10 rounded-full px-8 h-12 text-base bg-transparent">
                Explore Eazy’s Business AI
              </Button>
            </div>
          </motion.div>
          <HeroConsole />
        </div>
      </section>

      <Benefits />
      <Capabilities />

      <section id="how" className="py-24 lg:py-32 px-4 sm:px-8 bg-[#0F1117] border-y border-amber-500/10">
        <div className="max-w-7xl mx-auto">
          <motion.div {...fade} className="mb-16 max-w-2xl">
            <Eyebrow>How It Works</Eyebrow>
            <h2 className="font-serif text-3xl lg:text-5xl font-medium">From setup to command, in a day.</h2>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-px bg-amber-500/10 rounded-2xl overflow-hidden">
            {steps.map((s, i) => (
              <motion.div key={s.n} {...fade} transition={{ duration: 0.5, delay: i * 0.1 }} className="bg-[#0F1117] p-10" data-testid={`how-step-${i}`}>
                <div className="font-serif text-5xl gold-gradient-text mb-6">{s.n}</div>
                <h3 className="font-display text-xl font-semibold mb-3 text-slate-100">{s.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="py-24 lg:py-32 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div {...fade} className="mb-16 max-w-2xl">
            <Eyebrow>Subscription Plans</Eyebrow>
            <h2 className="font-serif text-3xl lg:text-5xl font-medium">One setup fee. Simple monthly plans.</h2>
            <p className="text-slate-500 text-sm mt-4" data-testid="pricing-payment-note">Online payments are not yet connected — no card is charged at signup.</p>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-6">
            {plans.map((p, i) => (
              <motion.div key={p.plan_id} {...fade} transition={{ duration: 0.5, delay: i * 0.08 }}
                className={`lux-card p-9 flex flex-col ${i === 1 ? "border-amber-500/50 gold-glow" : ""}`} data-testid={`pricing-card-${i}`}>
                {i === 1 && <span className="self-start px-3 py-1 rounded-full text-[10px] tracking-[0.2em] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30 mb-5">MOST CHOSEN</span>}
                <h3 className="font-display text-2xl font-semibold text-amber-100">{p.name}</h3>
                <div className="mt-5 mb-1"><span className="font-serif text-5xl gold-gradient-text">${p.monthly_fee}</span><span className="text-slate-500">/mo</span></div>
                <div className="text-sm text-slate-500 mb-8">+ ${p.setup_fee} one-time setup</div>
                <ul className="space-y-3 flex-1 mb-8">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300"><Check className="w-4 h-4 text-gold mt-0.5 shrink-0" /> {f}</li>
                  ))}
                </ul>
                <Button data-testid={`pricing-cta-${i}`} onClick={() => navigate("/signup")}
                  className={i === 1 ? "bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full w-full" : "bg-transparent border border-amber-500/30 text-slate-200 hover:bg-amber-500/10 rounded-full w-full"}>
                  Get Started
                </Button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="faqs" className="py-24 lg:py-32 px-4 sm:px-8 bg-[#0F1117] border-y border-amber-500/10">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-[1fr_1.6fr] gap-12">
          <motion.div {...fade}>
            <Eyebrow>FAQs</Eyebrow>
            <h2 className="font-serif text-3xl lg:text-5xl font-medium">Questions, answered with clarity.</h2>
          </motion.div>
          <Accordion type="single" collapsible className="space-y-3">
            {faqs.map((f, i) => (
              <AccordionItem key={i} value={`item-${i}`} className="lux-card px-6 border-amber-500/15" data-testid={`faq-item-${i}`}>
                <AccordionTrigger className="text-left font-display text-slate-100 hover:text-gold hover:no-underline">{f.q}</AccordionTrigger>
                <AccordionContent className="text-slate-400 leading-relaxed">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      <ContactSection />
      <Footer />
    </div>
  );
}
