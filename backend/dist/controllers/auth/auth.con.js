"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.logout = exports.loginUser = exports.confirmPassword = exports.veridyOtp = exports.registerUser = void 0;
const register_1 = require("./register");
Object.defineProperty(exports, "registerUser", { enumerable: true, get: function () { return register_1.registerUser; } });
Object.defineProperty(exports, "veridyOtp", { enumerable: true, get: function () { return register_1.veridyOtp; } });
const password_1 = require("./password");
Object.defineProperty(exports, "confirmPassword", { enumerable: true, get: function () { return password_1.confirmPassword; } });
const session_1 = require("./session");
Object.defineProperty(exports, "loginUser", { enumerable: true, get: function () { return session_1.loginUser; } });
Object.defineProperty(exports, "logout", { enumerable: true, get: function () { return session_1.logout; } });
exports.default = {
    loginUser: session_1.loginUser,
    registerUser: register_1.registerUser,
    logout: session_1.logout,
    veridyOtp: register_1.veridyOtp,
    confirmPassword: password_1.confirmPassword,
};
//# sourceMappingURL=auth.con.js.map