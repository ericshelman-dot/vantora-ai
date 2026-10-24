import { useEffect, useState } from "react";
import { Save, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/dashboard/parts";
import { SchedulingSettings } from "@/dashboard/SchedulingSettings";

const fields = [
  { k: "name", label: "Business name", type: "input" },
  { k: "industry", label: "Industry / category", type: "input" },
  { k: "phone", label: "Contact phone", type: "input" },
  { k: "address", label: "Address", type: "input" },
  { k: "hours", label: "Business hours", type: "input" },
  { k: "services", label: "Services offered", type: "textarea" },
  { k: "faqs", label: "FAQs & policies", type: "textarea" },
  { k: "ai_greeting", label: "AI greeting message", type: "textarea" },
  { k: "ai_tone", label: "AI tone of voice", type: "input" },
];

export default function Customization() {
  const { business, setBusiness } = useAuth();
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (business) setForm(business); }, [business]);

  const save = async () => {
    setSaving(true);
    try {
      const payload = Object.fromEntries(fields.map((f) => [f.k, form[f.k] ?? ""]));
      const { data } = await api.put("/business", payload);
      setBusiness(data);
      toast.success("AI assistant updated");
    } catch { toast.error("Could not save"); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Configuration" title="AI Customization" desc="Teach your AI assistant about your business. These details power phone reception, chat, and follow-ups."
        action={<Button data-testid="customization-submit-button" onClick={save} disabled={saving} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full px-6"><Save className="w-4 h-4 mr-2" />{saving ? "Saving…" : "Save Changes"}</Button>} />
      <div className="lux-card p-6 mb-6 flex items-center gap-3">
        <Sparkles className="w-5 h-5 text-gold" />
        <p className="text-sm text-slate-400">The more detail you provide, the more accurately your AI represents your brand to every customer.</p>
      </div>
      <div className="grid md:grid-cols-2 gap-5">
        {fields.map((f) => (
          <div key={f.k} className={f.type === "textarea" ? "md:col-span-2" : ""}>
            <Label className="text-slate-300">{f.label}</Label>
            {f.type === "input" ? (
              <Input data-testid={`custom-${f.k}-input`} value={form[f.k] || ""} onChange={(e) => setForm({ ...form, [f.k]: e.target.value })} className="mt-1.5 bg-[#171A21] border-amber-500/20" />
            ) : (
              <Textarea data-testid={`custom-${f.k}-input`} rows={3} value={form[f.k] || ""} onChange={(e) => setForm({ ...form, [f.k]: e.target.value })} className="mt-1.5 bg-[#171A21] border-amber-500/20" />
            )}
          </div>
        ))}
      </div>
      <SchedulingSettings />
    </div>
  );
}
