import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

export enum authStatus {
  otp = "otp",
  confirm = "confirm",
  verify = "verify",
  reset = "reset",
  none = "none",
  change = "change",
}
export enum roleStatus {
  user = "USER",
  admin = "ADMIN",
}

type State = {
  email: string | null;
  username: string | null;
  tenant: string | null;
  token: string | null;
  status: authStatus;
  role: roleStatus | null;
  message: string | null;
};

const initialState: State = {
  email: null,
  username: null,
  tenant: null,
  token: null,
  status: authStatus.none,
  role: roleStatus.user,
  message: null,
};

type Actions = {
  //type for action to manipulate initialState
  setAuth: (
    email: string,
    username: string,
    tenant: string,
    role: roleStatus,
    status: authStatus,
    token: string,
    message: string
  ) => void;
  clearAuth: () => void;
  setTempMessage: (msg: string | null) => void;
};

const useAuthStore = create<State & Actions>()(
  // () - is required only when you're using middleware like persist, immer, or devtools. Here's why:
  // create()() → Needed when using middleware.  create() alone → Only fine when not using middleware.
  persist(
    immer((set) => ({
      ...initialState,

      setAuth: (email, username, tenant, role, status, token, message) =>
        set((state) => {
          state.email = email;
          state.username = username;
          state.tenant = tenant;
          state.role = role ?? initialState.role;
          state.status = status;
          state.token = token;
          state.message = message;
        }),
      clearAuth: () => set(initialState),
      setTempMessage: (msg: string | null) =>
        set((state) => {
          state.message = msg;
        }),
    })),
    {
      name: "auth-credentials",
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);

export default useAuthStore;

//persist is middleware
//  store ထဲက data တွေကို browser ထဲမှာ သိမ်းထားဖို့ အသုံးပြုတာပါ။
//  ပြန် reload လုပ်လိုက်ရင် data တွေမပျက်ဘဲ မူလအတိုင်း ပြန်ရအောင်လုပ်တယ်။

//immer is middleware
// state ကို mutate (ပြောင်းလဲ) လုပ်တာကို မခက်ဘဲ လုပ်နိုင်အောင် လုပ်ပေးတယ်။
// မူရင်း state ကိုမပျက်ဘဲ copy ဖြစ်ပြီး အသစ်ပြင်တာမျိုး။
