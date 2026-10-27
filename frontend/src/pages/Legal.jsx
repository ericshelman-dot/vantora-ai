import { Logo } from "@/components/brand/Logo";
import { Link } from "react-router-dom";
import { Sparkles, ArrowLeft } from "lucide-react";

function LegalShell({ title, children }) {
  return (
    <div className="min-h-screen bg-[#0B0D12] text-slate-300">
      <div className="glass">
        <div className="max-w-3xl mx-auto px-6 h-20 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2"><Logo size="xl" /></Link>
          <Link to="/" className="text-sm text-slate-400 hover:text-gold flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> Home</Link>
        </div>
      </div>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-serif text-4xl font-semibold mb-2">{title}</h1>
        <p className="text-sm text-slate-500 mb-10 font-mono">Last updated: June 2026</p>
        <div className="space-y-6 leading-relaxed text-slate-400">{children}</div>
      </div>
    </div>
  );
}

export function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy">
      <p>Eazy’s Business AI ("we") provides an AI business assistant platform. This policy explains how we collect, use, and protect information when you use our services.</p>
      <h3 className="font-display text-xl text-amber-100">Information We Collect</h3>
      <p>We collect account details (name, email, business information) and the interaction data you generate — calls, chats, leads, bookings, and customer records. Each business operates in an isolated, multi-tenant workspace.</p>
      <h3 className="font-display text-xl text-amber-100">How We Use Data</h3>
      <p>We use your data solely to power your AI assistant, manage your dashboard, and improve service quality. We never sell your customer data.</p>
      <h3 className="font-display text-xl text-amber-100">Follow-up Communications</h3>
      <p>Email and SMS follow-ups are permission-based and only triggered when you enable consent for your business. In the current demo, all sends are simulated and logged.</p>
      <h3 className="font-display text-xl text-amber-100">Security</h3>
      <p>We employ encryption and strict tenant separation so only you can access your workspace. Use the contact form on our homepage for privacy requests.</p>
    </LegalShell>
  );
}

export function TermsPage() {
  return (
    <LegalShell title="Terms of Service">
      <p>By accessing Eazy’s Business AI, you agree to these terms. The service is provided to local businesses as a subscription product with a one-time setup fee plus recurring monthly billing.</p>
      <h3 className="font-display text-xl text-amber-100">Subscriptions & Billing</h3>
      <p>Plans include a setup fee and monthly subscription. Pricing is managed by the platform administrator and may be updated. In this demo, payments are not processed.</p>
      <h3 className="font-display text-xl text-amber-100">Acceptable Use</h3>
      <p>You agree to use the AI assistant lawfully and to obtain any necessary consent before sending customer communications.</p>
      <h3 className="font-display text-xl text-amber-100">Service Availability</h3>
      <p>We strive for high availability. Certain features such as AI phone reception and SMS/email delivery are simulated in this demo environment and clearly labeled.</p>
      <h3 className="font-display text-xl text-amber-100">Liability</h3>
      <p>The service is provided "as is." Use the contact form on our homepage with questions about these terms.</p>
    </LegalShell>
  );
}
