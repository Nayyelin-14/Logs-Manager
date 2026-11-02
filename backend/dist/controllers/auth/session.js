"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logout = exports.loginUser = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const PrismaClient_1 = require("../../config/PrismaClient");
const loginUser = async (req, res, next) => {
    try {
        const email = req.body.email?.trim();
        const inputPassword = req.body.password?.trim();
        if (!email || !inputPassword)
            return res
                .status(400)
                .json({ message: "Email and password are required" });
        // Find user by email
        const user = await (0, auth_service_1.getUserByEmail)(email);
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        if (user?.status && user.status !== "ACTIVE") {
            return res.status(403).json({ message: "This account is not active." });
        }
        // Check password
        const isPasswordValid = await bcryptjs_1.default.compare(inputPassword, user?.password);
        if (!isPasswordValid)
            return res.status(401).json({ message: "Invalid credentials" });
        const Payload = {
            userId: user?.id,
            username: user?.username,
            email: user?.email,
            tenant: user?.tenant,
            role: user?.role,
        };
        const generateAccessToken = jsonwebtoken_1.default.sign(Payload, process.env.ACCESS_TOKEN_SECRET, { expiresIn: 60 * 15 });
        const generateRefreshToken = jsonwebtoken_1.default.sign(Payload, process.env.REFRESH_TOKEN_SECRET, { expiresIn: "30d" });
        const option = {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: (process.env.NODE_ENV === "production" ? "none" : "strict"),
        };
        const { password, ...safeUser } = user;
        return res
            .cookie("accessToken", generateAccessToken, {
            ...option,
            maxAge: 15 * 60 * 1000, // 15 minutes
        })
            .cookie("refreshToken", generateRefreshToken, {
            ...option,
            maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
        })
            .status(201)
            .json({
            message: `Welcome back!!! ${user?.username}`,
            userData: safeUser,
        });
    }
    catch (error) {
        return res.status(500).json({ message: error?.message, isSuccess: false });
    }
};
exports.loginUser = loginUser;
const logout = async (req, res, next) => {
    if (!req.user || !req.user.userId) {
        return res.status(401).json({ message: "Unauthorized" });
    }
    const userId = req.user.userId;
    const user = await PrismaClient_1.prisma.user.findUnique({
        where: {
            id: userId,
        },
    });
    if (!user)
        return res.status(404).json({ message: "User not found" });
    const option = {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: process.env.NODE_ENV === "production" ? "none" : "strict",
    };
    return res
        .clearCookie("refreshToken", option)
        .clearCookie("accessToken", option)
        .json({
        message: "Loggedout successfully",
    });
};
exports.logout = logout;
//# sourceMappingURL=session.js.map