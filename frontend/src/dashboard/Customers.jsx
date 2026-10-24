import { useEffect, useState } from "react";
import { Plus, Trash2, Mail, Phone } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { PageHeader, Empty } from "@/dashboard/parts";

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", notes: "" });

  const load = () => api.get("/customers").then(({ data }) => setCustomers(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.name) return toast.error("Name required");
    await api.post("/customers", form);
    toast.success("Customer added");
    setOpen(false); setForm({ name: "", email: "", phone: "", notes: "" }); load();
  };
  const del = async (id) => { await api.delete(`/customers/${id}`); toast.success("Customer removed"); load(); };

  return (
    <div>
      <PageHeader eyebrow="CRM" title="Customers" desc="Your private, secure customer records."
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="add-customer-button" className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full px-6"><Plus className="w-4 h-4 mr-2" /> Add Customer</Button></DialogTrigger>
            <DialogContent className="bg-[#13161D] border-amber-500/20 text-slate-100">
              <DialogHeader><DialogTitle className="font-serif text-2xl">New Customer</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div><Label>Name</Label><Input data-testid="customer-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Email</Label><Input data-testid="customer-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                  <div><Label>Phone</Label><Input data-testid="customer-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
                </div>
                <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="bg-[#171A21] border-amber-500/20 mt-1" /></div>
              </div>
              <DialogFooter><Button data-testid="save-customer-button" onClick={add} className="bg-gold hover:bg-[#E3C88A] text-[#0B0D12] rounded-full">Save</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        } />
      {customers.length === 0 ? <Empty text="No customers yet." /> : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {customers.map((c) => (
            <div key={c.customer_id} className="lux-card p-5" data-testid={`customer-card-${c.customer_id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-gold font-display font-semibold">{c.name[0]}</div>
                  <div><div className="font-display font-semibold text-amber-100">{c.name}</div><div className="text-xs text-slate-500">{c.notes}</div></div>
                </div>
                <Button data-testid={`customer-delete-${c.customer_id}`} onClick={() => del(c.customer_id)} size="sm" variant="ghost" className="text-red-400 hover:bg-red-500/10"><Trash2 className="w-4 h-4" /></Button>
              </div>
              <div className="mt-4 space-y-1 text-xs text-slate-400">
                {c.email && <div className="flex items-center gap-2"><Mail className="w-3 h-3 text-gold" /> {c.email}</div>}
                {c.phone && <div className="flex items-center gap-2"><Phone className="w-3 h-3 text-gold" /> {c.phone}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
