"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.handleError = void 0;
const handleError = (message, status, code) => {
    const error = new Error(`${message}`);
    error.status = status;
    error.code = code;
    return error;
};
exports.handleError = handleError;
//# sourceMappingURL=errorHandeling.js.map