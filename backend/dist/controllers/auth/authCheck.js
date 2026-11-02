"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.authcheck = void 0;
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errrorcode_1 = require("../../config/errrorcode");
const authcheck = async (req, res, next) => {
    const userId = req.user?.userId;
    if (!userId) {
        const error = new Error("Unauthenticated User");
        error.status = 400;
        error.code = errrorcode_1.errorCode.unthenticated;
        return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
    }
    const user = await (0, auth_service_1.getUserById)(userId);
    await (0, auth_utils_1.checkUserIfNotExist)(user);
    return res.status(200).json({
        message: "Authenticated user",
        user: {
            id: user.id,
            username: user.username,
            email: user.email,
            role: user.role,
            tenant: user.tenant,
            status: user.status,
        },
    });
};
exports.authcheck = authcheck;
//# sourceMappingURL=authCheck.js.map