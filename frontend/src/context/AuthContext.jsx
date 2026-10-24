import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
      setBusiness(data.business);
    } catch {
      setUser(null);
      setBusiness(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    refresh();
  }, [refresh]);

  const applyAuth = (data) => {
    localStorage.setItem("lb_token", data.token);
    setUser(data.user);
  };

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    applyAuth(data);
    await refresh();
    return data.user;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    applyAuth(data);
    await refresh();
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("lb_token");
    setUser(null);
    setBusiness(null);
  };

  const enterDemo = async () => { await api.post("/admin/demo-workspace/enter"); await refresh(); };
  const exitDemo = async () => { await api.post("/admin/demo-workspace/exit"); await refresh(); };

  return (
    <AuthContext.Provider value={{ user, business, loading, login, register, logout, refresh, setBusiness, enterDemo, exitDemo }}>
      {children}
    </AuthContext.Provider>
  );
}
