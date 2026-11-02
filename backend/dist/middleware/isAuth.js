"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.requireTenant = exports.requireRole = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const errorHandeling_1 = require("../utils/errorHandeling");
const refreshToken_1 = require("../utils/refreshToken");
const errrorcode_1 = require("../config/errrorcode");
async function authMiddleware(req, res, next) {
    const accessToken = req.cookies?.accessToken || null;
    const refreshToken = req.cookies?.refreshToken || null;
    if (!refreshToken) {
        return next((0, errorHandeling_1.handleError)("Unauthenticated user. Try Again!!!", 401, errrorcode_1.errorCode.unthenticated));
    }
    let decoded;
    try {
        if (accessToken) {
            decoded = jsonwebtoken_1.default.verify(accessToken, process.env.ACCESS_TOKEN_SECRET);
            req.user = {
                userId: decoded.userId,
                username: decoded.username,
                role: decoded.role,
                tenant: decoded.tenant,
                email: decoded.email,
            };
            return next();
        }
        else {
            throw new jsonwebtoken_1.default.TokenExpiredError("AccessToken Missing", new Date());
        }
    }
    catch (error) {
        if (error.name === "TokenExpiredError" ||
            error.name === "JsonWebTokenError") {
            try {
                await (0, refreshToken_1.generateNewToken)(refreshToken, req, res, () => { });
                const newAccessToken = req.cookies?.accessToken;
                if (!newAccessToken) {
                    return next((0, errorHandeling_1.handleError)("New Token refresh failed", 401, errrorcode_1.errorCode.unthenticated));
                }
                // Step 3: Verify new access token
                decoded = jsonwebtoken_1.default.verify(newAccessToken, process.env.ACCESS_TOKEN_SECRET);
                req.user = {
                    userId: decoded.userId,
                    username: decoded.username,
                    role: decoded.role,
                    tenant: decoded.tenant,
                    email: decoded.email,
                };
                return next();
            }
            catch (refreshError) {
                return next((0, errorHandeling_1.handleError)("Token refresh failed", 401, errrorcode_1.errorCode.unthenticated));
            }
        }
    }
}
const requireRole = (roles) => {
    return (req, res, next) => {
        if (!req.user || !roles.includes(req.user.role)) {
            return res.status(403).json({ error: "Insufficient permissions" });
        }
        next();
    };
};
exports.requireRole = requireRole;
const requireTenant = (req, res, next) => {
    const tenant = req.query.tenant ||
        req.body.tenant ||
        req.cookies?.tenant;
    if (!tenant) {
        return res.status(400).json({ error: "Tenant parameter required" });
    }
    if (req.user?.role !== "ADMIN" && !req.user?.tenants.includes(tenant)) {
        return res.status(403).json({ error: "Access denied to this tenant" });
    }
    next();
};
exports.requireTenant = requireTenant;
exports.default = authMiddleware;
//# sourceMappingURL=isAuth.js.map