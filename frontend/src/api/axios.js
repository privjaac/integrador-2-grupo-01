import axios from "axios";

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
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
    const detail = error?.response?.data?.detail;
    error.userMessage = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(", ")
      : detail || error.message;
    return Promise.reject(error);
  },
);

export default axiosInstance;
