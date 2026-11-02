"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateAlertRuleById = exports.duplicate = exports.deleteExistedAlert = exports.createNewAlertRule = exports.getAllRules = exports.getExistedAlertRule = void 0;
const PrismaClient_1 = require("../config/PrismaClient");
// Get one alert rule by tenant+name OR by id
const getExistedAlertRule = async (where) => {
    return await PrismaClient_1.prisma.alertRule.findMany({ where });
};
exports.getExistedAlertRule = getExistedAlertRule;
const getAllRules = async (options) => {
    const { where, skip, take, cursor, orderBy, select } = options;
    return PrismaClient_1.prisma.alertRule.findMany({
        where: where || {},
        skip,
        take,
        cursor,
        orderBy,
        select,
    });
};
exports.getAllRules = getAllRules;
// Create a new AlertRule
const createNewAlertRule = async (data) => {
    const { name, description, tenant, enabled = true, conditions, } = data;
    const alertRule = await PrismaClient_1.prisma.alertRule.create({
        data: {
            name,
            description,
            tenant,
            enabled,
            conditions,
        },
    });
    return alertRule;
};
exports.createNewAlertRule = createNewAlertRule;
// Delete an existing AlertRule by id
const deleteExistedAlert = async (id) => {
    return PrismaClient_1.prisma.alertRule.delete({
        where: { id },
    });
};
exports.deleteExistedAlert = deleteExistedAlert;
const duplicate = (tenant, name, id) => {
    return PrismaClient_1.prisma.alertRule.findFirst({
        where: {
            tenant,
            name,
            NOT: { id }, // exclude current rule
        },
    });
};
exports.duplicate = duplicate;
const updateAlertRuleById = async (data, id) => {
    return PrismaClient_1.prisma.alertRule.update({
        where: { id },
        data,
    });
};
exports.updateAlertRuleById = updateAlertRuleById;
//# sourceMappingURL=alert.service.js.map