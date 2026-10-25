import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/dashboard/parts";

const blank = { name: "", company: "", service: "", source: "", need: "", email: "", decision_maker: false, timing: "unknown", permission: "unknown", permission_evidence: "" };
const field = "w-full rounded border border-amber-500/20 bg-[#141720] px-3 py-2 text-sm text-slate-100";
const button = "rounded border border-amber-500/30 px-3 py-2 text-sm text-amber-200 hover:bg-amber-500/10 disabled:opacity-40";

export default function SalesPilot() {
  const [mode, setMode] = useState("demo");
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState("");
  const [outcome, setOutcome] = useState("interested");
  const [stage, setStage] = useState("qualified");
  const [evidence, setEvidence] = useState("");
  const [revenue, setRevenue] = useState("0");
  const [start, setStart] = useState("");
  const [setup, setSetup] = useState({ business_name: "", owner_name: "", services: "", timezone: "America/New_York", consent_evidence: "", owner_consented: false });
  const load = async () => {
    const { data: next } = await api.get(`/sales-pilot?mode=${mode}`);
    setData(next);
  };
  useEffect(() => {
    let active = true;
    setData(null); setSelected(null); setForm(blank); setError("");
    api.get(`/sales-pilot?mode=${mode}`).then(({ data: next }) => { if (active) setData(next); })
      .catch(e => { if (active) setError(e.response?.data?.detail || "Could not load workspace."); });
    return () => { active = false; };
  }, [mode]);
  const p = data?.prospects.find(x => x.prospect_id === selected);
  useEffect(() => { setMessage(p?.draft?.message || ""); setResponse(""); setEvidence(""); setStart(""); }, [selected, p?.revision]);
  const run = async (work) => {
    setBusy(true); setError("");
    try { await work(); await load(); }
    catch (e) { setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Please check your entries and try again."); }
    finally { setBusy(false); }
  };
  const action = (kind, values = {}) => run(() => api.post(`/sales-pilot/prospects/${p.prospect_id}/actions?mode=${mode}`, { kind, expected_revision: p.revision, ...values }));
  const input = (label, key, values, setter, type = "text") => <label className="block text-sm text-slate-400">{label}<input required={!["email", "need", "permission_evidence"].includes(key)} type={type} className={`${field} mt-1`} value={values[key]} onChange={e => setter({ ...values, [key]: e.target.value })} /></label>;

  return <div data-testid="sales-pilot">
    <PageHeader eyebrow="Owner controlled pilot" title="Sales & Marketing" desc="Qualify prospects, review outreach drafts and track outcomes. No messages are sent and no calendar events are created." />
    <div className="flex flex-wrap gap-3 mb-5">
      <button className={button} disabled={mode === "demo" || busy} onClick={() => setMode("demo")}>Demo sandbox</button>
      <button className={button} disabled={mode === "live" || busy} onClick={() => setMode("live")}>Live pilot · consent required</button>
      <span className="text-sm text-amber-300 self-center">{mode === "demo" ? "Fictional data only · separate demo storage" : "Business data · owner authorization required"}</span>
      {mode === "live" && data?.ready && <button className={button} disabled={busy} onClick={() => run(() => api.post("/sales-pilot/pause"))}>Pause live authorization</button>}
    </div>
    <div className="lux-card p-4 mb-5 text-sm text-slate-400">Sending disabled · Calendar not connected · Free local templates · No paid AI calls. Live business data requires the owner's explicit authorization.</div>
    {error && <div role="alert" className="p-4 mb-4 border border-red-500/40 text-red-300">{error}</div>}
    {data && <>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">{[["Prospects", data.report.total], ["Qualified ≥50", data.report.qualified], ["Responded", data.report.responses], ["Won", data.report.won], ["Conversion", `${data.report.conversion_percent}%`]].map(([label, value]) => <div key={label} className="lux-card p-4"><p className="text-xs text-slate-400">{label}</p><strong className="text-2xl">{value}</strong></div>)}</div>
      <p className="text-xs text-slate-400 mb-6">Manually recorded outcomes. Conversion = won ÷ all prospects in this mode. Recorded value: {(data.report.recorded_revenue_cents / 100).toFixed(2)} USD; no payments collected. Report covers up to {data.safeguards.report_limit} prospects.</p>
      {!data.ready ? <form className="lux-card p-5 space-y-4" onSubmit={e => { e.preventDefault(); run(() => api.post("/sales-pilot/setup", setup)); }}>
        <h2 className="text-xl">Authorize a business pilot</h2><p className="text-sm text-slate-400">Obtain the owner's explicit permission first. Record who agreed, when, and the approved use. Do not enter customer data here. This authorizes this workspace's pilot only; calendar access requires a separate authorization.</p>
        {input("Business name", "business_name", setup, setSetup)}{input("Consenting owner", "owner_name", setup, setSetup)}{input("Approved services / offer", "services", setup, setSetup)}{input("Timezone", "timezone", setup, setSetup)}{input("Consent evidence and permitted scope", "consent_evidence", setup, setSetup)}
        <label className="block text-sm"><input required type="checkbox" checked={setup.owner_consented} onChange={e => setSetup({ ...setup, owner_consented: e.target.checked })} /> The business owner explicitly consented to this pilot and its data use.</label>
        <button className={button} disabled={busy || !setup.owner_consented}>Save owner authorization</button>
      </form> : <>
        <div className="grid xl:grid-cols-2 gap-6">
          <section className="lux-card p-5 space-y-4">
            <h2 className="text-xl">Prospect pipeline</h2>
            {mode === "demo" && <button disabled={busy} className={button} onClick={() => run(async () => {
              const { data: created } = await api.post("/sales-pilot/prospects?mode=demo", { ...blank, name: "Alex Example", company: "Fictional Salon", email: "alex@example.com", service: "Vantora appointment and inquiry demo", source: "Synthetic example", need: "Review missed inquiries and appointment requests", timing: "this_month", decision_maker: true, permission: "granted", permission_evidence: "Synthetic demo permission; no real person" }); setSelected(created.prospect_id);
            })}>Add fictional salon prospect</button>}
            {data.prospects.length === 0 && <p className="text-slate-400 text-sm">No prospects yet. Add a fictional example or an owner-approved prospect.</p>}
            <div className="space-y-2 max-h-80 overflow-y-auto">{data.prospects.map(row => <button key={row.prospect_id} onClick={() => setSelected(row.prospect_id)} className={`w-full text-left p-3 rounded border ${selected === row.prospect_id ? "border-amber-400" : "border-white/10"}`}><strong>{row.company}</strong><p className="text-sm text-slate-400">{row.name} · {row.stage} · {row.qualification.score}/100 · {row.permission}</p></button>)}</div>
            <details className="border-t border-white/10 pt-4"><summary>Add prospect manually</summary><form className="space-y-3 pt-4" onSubmit={e => { e.preventDefault(); run(async () => { const { data: created } = await api.post(`/sales-pilot/prospects?mode=${mode}`, form); setSelected(created.prospect_id); setForm(blank); }); }}>
              <h3>Add prospect</h3>{input("Contact name", "name", form, setForm)}{input("Business", "company", form, setForm)}{input("Proposed service / demo", "service", form, setForm)}{input("Source", "source", form, setForm)}{input("Business need", "need", form, setForm)}{input("Email (optional; example.com in demo)", "email", form, setForm, "email")}
              <label className="block text-sm"><input type="checkbox" checked={form.decision_maker} onChange={e => setForm({ ...form, decision_maker: e.target.checked })} /> Decision maker confirmed</label>
              <label className="block text-sm">Timing<select className={field} value={form.timing} onChange={e => setForm({ ...form, timing: e.target.value })}><option value="unknown">Unknown</option><option value="later">Later</option><option value="this_month">This month</option></select></label>
              <label className="block text-sm">Outreach permission<select className={field} value={form.permission} onChange={e => setForm({ ...form, permission: e.target.value })}><option value="unknown">Unknown — outreach blocked</option><option value="granted">Granted with evidence</option><option value="opted_out">Opted out</option></select></label>
              {input("Permission evidence", "permission_evidence", form, setForm)}<button className={button} disabled={busy}>Save prospect</button>
            </form></details>
          </section>
          <section className="lux-card p-5 space-y-5">{p ? <>
            <h2 className="text-xl">{p.company}</h2><p className="text-sm text-slate-400">Qualification: {p.qualification.score}/100. {p.qualification.reasons.join(" · ") || "More information needed"}. Rules award 25 points for need, decision maker, near-term timing and permission.</p>
            <h3>Personalized outreach draft</h3><button className={button} disabled={busy || p.permission !== "granted"} onClick={() => action("draft")}>Prepare free draft</button>
            {p.draft && <><textarea aria-label="Outreach draft" rows={6} className={field} value={message} disabled={p.draft.status !== "pending"} onChange={e => setMessage(e.target.value)} /><p className="text-sm text-amber-300">{p.draft.status} · Not sent</p><div className="flex gap-2"><button className={button} disabled={busy || p.draft.status !== "pending" || !message.trim()} onClick={() => action("edit_draft", { text: message })}>Save edits</button><button className={button} disabled={busy || p.draft.status !== "pending" || message !== p.draft.message} onClick={() => action("approve_draft")}>Approve saved draft · no sending</button></div></>}
            <div className="border-t border-white/10 pt-4 space-y-3"><h3>Record response</h3><textarea aria-label="Response text" className={field} value={response} onChange={e => setResponse(e.target.value)} /><select aria-label="Response outcome" className={field} value={outcome} onChange={e => setOutcome(e.target.value)}><option value="interested">Interested</option><option value="not_now">Not now</option><option value="opt_out">Opt out — blocks drafts</option></select><button className={button} disabled={busy || !response.trim()} onClick={() => action("response", { text: response, outcome })}>Record response</button>{p.responses?.map((r, i) => <p key={i} className="text-sm text-slate-400">{r.outcome}: {r.text}</p>)}</div>
            <div className="border-t border-white/10 pt-4 space-y-3"><h3>Appointment / demo proposal</h3><p className="text-sm text-slate-400">Choose a tentative time in your device's local timezone. Calendar authorization, availability checks and owner confirmation are required before an event can be booked. This only records a proposal.</p><input aria-label="Proposed appointment time" type="datetime-local" className={field} value={start} onChange={e => setStart(e.target.value)} /><button className={button} disabled={busy || !start} onClick={() => action("booking_proposal", { starts_at: new Date(start).toISOString() })}>Save proposal · awaiting calendar access</button>{p.booking_proposal && <p className="text-sm text-amber-300">{p.booking_proposal.starts_at} · Awaiting calendar authorization · No event created</p>}</div>
            <div className="border-t border-white/10 pt-4 space-y-3"><h3>Manually record outcome</h3><select aria-label="Pipeline stage" className={field} value={stage} onChange={e => setStage(e.target.value)}>{["new", "qualified", "contacted", "responded", "won", "lost"].map(x => <option key={x}>{x}</option>)}</select><input aria-label="Outcome evidence" placeholder="Evidence / source for outcome" className={field} value={evidence} onChange={e => setEvidence(e.target.value)} />{stage === "won" && <label className="block text-sm">Recorded value in USD<input type="number" min="0" max="1000000" step="0.01" className={field} value={revenue} onChange={e => setRevenue(e.target.value)} /></label>}<button disabled={busy} className={button} onClick={() => action("stage", { stage, text: evidence, revenue_cents: Math.round(Number(revenue) * 100) })}>Record outcome</button></div>
            <details className="border-t border-white/10 pt-4"><summary>Audit history ({p.audit.length})</summary>{p.audit.map(e => <p key={e.event_id} className="text-xs text-slate-400 mt-2">{e.at} · {e.action} · {e.actor}</p>)}</details>
          </> : <p className="text-slate-400">Select a prospect to qualify, draft outreach, record replies and propose a demo.</p>}</section>
        </div>
      </>}
    </>}
  </div>;
}
