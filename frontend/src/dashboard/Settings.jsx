import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/dashboard/parts";

export default function Settings() {
  const { user, business, setBusiness } = useAuth();
  const [form, setForm] = useState({});
  useEffect(() => { if (business) setForm(business); }, [business]);

  const toggle = async (key, v) => {
    const { data } = await api.put("/business", { [key]: v });
    setBusiness(data); setForm(data);
    toast.success("Settings updated");
  };
  const saveName = async () => {
    const { data } = await api.put("/business", { name: form.name });
    setBusiness(data);
    toast.success("Business name updated");
  };

  const toggles = [
    { key: "phone_reception_enabled", label: "AI Phone Reception", desc: "Let the AI answer inbound calls 24/7" },
    { key: "chat_enabled", label: "Website Chat Assistant", desc: "Show the embeddable chat widget on your site" },
    { key: "follow_up_consent", label: "Follow-up Consent", desc: "Permit email & SMS follow-ups to leads" },
  ];

  return (
    <div>
      <PageHeader eyebrow="Preferences" title="Settings" desc="Manage your workspace, assistant features, and account." />
      <div className="lux-card p-6 mb-6">
        <h3 className="font-display text-lg font-semibold mb-4">Business Profile</h3>
        <div className="flex items-end gap-3 max-w-md">
          <div className="flex-1"><Label className="text-slate-300">Business name</Label><Input data-testid="settings-business-name" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5 bg-[#171A21] border-amber-500/20" /></div>
          <Button data-testid="settings-save-name" onClick={saveName} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full">Save</Button>
        </div>
        <div className="mt-4 text-sm text-slate-500">Account email: <span className="text-slate-300">{user?.email}</span></div>
      </div>
      <div className="lux-card p-6">
        <h3 className="font-display text-lg font-semibold mb-4">Assistant Features</h3>
        <div className="space-y-5">
          {toggles.map((t) => (
            <div key={t.key} className="flex items-center justify-between border-b border-amber-500/10 pb-4 last:border-0 last:pb-0">
              <div><div className="font-medium text-sm">{t.label}</div><div className="text-xs text-slate-500">{t.desc}</div></div>
              <Switch data-testid={`settings-toggle-${t.key}`} checked={!!form[t.key]} onCheckedChange={(v) => toggle(t.key, v)} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
