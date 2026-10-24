export function PageHeader({ eyebrow, title, desc, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-8 flex-wrap">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-gold font-mono mb-2">{eyebrow}</p>
        <h1 className="font-serif text-3xl lg:text-4xl font-medium">{title}</h1>
        {desc && <p className="text-slate-400 text-sm mt-2 max-w-2xl">{desc}</p>}
      </div>
      {action}
    </div>
  );
}

export function SimBadge({ text = "Simulated" }) {
  return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">{text}</span>;
}

export function Empty({ text }) {
  return <div className="lux-card p-10 text-center text-slate-500 text-sm">{text}</div>;
}
