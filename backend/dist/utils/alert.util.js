"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkExistedAlertRule = void 0;
exports.getSeverityLevel = getSeverityLevel;
const errrorcode_1 = require("../config/errrorcode");
const errorHandeling_1 = require("./errorHandeling");
const checkExistedAlertRule = async (rule) => {
    if (Array.isArray(rule) ? rule.length > 0 : Boolean(rule)) {
        throw (0, errorHandeling_1.handleError)("This rule is already existed.", 400, errrorcode_1.errorCode.existedRule);
    }
};
exports.checkExistedAlertRule = checkExistedAlertRule;
function getSeverityLevel(severity) {
    if (severity === undefined || severity === null)
        return "Unknown";
    if (severity >= 0 && severity <= 3)
        return "Low";
    if (severity >= 4 && severity <= 7)
        return "Medium";
    if (severity >= 8 && severity <= 10)
        return "High";
    return "Unknown";
}
//# sourceMappingURL=alert.util.js.map