import { useEffect, useRef, useState } from "react";
import { Send, Bot, Code2, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { API } from "@/lib/api";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/dashboard/parts";
import { SwitchToDemoButton } from "@/dashboard/DemoMode";

export default function ChatAssistant() {
  const { user, business, setBusiness } = useAuth();
  const [messages, setMessages] = useState([{ role: "assistant", content: `Hi! I'm the AI assistant for ${business?.name || "your business"}. Ask me anything a customer might ask.` }]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [consent, setConsent] = useState({ email: false, sms: false });
  const [savedLead, setSavedLead] = useState(null);
  const sessionId = useRef("preview_" + Math.random().toString(36).slice(2));
  const listRef = useRef(null);
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }); }, [messages]);
  const embed = `<script src="${window.location.origin}/widget.js" data-business="${user?.business_id}"></script>`;

  const send = async () => {
    if (!input.trim() || streaming) return;
    const msg = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
    const sendConsent = { email: consent.email || undefined, sms: consent.sms || undefined };
    setConsent({ email: false, sms: false });
    setStreaming(true);
    try {
      const token = localStorage.getItem("lb_token");
      const res = await fetch(`${API}/chat/stream`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        credentials: "include", body: JSON.stringify({ session_id: sessionId.current, message: msg, consent: sendConsent }),
      });
      if (!res.ok) {
        let detail = "The assistant is unavailable right now. Please try again.";
        try { const err = await res.json(); if (err?.detail) detail = err.detail; } catch {}
        setMessages((m) => { const copy = [...m]; copy[copy.length - 1] = { role: "assistant", content: detail, error: true }; return copy; });
        toast.error(detail);
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let acc = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        setMessages((m) => { const copy = [...m]; copy[copy.length - 1] = { role: "assistant", content: acc }; return copy; });
      }
    } catch {
      setMessages((m) => { const copy = [...m]; copy[copy.length - 1] = { role: "assistant", content: "Something went wrong reaching the assistant. Please try again.", error: true }; return copy; });
      toast.error("Chat failed");
    }
    finally {
      setStreaming(false);
      api.get(`/chat/session-lead/${sessionId.current}`).then(({ data }) => setSavedLead(data.lead)).catch(() => {});
    }
  };

  const toggleChat = async (v) => {
    const { data } = await api.put("/business", { chat_enabled: v });
    setBusiness(data);
    toast.success(`Chat assistant ${v ? "enabled" : "disabled"}`);
  };

  if (!user?.business_id) {
    return (
      <div>
        <PageHeader eyebrow="Assistant" title="Website Chat Assistant" desc="Preview your embeddable AI chat widget and copy the install snippet for your website." />
        <div data-testid="chat-no-business-note" className="lux-card p-8 flex items-start gap-4 max-w-2xl">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center shrink-0"><Bot className="w-5 h-5 text-gold" /></div>
          <div>
            <div className="font-display font-semibold">Chat needs a business account</div>
            <p className="text-sm text-slate-400 mt-1">This account isn't linked to a business workspace, so there's no assistant to preview.</p>
            {user?.role === "admin" && <SwitchToDemoButton className="mt-4" />}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader eyebrow="Assistant" title="Website Chat Assistant" desc="Preview your embeddable AI chat widget and copy the install snippet for your website." />
      <div className="grid items-start gap-6 md:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="lux-card p-0 flex flex-col h-[520px] w-full max-w-[380px] min-w-0">
          <div className="px-5 py-4 border-b border-amber-500/15 flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center"><Bot className="w-4 h-4 text-gold" /></div>
            <div className="flex-1"><div className="font-display font-semibold text-sm">{business?.name} Assistant</div><div className="text-xs text-emerald-400">Online · Powered by AI</div></div>
          </div>
          {savedLead && (
            <div data-testid="chat-saved-lead" className="mx-4 mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-300">
              Saved to CRM: <b>{savedLead.name}</b> · {savedLead.email || savedLead.phone} · status {savedLead.status} — visible in Leads now.
            </div>
          )}
          <div ref={listRef} data-testid="chat-message-list" className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-line leading-relaxed ${m.role === "user" ? "bg-gold text-[#0B0D12]" : "bg-[#171A21] border border-amber-500/15 text-slate-200"}`}>
                  {m.content || <span className="text-slate-500 animate-pulse">thinking…</span>}
                </div>
              </div>
            ))}
          </div>
          <div className="p-4 border-t border-amber-500/15 flex gap-2">
            <Input data-testid="chat-input" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Ask the assistant…" className="bg-[#171A21] border-amber-500/20" />
            <Button data-testid="chat-send-button" onClick={send} disabled={streaming} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-lg px-4"><Send className="w-4 h-4" /></Button>
          </div>
          <div className="px-4 pb-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-slate-500">
            {[["email", "Email me offers & updates"], ["sms", "Text me offers & updates"]].map(([k, l]) => (
              <label key={k} className="flex items-center gap-1.5 cursor-pointer"><input type="checkbox" data-testid={`chat-consent-${k}`} checked={!!consent[k]} onChange={(e) => setConsent({ ...consent, [k]: e.target.checked })} className="accent-[#D6B76C]" />{l} <span className="text-slate-600">(optional)</span></label>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          <div className="lux-card p-6">
            <div className="flex items-center justify-between">
              <div><div className="font-display font-semibold">Chat Widget</div><div className="text-xs text-slate-500">Show the assistant on your website</div></div>
              <Switch data-testid="chat-enabled-toggle" checked={!!business?.chat_enabled} onCheckedChange={toggleChat} />
            </div>
          </div>
          <div className="lux-card p-6">
            <div className="flex items-center gap-2 mb-3"><Code2 className="w-4 h-4 text-gold" /><span className="font-display font-semibold">Embed Snippet</span></div>
            <p className="text-xs text-slate-500 mb-3">Paste this before the closing &lt;/body&gt; tag of your website.</p>
            <div className="bg-black/40 rounded-lg p-4 border border-amber-500/10 font-mono text-xs text-amber-200 break-all">{embed}</div>
            <Button data-testid="copy-embed-button" onClick={() => { navigator.clipboard.writeText(embed); toast.success("Snippet copied"); }} variant="outline" className="mt-3 bg-transparent border-amber-500/20 text-slate-300 hover:bg-amber-500/10 rounded-lg h-9 text-sm"><Copy className="w-4 h-4 mr-2" /> Copy Snippet</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
