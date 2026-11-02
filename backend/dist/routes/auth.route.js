"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const isAuth_1 = __importDefault(require("../middleware/isAuth"));
const auth_con_1 = require("../controllers/auth/auth.con");
const authCheck_1 = require("../controllers/auth/authCheck");
const router = express_1.default.Router();
// Login
router.post("/login", auth_con_1.loginUser);
router.post("/register", auth_con_1.registerUser);
router.post("/verify-Otp", auth_con_1.veridyOtp);
router.post("/confirm-password", auth_con_1.confirmPassword);
router.post("/logout", isAuth_1.default, auth_con_1.logout);
router.get("/auth-check", isAuth_1.default, authCheck_1.authcheck);
exports.default = router;
//# sourceMappingURL=auth.route.js.map