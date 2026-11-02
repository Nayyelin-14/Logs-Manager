import { registerUser, veridyOtp } from "./register";
import { confirmPassword } from "./password";
import { loginUser, logout } from "./session";

export { registerUser, veridyOtp, confirmPassword, loginUser, logout };

export default {
  loginUser,
  registerUser,
  logout,
  veridyOtp,
  confirmPassword,
};
