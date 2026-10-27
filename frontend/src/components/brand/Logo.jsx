const sizes = { sm: [22, "text-base"], base: [24, "text-lg"], lg: [26, "text-lg"], xl: [28, "text-xl"], "2xl": [32, "text-2xl"] };

export function EMark({ size = 28, framed = false, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="vg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F5E6BF" /><stop offset="0.55" stopColor="#D6B76C" /><stop offset="1" stopColor="#A8894A" />
        </linearGradient>
      </defs>
      {framed && <rect x="1" y="1" width="62" height="62" rx="15" fill="#0B0D12" stroke="#D6B76C" strokeOpacity="0.35" strokeWidth="1.5" />}
      <path d="M14 14H47V23H24V28H43V37H24V42H47V51H14Z" fill="url(#vg)" />
      <polygon points="47,6 52,11 47,16 42,11" fill="#D6B76C" />
    </svg>
  );
}

export function Logo({ size = "xl", sub, className = "" }) {
  const [px, text] = sizes[size] || sizes.xl;
  return (
    <span data-testid="brand-logo" className={`inline-flex items-center gap-2.5 ${className}`}>
      <EMark size={px} />
      <span className="flex flex-col leading-none">
        <span className={`font-serif ${text} font-semibold tracking-[0.04em] text-[#F5F1E8]`}>Eazy’s</span>
        <span className="mt-1 text-[10px] font-sans font-semibold uppercase tracking-[0.18em] gold-gradient-text">Business AI</span>
        {sub && <span className="mt-1 text-[10px] font-sans uppercase tracking-[0.32em] text-[#89919E]">{sub}</span>}
      </span>
    </span>
  );
}
