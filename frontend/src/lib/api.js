import axios from "axios";

// Netlify proxies /api to the existing backend; an explicit URL still supports other hosts.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lb_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
