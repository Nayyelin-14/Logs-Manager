"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateNewToken = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const errorHandeling_1 = require("./errorHandeling");
const auth_service_1 = require("../services/auth.service");
const auth_utils_1 = require("./auth.utils");
const errrorcode_1 = require("../config/errrorcode");
const generateNewToken = async (oldRefreshToken, req, res, next) => {
    let decoded;
    if (!oldRefreshToken) {
        return next((0, errorHandeling_1.handleError)("Not an authenticated user", 401, errrorcode_1.errorCode.unthenticated));
    }
    try {
        decoded = jsonwebtoken_1.default.verify(oldRefreshToken, process.env.REFRESH_TOKEN_SECRET);
    }
    catch (error) {
        return next((0, errorHandeling_1.handleError)("Not an authenticated user", 401, errrorcode_1.errorCode.unthenticated));
    }
    const user = await (0, auth_service_1.getUserByEmail)(decoded.email);
    await (0, auth_utils_1.checkUserIfNotExist)(user);
    if (user?.status && user.status !== "ACTIVE") {
        return next((0, errorHandeling_1.handleError)("This account is not active.", 401, errrorcode_1.errorCode.unthenticated));
    }
    const validUser = user?.email === decoded.email;
    if (!validUser) {
        return next((0, errorHandeling_1.handleError)("Not an authenticated user", 401, errrorcode_1.errorCode.unthenticated));
    }
    const TokenPayload = {
        userId: user.id,
        username: user.username,
        email: user.email,
        tenant: user.tenant,
        role: user.role,
    };
    const NewAccessToken = jsonwebtoken_1.default.sign(TokenPayload, process.env.ACCESS_TOKEN_SECRET, { expiresIn: 60 * 15 });
    const NewRefreshToken = jsonwebtoken_1.default.sign(TokenPayload, process.env.REFRESH_TOKEN_SECRET, { expiresIn: "30d" });
    const option = {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: process.env.NODE_ENV === "production" ? "none" : "strict",
    };
    res
        .cookie("accessToken", NewAccessToken, {
        ...option,
        maxAge: 15 * 60 * 1000, // 15 minutes
    })
        .cookie("refreshToken", NewRefreshToken, {
        ...option,
        maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
    });
    req.cookies = {
        ...req.cookies,
        accessToken: NewAccessToken,
    };
    req.user = {
        userId: user.id,
        username: user.username ?? undefined,
        email: user.email,
        tenant: user.tenant,
        role: user.role,
    };
    next();
};
exports.generateNewToken = generateNewToken;
//# sourceMappingURL=refreshToken.js.map