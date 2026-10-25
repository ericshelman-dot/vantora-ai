import { Logo } from "@/components/brand/Logo";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";

const googleLogin = () => {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

function Shell({ children, title, subtitle }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#0B0D12]">
      <div className="hidden lg:block relative">
        <img src="https://images.pexels.com/photos/5378701/pexels-photo-5378701.jpeg?auto=compress&cs=tinysrgb&w=940&h=1200" alt="Luxury" className="absolute inset-0 w-full h-full object-cover opacity-50" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0B0D12] via-[#0B0D12]/40 to-transparent" />
        <div className="relative h-full flex flex-col justify-end p-12">
          <Link to="/" className="flex items-center gap-2 mb-auto"><Logo size="2xl" /></Link>
          <h2 className="font-serif text-4xl font-medium leading-tight mb-3">Your Business.<br /><span className="gold-gradient-text">Always Ahead.</span></h2>
          <p className="text-slate-400 max-w-sm">The intelligent business command center for growing businesses.</p>
        </div>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 mb-8 justify-center"><Logo size="2xl" /></Link>
          <h1 className="font-serif text-3xl font-semibold mb-2">{title}</h1>
          <p className="text-slate-400 text-sm mb-8">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

export function GoogleButton({ label }) {
  return (
    <Button data-testid="google-auth-button" type="button" onClick={googleLogin} variant="outline"
      className="w-full bg-transparent border-amber-500/30 text-slate-200 hover:bg-amber-500/10 rounded-lg h-11">
      <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-5 h-5 mr-2" />{label}
    </Button>
  );
}

export { Shell };

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success("Welcome back");
      navigate(u.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <Shell title="Welcome back" subtitle="Sign in to the Eazy’s Business AI Console.">
      <form onSubmit={submit} className="space-y-4">
        <div><Label className="text-slate-300">Email</Label>
          <Input data-testid="login-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="you@business.com" /></div>
        <div><Label className="text-slate-300">Password</Label>
          <Input data-testid="login-password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="••••••••" /></div>
        <Button data-testid="login-submit-button" disabled={loading} className="w-full bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-lg h-11 font-medium">{loading ? "Signing in…" : "Sign In"}</Button>
      </form>
      <div className="flex items-center gap-3 my-6"><div className="h-px flex-1 bg-amber-500/15" /><span className="text-xs text-slate-500">OR</span><div className="h-px flex-1 bg-amber-500/15" /></div>
      <GoogleButton label="Continue with Google" />
      <p className="text-center text-sm text-slate-400 mt-6">No account? <Link to="/signup" className="text-gold hover:underline">Create one</Link></p>
    </Shell>
  );
}

export function SignupPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", business_name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form);
      toast.success("Account created — welcome!");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Signup failed");
    } finally { setLoading(false); }
  };

  return (
    <Shell title="Create your workspace" subtitle="Set up your AI business assistant in minutes.">
      <form onSubmit={submit} className="space-y-4">
        <div><Label className="text-slate-300">Your name</Label>
          <Input data-testid="signup-name-input" required value={form.name} onChange={set("name")} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="Jane Doe" /></div>
        <div><Label className="text-slate-300">Business name</Label>
          <Input data-testid="signup-business-input" required value={form.business_name} onChange={set("business_name")} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="Aura Luxury Spa" /></div>
        <div><Label className="text-slate-300">Email</Label>
          <Input data-testid="signup-email-input" type="email" required value={form.email} onChange={set("email")} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="you@business.com" /></div>
        <div><Label className="text-slate-300">Password</Label>
          <Input data-testid="signup-password-input" type="password" required minLength={6} value={form.password} onChange={set("password")} className="mt-1.5 bg-[#171A21] border-amber-500/20 h-11" placeholder="Min 6 characters" /></div>
        <Button data-testid="signup-submit-button" disabled={loading} className="w-full bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-lg h-11 font-medium">{loading ? "Creating…" : "Create Account"}</Button>
      </form>
      <div className="flex items-center gap-3 my-6"><div className="h-px flex-1 bg-amber-500/15" /><span className="text-xs text-slate-500">OR</span><div className="h-px flex-1 bg-amber-500/15" /></div>
      <GoogleButton label="Sign up with Google" />
      <p className="text-center text-sm text-slate-400 mt-6">Already have an account? <Link to="/login" className="text-gold hover:underline">Sign in</Link></p>
    </Shell>
  );
}
