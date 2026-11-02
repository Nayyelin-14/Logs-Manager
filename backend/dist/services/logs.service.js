"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteLogById = exports.getLogById = exports.getAllLogsListByPagi = void 0;
const PrismaClient_1 = require("../config/PrismaClient");
const getAllLogsListByPagi = async (options) => {
    return await PrismaClient_1.prisma.securityEvent.findMany(options);
};
exports.getAllLogsListByPagi = getAllLogsListByPagi;
const getLogById = async (id) => {
    return PrismaClient_1.prisma.securityEvent.findUnique({
        where: {
            id,
        },
    });
};
exports.getLogById = getLogById;
const deleteLogById = async (id) => {
    return PrismaClient_1.prisma.securityEvent.delete({ where: { id } });
};
exports.deleteLogById = deleteLogById;
//# sourceMappingURL=logs.service.js.map