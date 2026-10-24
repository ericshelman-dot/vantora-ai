import { Logo } from "@/components/brand/Logo";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Menu, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

const links = [
  { label: "Platform", href: "#features" },
  { label: "How It Works", href: "#how" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQs", href: "#faqs" },
  { label: "Contact", href: "#contact" },
];

export function Navbar() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();
  return (
    <header className="fixed top-0 inset-x-0 z-50 glass">
      <nav className="max-w-7xl mx-auto px-4 sm:px-8 h-20 flex items-center justify-between">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-2">
          <Logo size="xl" />
        </Link>
        <div className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a key={l.label} href={l.href} data-testid={`nav-link-${l.label.toLowerCase().replace(/ /g,'-')}`}
              className="text-sm font-display text-slate-300 hover:text-gold transition-colors">{l.label}</a>
          ))}
        </div>
        <div className="hidden md:flex items-center gap-3">
          {user ? (
            <Button data-testid="nav-dashboard-btn" onClick={() => navigate(user.role === "admin" ? "/admin" : "/dashboard")}
              className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] font-medium rounded-full px-6">Dashboard</Button>
          ) : (
            <>
              <Link to="/login" data-testid="nav-login-link" className="text-sm font-display text-slate-300 hover:text-gold transition-colors">Login</Link>
              <Button data-testid="nav-get-started-btn" onClick={() => navigate("/signup")}
                className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] font-medium rounded-full px-6 hover:scale-[1.02] transition-transform">Get Started</Button>
            </>
          )}
        </div>
        <button data-testid="nav-mobile-toggle" className="md:hidden text-slate-200" onClick={() => setOpen(!open)}>
          {open ? <X /> : <Menu />}
        </button>
      </nav>
      {open && (
        <div className="md:hidden glass px-6 py-6 space-y-4 border-t border-amber-500/10">
          {links.map((l) => (
            <a key={l.label} href={l.href} onClick={() => setOpen(false)} className="block text-slate-300 hover:text-gold">{l.label}</a>
          ))}
          <Link to="/login" className="block text-slate-300">Login</Link>
          <Button onClick={() => navigate("/signup")} className="w-full bg-gold text-[#0B0D12] rounded-full">Get Started</Button>
        </div>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-amber-500/15 bg-[#08090D]">
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-16 grid md:grid-cols-4 gap-10">
        <div className="md:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <Logo size="xl" />
          </div>
          <p className="text-sm text-slate-400 max-w-sm leading-relaxed mt-4">Your Business. Always Ahead. The intelligent business command center for growing businesses.</p>
        </div>
        <div>
          <h4 className="font-display text-sm uppercase tracking-widest text-gold mb-4">Product</h4>
          <ul className="space-y-2 text-sm text-slate-400">
            <li><a href="#features" className="hover:text-gold">Features</a></li>
            <li><a href="#pricing" className="hover:text-gold">Pricing</a></li>
            <li><Link to="/signup" className="hover:text-gold">Get Started</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="font-display text-sm uppercase tracking-widest text-gold mb-4">Legal</h4>
          <ul className="space-y-2 text-sm text-slate-400">
            <li><Link to="/privacy" data-testid="footer-privacy-link" className="hover:text-gold">Privacy Policy</Link></li>
            <li><Link to="/terms" data-testid="footer-terms-link" className="hover:text-gold">Terms of Service</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-amber-500/10 py-6 text-center text-xs text-slate-500 font-mono">© 2026 Vantora AI. Your Business. Always Ahead.</div>
    </footer>
  );
}
