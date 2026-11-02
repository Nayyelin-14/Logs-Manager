"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.authroiseMiddleware = void 0;
const auth_service_1 = require("../services/auth.service");
const auth_utils_1 = require("../utils/auth.utils");
const errorHandeling_1 = require("../utils/errorHandeling");
const errrorcode_1 = require("../config/errrorcode");
const authroiseMiddleware = (permission, ...roles) => {
    return async (req, res, next) => {
        if (!req.user || !req.user.userId) {
            return res.status(401).json({ message: "Unauthorized" });
        }
        const user = await (0, auth_service_1.getUserById)(req.user.userId);
        (0, auth_utils_1.checkUserIfNotExist)(user);
        const roleResult = roles.includes(user.role);
        if ((permission && !roleResult) || (!permission && roleResult)) {
            return next((0, errorHandeling_1.handleError)("Unauthorized User", 401, errrorcode_1.errorCode.unauthorized));
        }
        next();
    };
};
exports.authroiseMiddleware = authroiseMiddleware;
//# sourceMappingURL=authorization.js.map