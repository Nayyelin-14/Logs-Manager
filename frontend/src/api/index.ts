import axios, { type InternalAxiosRequestConfig } from "axios";

import { resolveApiBase } from "../lib/apiBase";

const apiBase = resolveApiBase();

function getCookie(name: string): string | undefined {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${escapedName}=([^;]*)`)
  );
  return match ? decodeURIComponent(match[1]) : undefined;
}

function attachCsrfToken(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const token = getCookie("XSRF-TOKEN");
  if (token) {
    config.headers["X-XSRF-TOKEN"] = token;
  }
  return config;
}

export const API = axios.create({
  baseURL: apiBase,
  headers: {
    "Content-type": "application/json",
  },
  withCredentials: true,
});

API.interceptors.request.use(attachCsrfToken);

API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = `/login?redirect=${encodeURIComponent(
        window.location.pathname
      )}`;
    }

    return Promise.reject(error);
  }
);
export const adminApi = axios.create({
  baseURL: apiBase,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

adminApi.interceptors.request.use(attachCsrfToken);

adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 403) {
      window.location.href = "/login";
    }
    if (error.response?.status === 401) {
      window.location.href = `/login?redirect=${encodeURIComponent(
        window.location.pathname
      )}`;
    }
    return Promise.reject(error);
  }
);
export default API;
// Promise.reject(error) မရေးဘူးဆိုရင်	catch မသွားဘူး၊ app က မသိဘူး error တက်တယ်လို့
// Promise.reject(error) ရေးမယ်	error ကို ပြန်ပေးတယ်၊ catch မှာသိတယ် — handle လုပ်လို့ရတယ် //ဒီမှာ API.get() မှာ အမှားတက်ရင် catch ထဲမှာမရောက်ဘူးနော် အမှားကို reject မလုပ်ရင်။
// ဒါကြောင့် Promise.reject(error) လုပ်ဖို့လိုတယ်။
// ဒီအရာက try/catch ကို “အမှားတက်တယ်” ဆိုပြီး သတိပေးတာပါ။
