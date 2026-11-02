"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateToken = exports.generateOTP = void 0;
const crypto_1 = require("crypto");
const generateOTP = () => {
    //toString("hex") and parseInt(..., 16):
    // Converts the 3 bytes to a hexadecimal string, then parses it into a decimal integer.For example: "f1b2c3" → 15866115.
    return (parseInt((0, crypto_1.randomBytes)(3).toString("hex"), 16) % 900000) + 100000;
};
exports.generateOTP = generateOTP;
const generateToken = () => {
    return (0, crypto_1.randomBytes)(32).toString("hex");
};
exports.generateToken = generateToken;
//# sourceMappingURL=generateOTP.js.map