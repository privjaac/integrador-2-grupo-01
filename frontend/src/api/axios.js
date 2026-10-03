import axios from "axios";
import { normalizeApiError } from "./errorMessage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

axiosInstance.interceptors.request.use((config) => {
  const token = window.__elisa_token__;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    error.userMessage = normalizeApiError(error);
    return Promise.reject(error);
  },
);

export default axiosInstance;
