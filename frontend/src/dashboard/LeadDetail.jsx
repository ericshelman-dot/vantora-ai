import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, MessageSquare, Sparkles, Trash2, RefreshCw, CalendarCheck, Check, X, ShieldCheck } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { SimBadge } from "@/dashboard/parts";
import { STATUSES } from "@/dashboard/Leads";

const field = "bg-[#171A21] border-amber-500/20 h-9 mt-1";
const err = (e, f) => toast.error(e.response?.data?.detail || f);
const Section = ({ title, children, testid }) => (
  <div className="border-t border-amber-500/10 pt-5 mt-5" data-testid={testid}><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-3">{title}</div>{children}</div>
);

function Consent({ lead, reload }) {
  const optOut = async (channel) => {
    try { await api.post(`/leads/${lead.lead_id}/opt-out`, { channel }); toast.success("Opt-out recorded"); reload(); } catch (e) { err(e, "Failed"); }
  };
  const inq = lead.consent?.inquiry_reply;
  return (
    <Section title="Permissions & consent" testid="lead-consent-section">
      <div className="rounded-lg border border-amber-500/20 p-3 mb-3" data-testid="lead-consent-inquiry">
        <div className="text-sm font-medium">Reply to this inquiry: <span className={inq?.granted ? "text-emerald-400" : inq ? "text-red-400" : "text-slate-500"}>{inq?.granted ? `Allowed by ${inq.channel_to_use === "sms" ? "text" : "email"}` : inq ? "Declined" : "Not asked yet"}</span></div>
        <div className="text-[11px] text-slate-500 mt-0.5">Separate from marketing: permits one personal reply about their question only.</div>
        {inq && <div className="text-xs text-slate-500 mt-1.5">"{inq.text}" · {inq.source} · {new Date(inq.at).toLocaleString()}</div>}
      </div>
      <div className="text-[11px] uppercase tracking-[0.2em] text-slate-600 mb-2">Ongoing marketing</div>
      {["email", "sms"].map((ch) => {
        const c = lead.consent?.[ch];
        return (
          <div key={ch} className="rounded-lg border border-amber-500/10 p-3 mb-2" data-testid={`lead-consent-${ch}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{ch === "email" ? "Email" : "SMS"}: <span className={c?.granted ? "text-emerald-400" : c ? "text-red-400" : "text-slate-500"}>{c?.granted ? "Opted in" : c ? "Opted out" : "No consent given"}</span></span>
              {c?.granted && <Button data-testid={`lead-optout-${ch}`} size="sm" variant="outline" onClick={() => optOut(ch)} className="h-7 text-xs bg-transparent border-red-500/30 text-red-400">Record opt-out</Button>}
            </div>
            {c && <div className="text-xs text-slate-500 mt-1.5">"{c.text}" · {c.source} · {new Date(c.at).toLocaleString()}</div>}
          </div>
        );
      })}
    </Section>
  );
}

function Drafts({ lead, reload }) {
  const [busy, setBusy] = useState(null);
  const [edits, setEdits] = useState({});
  const gen = async (channel) => {
    setBusy(channel);
    try { await api.post(`/leads/${lead.lead_id}/drafts`, { channel }); toast.success("Draft ready for review"); reload(); } catch (e) { err(e, "Could not draft"); }
    finally { setBusy(null); }
  };
  const act = async (d, action) => {
    try {
      if (action === "approve" && edits[d.draft_id] !== undefined) await api.put(`/leads/${lead.lead_id}/drafts/${d.draft_id}`, { message: edits[d.draft_id] });
      await api.post(`/leads/${lead.lead_id}/drafts/${d.draft_id}/${action}`);
      toast.success(action === "approve" ? "Approved — SIMULATED SEND recorded. NOT ACTUALLY SENT." : "Draft discarded");
      reload();
    } catch (e) { err(e, "Failed"); }
  };
  const pending = (lead.drafts || []).filter((d) => d.status === "pending");
  return (
    <Section title="AI follow-up drafts" testid="lead-drafts-section">
      <div className="flex gap-2 mb-3">
        {["email", "sms"].map((ch) => (
          <Button key={ch} data-testid={`lead-draft-${ch}-button`} size="sm" disabled={!!busy} onClick={() => gen(ch)} variant="outline" className="bg-transparent border-amber-500/30 text-gold hover:bg-amber-500/10 rounded-full h-8 text-xs">
            <Sparkles className="w-3.5 h-3.5 mr-1" />{busy === ch ? "Drafting…" : `Draft ${ch === "email" ? "email" : "SMS"}`}
          </Button>
        ))}
      </div>
      {pending.map((d) => (
        <div key={d.draft_id} className="rounded-lg border border-amber-500/20 p-3 mb-2" data-testid={`lead-draft-${d.draft_id}`}>
          <div className="flex items-center gap-2 mb-2 text-xs text-slate-400">{d.channel === "email" ? <Mail className="w-3 h-3 text-gold" /> : <MessageSquare className="w-3 h-3 text-gold" />}{d.kind === "inquiry_reply" ? "INQUIRY REPLY" : "MARKETING"} · {d.channel.toUpperCase()} draft · awaiting your approval</div>
          <Textarea data-testid={`lead-draft-text-${d.draft_id}`} rows={4} value={edits[d.draft_id] ?? d.message} onChange={(e) => setEdits({ ...edits, [d.draft_id]: e.target.value })} className="bg-[#171A21] border-amber-500/20 text-sm" />
          <div className="flex gap-2 mt-2">
            <Button data-testid={`lead-draft-approve-${d.draft_id}`} size="sm" onClick={() => act(d, "approve")} className="h-8 bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full text-xs"><Check className="w-3.5 h-3.5 mr-1" />Approve & send (simulated)</Button>
            <Button data-testid={`lead-draft-discard-${d.draft_id}`} size="sm" variant="outline" onClick={() => act(d, "discard")} className="h-8 bg-transparent border-slate-600 text-slate-400 rounded-full text-xs"><X className="w-3.5 h-3.5 mr-1" />Discard</Button>
          </div>
        </div>
      ))}
      <p className="text-[11px] text-slate-600 flex items-center gap-1"><ShieldCheck className="w-3 h-3" />Sending requires the customer's opt-in for that channel. Email/SMS providers are not connected — sends are simulated.</p>
    </Section>
  );
}

function History({ lead }) {
  const items = [...(lead.follow_ups || [])].reverse();
  return (
    <Section title="Follow-up history" testid="lead-history-section">
      {items.length === 0 && <p className="text-xs text-slate-500">No follow-ups yet.</p>}
      {items.map((f) => (
        <div key={f.id} className="text-xs text-slate-400 mb-2 rounded-lg bg-[#0B0D12] border border-amber-500/10 p-2.5" data-testid={`lead-history-${f.id}`}>
          <div className="flex items-center gap-2 mb-1">{f.channel === "email" ? <Mail className="w-3 h-3 text-gold" /> : <MessageSquare className="w-3 h-3 text-gold" />}
            <span className="uppercase">{f.channel}</span><span className="text-slate-600">{{ booking_confirmation: "booking confirmation", inquiry_reply: "inquiry reply" }[f.kind] || "marketing follow-up"}</span>
            <SimBadge text="simulated send · NOT ACTUALLY SENT" /><span className="ml-auto text-slate-600">{new Date(f.sent_at).toLocaleString()}</span></div>
          <div className="text-slate-300 whitespace-pre-line">{f.message}</div>
          {f.approved_by && <div className="text-slate-600 mt-1">Approved by {f.approved_by}</div>}
        </div>
      ))}
    </Section>
  );
}

function Edit({ lead, reload }) {
  const [f, setF] = useState(lead);
  useEffect(() => setF(lead), [lead]);
  const save = async (patch) => {
    try { await api.put(`/leads/${lead.lead_id}`, patch); toast.success("Lead updated"); reload(); } catch (e) { err(e, "Could not update"); }
  };
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-3">
        <div className="flex-1"><Label className="text-xs text-slate-400">Status</Label>
          <Select value={lead.status} onValueChange={(v) => save({ status: v })}>
            <SelectTrigger data-testid="lead-status-select" className={`${field} capitalize`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#171A21] border-amber-500/20 text-slate-100">{STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
          </Select></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2"><Label className="text-xs text-slate-400">Name</Label><Input data-testid="lead-edit-name" value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} className={field} /></div>
        <div><Label className="text-xs text-slate-400">Email</Label><Input data-testid="lead-edit-email" value={f.email || ""} onChange={(e) => setF({ ...f, email: e.target.value })} className={field} /></div>
        <div><Label className="text-xs text-slate-400">Phone</Label><Input data-testid="lead-edit-phone" value={f.phone || ""} onChange={(e) => setF({ ...f, phone: e.target.value })} className={field} /></div>
        <div className="col-span-2"><Label className="text-xs text-slate-400">Notes</Label><Textarea data-testid="lead-edit-notes" value={f.notes || ""} onChange={(e) => setF({ ...f, notes: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" rows={2} /></div>
      </div>
      <Button data-testid="lead-save-button" size="sm" onClick={() => save({ name: f.name, email: f.email || "", phone: f.phone || "", notes: f.notes || "" })} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full h-8 text-xs">Save changes</Button>
    </div>
  );
}

export function LeadDetail({ leadId, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [summarizing, setSummarizing] = useState(false);
  const load = () => leadId && api.get(`/leads/${leadId}`).then(({ data }) => setData(data)).catch(() => {});
  useEffect(() => { setData(null); load(); }, [leadId]); // eslint-disable-line react-hooks/exhaustive-deps
  const reload = () => { load(); onChanged(); };
  const resummarize = async () => {
    setSummarizing(true);
    try { await api.post(`/leads/${leadId}/summarize`); reload(); } catch (e) { err(e, "Could not summarize"); } finally { setSummarizing(false); }
  };
  const del = async () => { await api.delete(`/leads/${leadId}`); toast.success("Lead archived"); onChanged(); onClose(); };
  const lead = data?.lead;
  return (
    <Sheet open={!!leadId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="bg-[#13161D] border-amber-500/20 text-slate-100 w-full sm:max-w-xl overflow-y-auto" data-testid="lead-detail-sheet">
        {!lead ? <div className="text-slate-500 text-sm mt-10">Loading…</div> : (<>
          <SheetHeader><SheetTitle className="font-serif text-2xl text-slate-100">{lead.name}</SheetTitle>
            <p className="text-xs text-slate-500">Inquiry {new Date(lead.inquiry_date || lead.created_at).toLocaleString()} · via {lead.source}{data.customer && ` · Customer record ${data.customer.customer_id}`}</p></SheetHeader>
          <div className="mt-5"><Edit lead={lead} reload={reload} /></div>
          <Section title="AI conversation summary" testid="lead-summary-section">
            <p data-testid="lead-summary-text" className="text-sm text-slate-300 leading-relaxed">{lead.summary || "No summary yet."}</p>
            {lead.service_interests?.length > 0 && <div className="flex flex-wrap gap-1.5 mt-2">{lead.service_interests.map((s) => <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-200">{s}</span>)}</div>}
            {lead.chat_session_ids?.length > 0 && <Button data-testid="lead-resummarize-button" size="sm" variant="outline" disabled={summarizing} onClick={resummarize} className="mt-3 h-7 text-xs bg-transparent border-amber-500/20 text-slate-300"><RefreshCw className={`w-3 h-3 mr-1 ${summarizing ? "animate-spin" : ""}`} />Refresh summary</Button>}
          </Section>
          <Section title={`Appointments (${data.bookings.length})`} testid="lead-bookings-section">
            {data.bookings.length === 0 ? <p className="text-xs text-slate-500">No appointments linked.</p> : data.bookings.map((b) => (
              <div key={b.booking_id} className="text-sm flex items-center gap-2 mb-1.5" data-testid={`lead-booking-${b.booking_id}`}><CalendarCheck className="w-4 h-4 text-gold" />{b.service} · {new Date(b.datetime).toLocaleString([], { dateStyle: "medium", timeStyle: "short", timeZone: b.timezone || undefined })} · <span className="capitalize text-slate-400">{b.status}</span> <span className="text-[10px] font-mono text-slate-600">{b.booking_id}</span></div>
            ))}
          </Section>
          <Section title={`Conversations (${data.conversations.length})`} testid="lead-conversations-section">
            {data.conversations.length === 0 ? <p className="text-xs text-slate-500">No linked chats.</p> : data.conversations.map((c) => (
              <details key={c.session_id} className="rounded-lg border border-amber-500/10 p-2.5 mb-2" data-testid={`lead-conversation-${c.session_id}`}>
                <summary className="text-xs text-slate-400 cursor-pointer">Chat {c.session_id.slice(0, 14)} · {c.messages.length} messages</summary>
                <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto">{c.messages.map((m, i) => <div key={i} className={`text-xs whitespace-pre-line ${m.role === "user" ? "text-amber-200" : "text-slate-400"}`}><b className="uppercase text-[10px] mr-1">{m.role === "user" ? "Customer" : "AI"}</b>{m.content}</div>)}</div>
              </details>
            ))}
          </Section>
          <Consent lead={lead} reload={reload} />
          <Drafts lead={lead} reload={reload} />
          <History lead={lead} />
          <div className="border-t border-amber-500/10 pt-5 mt-5"><Button data-testid="lead-delete-button" size="sm" variant="outline" onClick={del} className="bg-transparent border-red-500/20 text-red-400 hover:bg-red-500/10 rounded-full h-8 text-xs"><Trash2 className="w-3.5 h-3.5 mr-1" />Archive lead</Button></div>
        </>)}
      </SheetContent>
    </Sheet>
  );
}
