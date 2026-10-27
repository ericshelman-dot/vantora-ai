import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AuthCallback from "@/pages/AuthCallback";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Privacy from "@/pages/Privacy";
import Terms from "@/pages/Terms";
import DashboardLayout from "@/dashboard/DashboardLayout";
import Overview from "@/dashboard/Overview";
import PhoneReception from "@/dashboard/PhoneReception";
import ChatAssistant from "@/dashboard/ChatAssistant";
import Leads from "@/dashboard/Leads";
import Appointments from "@/dashboard/Appointments";
import Customers from "@/dashboard/Customers";
import Customization from "@/dashboard/Customization";
import Billing from "@/dashboard/Billing";
import Settings from "@/dashboard/Settings";
import AdminDashboard from "@/admin/AdminDashboard";
import SalesPilot from "@/dashboard/SalesPilot";

function Protected({ children, adminOnly }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-[#0B0D12] flex items-center justify-center text-gold font-mono text-sm animate-pulse">LOADING…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/admin" element={<Protected adminOnly><AdminDashboard /></Protected>} />
      <Route path="/dashboard" element={<Protected><DashboardLayout /></Protected>}>
        <Route index element={<Overview />} />
        <Route path="phone" element={<PhoneReception />} />
        <Route path="chat" element={<ChatAssistant />} />
        <Route path="leads" element={<Leads />} />
        <Route path="sales" element={<SalesPilot />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="customers" element={<Customers />} />
        <Route path="customization" element={<Customization />} />
        <Route path="billing" element={<Billing />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster position="bottom-right" theme="dark" />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
