import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Users, GitMerge, Undo2, CalendarCheck, MessageSquare, ShieldAlert } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api } from "@/lib/api";

const consentLabel = (c) => (c ? (c.granted ? "opted in" : "opted out") : "no consent");

function LeadCard({ b, primary, selected, onPrimary, onToggle }) {
  const l = b.lead;
  return (
    <div data-testid={`dup-lead-${l.lead_id}`} className={`rounded-xl border p-4 ${primary ? "border-gold bg-amber-500/5" : "border-amber-500/15"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-display font-semibold text-amber-100">{l.name} <span className="text-[10px] font-mono text-slate-400">{l.lead_id}</span></div>
          <div className="text-xs text-slate-400">{[l.email, l.phone].filter(Boolean).join(" · ") || "no contact"} · <span className="capitalize">{l.status}</span> · {new Date(l.inquiry_date || l.created_at).toLocaleDateString()}</div>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs">
          <label className="flex items-center gap-1.5 cursor-pointer"><input type="radio" data-testid={`dup-primary-${l.lead_id}`} checked={primary} onChange={onPrimary} className="accent-[#D6B76C]" />Keep as primary</label>
          {!primary && <label className="flex items-center gap-1.5 cursor-pointer"><input type="checkbox" data-testid={`dup-select-${l.lead_id}`} checked={selected} onChange={onToggle} className="accent-[#D6B76C]" />Merge into primary</label>}
        </div>
      </div>
      {l.service_interests?.length > 0 && <div className="flex flex-wrap gap-1 mt-2">{l.service_interests.map((s) => <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-200">{s}</span>)}</div>}
      <div className="text-[11px] text-slate-500 mt-2">Inquiry reply: {consentLabel(l.consent?.inquiry_reply)} · Email: {consentLabel(l.consent?.email)} · SMS: {consentLabel(l.consent?.sms)}</div>
      <div className="mt-2 space-y-1">
        {b.bookings.map((bk) => <div key={bk.booking_id} className="text-xs text-slate-400 flex items-center gap-1.5"><CalendarCheck className="w-3 h-3 text-gold" />{bk.service} · {new Date(bk.datetime).toLocaleString()} · {bk.booking_id}</div>)}
        {b.conversations.map((c) => (
          <details key={c.session_id} className="text-xs">
            <summary className="cursor-pointer text-slate-400 flex items-center gap-1.5"><MessageSquare className="w-3 h-3 text-gold inline" />Chat {c.session_id} · {c.messages.length} messages</summary>
            <div className="mt-1 pl-4 max-h-40 overflow-y-auto space-y-1">{c.messages.map((m, i) => <div key={i} className={m.role === "user" ? "text-amber-200" : "text-slate-500"}><b className="text-[9px] uppercase mr-1">{m.role === "user" ? "Customer" : "AI"}</b>{m.content.slice(0, 300)}</div>)}</div>
          </details>
        ))}
      </div>
    </div>
  );
}

function Group({ g, onDone }) {
  const [primary, setPrimary] = useState(g.leads[0]?.lead.lead_id);
  const [sel, setSel] = useState([]);
  const [plan, setPlan] = useState(null);
  const dupIds = sel.filter((i) => i !== primary);
  const review = async () => {
    try { const { data } = await api.post("/lead-merges/preview", { primary_id: primary, duplicate_ids: dupIds }); setPlan(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not prepare merge"); }
  };
  const approve = async () => {
    try { await api.post("/lead-merges", { primary_id: primary, duplicate_ids: dupIds, confirm: true }); toast.success("Merged. Superseded records archived — undo available in merge history."); setPlan(null); onDone(); }
    catch (e) { toast.error(e.response?.data?.detail || "Merge failed"); }
  };
  return (
    <div className="lux-card p-5 mb-5" data-testid={`dup-group-${g.group_id}`}>
      <div className={`text-xs mb-3 flex items-center gap-2 ${g.match === "name_only" ? "text-amber-300" : "text-red-300"}`}><ShieldAlert className="w-4 h-4" />{g.reason} · {g.leads.length} records</div>
      <div className="space-y-3">
        {g.leads.map((b) => (
          <LeadCard key={b.lead.lead_id} b={b} primary={primary === b.lead.lead_id} selected={sel.includes(b.lead.lead_id)}
            onPrimary={() => { setPrimary(b.lead.lead_id); setSel(sel.filter((i) => i !== b.lead.lead_id)); }}
            onToggle={() => setSel(sel.includes(b.lead.lead_id) ? sel.filter((i) => i !== b.lead.lead_id) : [...sel, b.lead.lead_id])} />
        ))}
      </div>
      <Button data-testid={`dup-review-merge-${g.group_id}`} disabled={!dupIds.length} onClick={review} className="mt-4 bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-9 disabled:bg-slate-700 disabled:text-slate-400"><GitMerge className="w-4 h-4 mr-2" />Review merge ({dupIds.length})</Button>
      <AlertDialog open={!!plan} onOpenChange={(o) => !o && setPlan(null)}>
        <AlertDialogContent className="bg-[#171A21] border-amber-500/30 text-slate-100" data-testid="dup-merge-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl">Approve this merge?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="text-slate-400 text-sm space-y-1.5">
                <p>{plan?.duplicate_ids.length} record(s) will be merged into <b className="text-amber-200">{primary}</b> and archived (not deleted). You can undo it from merge history.</p>
                <p>Result: {plan?.conversations} conversations · {plan?.bookings} appointment{plan?.bookings === 1 ? "" : "s"}{plan?.booking_ids?.length ? ` (${plan.booking_ids.join(", ")})` : ""} · {plan?.follow_ups} follow-ups · status {plan?.result_status} · interests: {plan?.service_interests.join(", ") || "none"}</p>
                {plan?.alternate_emails.length > 0 && <p>Other emails kept as alternates: {plan.alternate_emails.join(", ")}</p>}
                <p data-testid="dup-merge-consent-result">Consent after merge (most cautious): inquiry reply {consentLabel(plan?.result_consent.inquiry_reply)} · email {consentLabel(plan?.result_consent.email)} · SMS {consentLabel(plan?.result_consent.sms)}. Full consent history is kept.</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="dup-merge-cancel" className="bg-transparent border-amber-500/20 text-slate-300">Cancel</AlertDialogCancel>
            <AlertDialogAction data-testid="dup-merge-approve" onClick={approve} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12]">Approve merge</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export function DuplicateReview({ onChanged }) {
  const [open, setOpen] = useState(false);
  const [groups, setGroups] = useState([]);
  const [history, setHistory] = useState([]);
  const load = () => {
    api.get("/lead-duplicates").then(({ data }) => setGroups(data)).catch(() => {});
    api.get("/lead-merges").then(({ data }) => setHistory(data)).catch(() => {});
  };
  useEffect(() => { load(); }, [open]);
  const done = () => { load(); onChanged(); };
  const undo = async (id) => {
    try {
      const { data } = await api.post(`/lead-merges/${id}/undo`);
      toast.success(data.conflicts?.length ? "Merge undone. Some restored contacts are now used by another lead — check Duplicate Review." : "Merge undone — records restored");
      done();
    } catch (e) { toast.error(e.response?.data?.detail || "Undo failed"); }
  };
  return (<>
    <Button data-testid="duplicate-review-button" variant="outline" onClick={() => setOpen(true)} className="bg-transparent border-amber-500/30 text-slate-200 hover:bg-amber-500/10 rounded-full h-9">
      <Users className="w-4 h-4 mr-2" />Duplicate Review{groups.length > 0 && <span className="ml-2 px-1.5 rounded-full bg-gold text-[#0B0D12] text-[10px] font-bold" data-testid="duplicate-count">{groups.length}</span>}
    </Button>
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent className="bg-[#13161D] border-amber-500/20 text-slate-100 w-full sm:max-w-2xl overflow-y-auto" data-testid="duplicate-review-sheet">
        <SheetHeader><SheetTitle className="font-serif text-2xl text-slate-100">Duplicate Lead Review</SheetTitle>
          <p className="text-xs text-slate-500">Possible duplicates in this workspace. Nothing is merged until you approve it. Same-name matches are suggestions only.</p></SheetHeader>
        <div className="mt-6">{groups.length === 0 ? <p className="text-sm text-slate-500">No possible duplicates found.</p> : groups.map((g) => <Group key={g.group_id} g={g} onDone={done} />)}</div>
        <div className="border-t border-amber-500/10 pt-5 mt-5" data-testid="merge-history">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-3">Merge history</div>
          {history.length === 0 && <p className="text-xs text-slate-500">No merges yet.</p>}
          {history.map((m) => (
            <div key={m.merge_id} className="flex items-center gap-3 text-xs text-slate-400 mb-2">
              <span className="flex-1">{m.primary_before?.name} · {m.duplicate_ids.length} merged into {m.primary_id} · {new Date(m.at).toLocaleString()} · by {m.approved_by}{m.undone && " · undone"}</span>
              {!m.undone && <Button data-testid={`merge-undo-${m.merge_id}`} size="sm" variant="outline" onClick={() => undo(m.merge_id)} className="h-7 text-xs bg-transparent border-amber-500/30 text-gold"><Undo2 className="w-3 h-3 mr-1" />Undo</Button>}
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  </>);
}
