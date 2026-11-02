"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkLogIfNotExist = exports.checkOtpExist = exports.checkUserIfNotExist = exports.checkUserExist = void 0;
const errrorcode_1 = require("../config/errrorcode");
const errorHandeling_1 = require("./errorHandeling");
const checkUserExist = async (user) => {
    if (user) {
        throw (0, errorHandeling_1.handleError)("This email number is already in use", 409, errrorcode_1.errorCode.userExist);
    }
};
exports.checkUserExist = checkUserExist;
const checkUserIfNotExist = async (user) => {
    if (!user) {
        throw (0, errorHandeling_1.handleError)("User not found.Try Again!!!", 409, errrorcode_1.errorCode.unthenticated);
    }
};
exports.checkUserIfNotExist = checkUserIfNotExist;
const checkOtpExist = async (otp) => {
    if (!otp) {
        throw (0, errorHandeling_1.handleError)("Something went wrong with one time password", 400, errrorcode_1.errorCode.invalid);
    }
};
exports.checkOtpExist = checkOtpExist;
const checkLogIfNotExist = async (log) => {
    if (!log) {
        throw (0, errorHandeling_1.handleError)("Log not found.Try Again!!!", 409, errrorcode_1.errorCode.unthenticated);
    }
};
exports.checkLogIfNotExist = checkLogIfNotExist;
//# sourceMappingURL=auth.utils.js.map