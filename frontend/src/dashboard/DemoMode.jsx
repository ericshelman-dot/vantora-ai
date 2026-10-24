import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { FlaskConical, RotateCcw, ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export function DemoBanner() {
  const { user, exitDemo } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  const reset = async () => {
    setBusy(true);
    try {
      await api.post("/demo/reset");
      toast.success("Demo data reset to fresh samples");
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) { toast.error(e.response?.data?.detail || "Reset failed"); }
    finally { setBusy(false); }
  };

  const leave = async () => { await exitDemo(); toast.success("Returned to Admin Console"); navigate("/admin"); };

  return (
    <div data-testid="demo-mode-banner" className="bg-[#D6B76C]/10 border-b border-amber-500/30 px-4 sm:px-8 py-2.5 flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gold text-[#0B0D12] text-[10px] font-bold tracking-[0.2em]"><FlaskConical className="w-3 h-3" />DEMO MODE</span>
      <span className="text-xs text-amber-200 flex-1 min-w-[220px]">Sample business with fictional data. Phone calls, email, SMS and payments are simulated. Excluded from revenue reporting.</span>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button data-testid="demo-reset-button" size="sm" variant="outline" disabled={busy} className="h-8 bg-transparent border-amber-500/40 text-amber-200 hover:bg-amber-500/10 rounded-full text-xs"><RotateCcw className="w-3.5 h-3.5 mr-1.5" />Reset Demo Data</Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="bg-[#171A21] border-amber-500/30 text-slate-100">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl">Reset demo data?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">This clears the demo workspace's chats, leads, follow-ups and appointments and restores fresh sample records. Real customer accounts are never affected.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="demo-reset-cancel" className="bg-transparent border-amber-500/20 text-slate-300">Cancel</AlertDialogCancel>
            <AlertDialogAction data-testid="demo-reset-confirm" onClick={reset} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12]">Reset Demo Data</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {user?.demo_mode && (
        <Button data-testid="return-to-admin-button" size="sm" onClick={leave} className="h-8 bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full text-xs"><ArrowLeftRight className="w-3.5 h-3.5 mr-1.5" />Return to Admin Console</Button>
      )}
    </div>
  );
}

export function SwitchToDemoButton({ className = "" }) {
  const { enterDemo } = useAuth();
  const navigate = useNavigate();
  const go = async () => {
    try { await enterDemo(); toast.success("Switched to Demo Workspace"); navigate("/dashboard"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not open the demo workspace"); }
  };
  return (
    <Button data-testid="switch-to-demo-button" onClick={go} className={`bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-9 ${className}`}>
      <FlaskConical className="w-4 h-4 mr-2" />Switch to Demo Workspace
    </Button>
  );
}
