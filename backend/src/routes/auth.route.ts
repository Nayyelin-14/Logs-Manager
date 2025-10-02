import express from "express";

import authMiddleware from "../middleware/isAuth";
import {
  confirmPassword,
  loginUser,
  logout,
  registerUser,
  veridyOtp,
} from "../controllers/auth/auth.con";
import { authcheck } from "../controllers/auth/authCheck";

const router = express.Router();

// Login
router.post("/login", loginUser);
router.post("/register", registerUser);
router.post("/verify-Otp", veridyOtp);
router.post("/confirm-password", confirmPassword);

router.post("/logout", authMiddleware, logout);
router.get("/auth-check", authMiddleware, authcheck);

export default router;
