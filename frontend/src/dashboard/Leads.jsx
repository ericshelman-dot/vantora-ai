import { useEffect, useMemo, useState } from "react";
import { Plus, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { PageHeader, Empty } from "@/dashboard/parts";
import { LeadDetail } from "@/dashboard/LeadDetail";
import { DuplicateReview } from "@/dashboard/DuplicateReview";

export const STATUSES = ["new", "contacted", "qualified", "booked", "closed"];
export const statusColor = (s) => ({
  new: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  contacted: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  qualified: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  booked: "bg-[#D6B76C]/15 text-amber-200 border-amber-500/40",
}[s] || "bg-slate-500/10 text-slate-400 border-slate-500/30");

const blank = { name: "", email: "", phone: "", source: "manual", notes: "", status: "new" };
const field = "bg-[#171A21] border-amber-500/20 mt-1";

function AddLead({ onSaved }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const save = async () => {
    if (!form.name) return toast.error("Name required");
    try { await api.post("/leads", form); toast.success("Lead added"); setOpen(false); setForm(blank); onSaved(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not add lead"); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button data-testid="add-lead-button" className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full px-6"><Plus className="w-4 h-4 mr-2" /> Add Lead</Button></DialogTrigger>
      <DialogContent className="bg-[#13161D] border-amber-500/20 text-slate-100">
        <DialogHeader><DialogTitle className="font-serif text-2xl">New Lead</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label>Name</Label><Input data-testid="lead-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={field} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Email</Label><Input data-testid="lead-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={field} /></div>
            <div><Label>Phone</Label><Input data-testid="lead-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className={field} /></div>
          </div>
          <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className={field} /></div>
          <p className="text-xs text-slate-500">Manually added leads have no marketing consent until the customer opts in.</p>
        </div>
        <DialogFooter><Button data-testid="save-lead-button" onClick={save} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full">Save Lead</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LeadRow({ l, onOpen }) {
  const c = l.consent || {};
  const pill = (ch, label) => {
    const v = c[ch]?.granted;
    return <span className={`text-[10px] px-1.5 py-0.5 rounded border ${v === true ? "border-emerald-500/30 text-emerald-400" : v === false ? "border-red-500/30 text-red-400" : "border-slate-600/40 text-slate-500"}`}>{label} {v === true ? "opt-in" : v === false ? "opt-out" : "no consent"}</span>;
  };
  return (
    <button onClick={() => onOpen(l.lead_id)} data-testid={`lead-card-${l.lead_id}`} className="lux-card p-5 w-full text-left transition-[border-color,transform] hover:border-amber-500/40 hover:-translate-y-0.5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-display font-semibold text-amber-100">{l.name}</span>
            <span data-testid={`lead-status-${l.lead_id}`} className={`text-xs px-2 py-0.5 rounded-full border capitalize ${statusColor(l.status)}`}>{l.status}</span>
            {l.chat_session_ids?.length > 0 && <span data-testid={`lead-auto-captured-${l.lead_id}`} className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-widest border border-emerald-500/30 text-emerald-400">auto-captured from AI chat</span>}
          </div>
          <div className="text-xs text-slate-500 mt-1">{[l.email, l.phone].filter(Boolean).join(" · ")} · via {l.source} · {new Date(l.inquiry_date || l.created_at).toLocaleDateString()}</div>
          {l.summary && <p className="text-sm text-slate-400 mt-2 line-clamp-2"><Sparkles className="w-3 h-3 text-gold inline mr-1" />{l.summary}</p>}
          {l.service_interests?.length > 0 && <div className="flex flex-wrap gap-1.5 mt-2">{l.service_interests.map((s) => <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-200">{s}</span>)}</div>}
        </div>
        <div className="flex flex-col items-end gap-1.5">{l.consent?.inquiry_reply?.granted && <span data-testid={`lead-inquiry-ok-${l.lead_id}`} className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/30 text-emerald-400">Inquiry reply allowed</span>}{l.consent?.inquiry_reply && !l.consent.inquiry_reply.granted && <span data-testid={`lead-inquiry-declined-${l.lead_id}`} className="text-[10px] px-1.5 py-0.5 rounded border border-red-500/30 text-red-400">Inquiry reply declined</span>}{pill("email", "Email")}{pill("sms", "SMS")}
          {l.drafts?.some((d) => d.status === "pending") && <span className="text-[10px] text-amber-300">Draft awaiting approval</span>}
        </div>
      </div>
    </button>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(null);
  const [errors, setErrors] = useState([]);
  const load = () => {
    api.get("/leads").then(({ data }) => setLeads(data)).catch(() => {});
    api.get("/lead-capture-errors").then(({ data }) => setErrors(data)).catch(() => {});
  };
  const resolve = async (id) => { await api.post(`/lead-capture-errors/${id}/resolve`); load(); };
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, []);

  const counts = useMemo(() => Object.fromEntries(STATUSES.map((s) => [s, leads.filter((l) => l.status === s).length])), [leads]);
  const shown = leads.filter((l) => (status === "all" || l.status === status) &&
    (!q || [l.name, l.email, l.phone, l.summary, ...(l.service_interests || [])].join(" ").toLowerCase().includes(q.toLowerCase())));

  return (
    <div>
      <PageHeader eyebrow="CRM" title="Leads" desc="Leads captured automatically by your AI assistant and added manually. Outbound email and SMS are simulated." action={<div className="flex gap-2"><DuplicateReview onChanged={load} /><AddLead onSaved={load} /></div>} />
      {errors.length > 0 && (
        <div data-testid="lead-capture-errors" className="mb-6 rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <div className="text-sm text-red-300 font-medium mb-2">{errors.length} chat contact detail(s) could not be saved automatically. Review and add them manually:</div>
          {errors.map((e) => (
            <div key={e.error_id} className="flex items-start gap-3 text-xs text-slate-300 mb-1.5">
              <span className="flex-1">"{e.message}" <span className="text-slate-600">· {new Date(e.created_at).toLocaleString()}</span></span>
              <button data-testid={`lead-capture-error-resolve-${e.error_id}`} onClick={() => resolve(e.error_id)} className="text-gold hover:underline">Mark handled</button>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex flex-wrap gap-1.5 p-1 rounded-full bg-[#13161D] border border-amber-500/15">
          {["all", ...STATUSES].map((s) => (
            <button key={s} data-testid={`lead-filter-${s}`} onClick={() => setStatus(s)} className={`px-3.5 py-1.5 rounded-full text-xs capitalize transition-colors ${status === s ? "bg-gold text-[#0B0D12]" : "text-slate-400 hover:text-slate-100"}`}>
              {s}{s !== "all" && ` (${counts[s] || 0})`}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <Input data-testid="lead-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, contact, interest…" className="pl-9 bg-[#171A21] border-amber-500/20 h-9" />
        </div>
      </div>
      {shown.length === 0 ? <Empty text={leads.length ? "No leads match this filter." : "No leads yet. Your AI assistant captures them automatically when customers share their details."} /> : (
        <div className="space-y-3" data-testid="leads-list">{shown.map((l) => <LeadRow key={l.lead_id} l={l} onOpen={setOpenId} />)}</div>
      )}
      <LeadDetail leadId={openId} onClose={() => setOpenId(null)} onChanged={load} />
    </div>
  );
}
