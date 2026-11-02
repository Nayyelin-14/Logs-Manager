"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAllUserListByPagi = exports.deleteUserById = exports.getUserById = exports.updateUser = exports.createNewUser = exports.updateOtp = exports.storeOtp = exports.getOtpByEmail = exports.getUserByEmail = void 0;
const PrismaClient_1 = require("../config/PrismaClient");
const getUserByEmail = async (email) => {
    return PrismaClient_1.prisma.user.findUnique({
        where: {
            email,
        },
    });
};
exports.getUserByEmail = getUserByEmail;
const getOtpByEmail = async (email) => {
    return PrismaClient_1.prisma.otp.findUnique({
        where: {
            email,
        },
    });
};
exports.getOtpByEmail = getOtpByEmail;
const storeOtp = (optData) => {
    return PrismaClient_1.prisma.otp.create({
        data: optData,
    });
};
exports.storeOtp = storeOtp;
const updateOtp = (optData, id) => {
    return PrismaClient_1.prisma.otp.update({
        where: { id },
        data: optData,
    });
};
exports.updateOtp = updateOtp;
const createNewUser = (userData) => {
    return PrismaClient_1.prisma.user.create({
        data: userData,
    });
};
exports.createNewUser = createNewUser;
const updateUser = (userData, id) => {
    return PrismaClient_1.prisma.user.update({
        where: { id },
        data: userData,
    });
};
exports.updateUser = updateUser;
const getUserById = async (id) => {
    return PrismaClient_1.prisma.user.findUnique({
        where: {
            id,
        },
    });
};
exports.getUserById = getUserById;
const deleteUserById = async (id) => {
    return PrismaClient_1.prisma.user.delete({ where: { id } });
};
exports.deleteUserById = deleteUserById;
const getAllUserListByPagi = async (options) => {
    return await PrismaClient_1.prisma.user.findMany(options);
};
exports.getAllUserListByPagi = getAllUserListByPagi;
//# sourceMappingURL=auth.service.js.map