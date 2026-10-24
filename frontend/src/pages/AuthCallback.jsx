import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const hash = window.location.hash;
    const sid = new URLSearchParams(hash.replace("#", "")).get("session_id");
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sid });
        localStorage.setItem("lb_token", data.token);
        window.history.replaceState(null, "", "/dashboard");
        await refresh();
        navigate("/dashboard", { replace: true });
      } catch {
        navigate("/login", { replace: true });
      }
    })();
  }, [navigate, refresh]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0B0D12]">
      <div className="text-gold font-mono text-sm tracking-widest animate-pulse">AUTHENTICATING…</div>
    </div>
  );
}
