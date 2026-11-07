import axios from "axios";

export const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-type": "application/json",
  },
  withCredentials: true,
});

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
export const authAPI = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-type": "application/json",
  },
  withCredentials: true,
});

export const adminApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

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
