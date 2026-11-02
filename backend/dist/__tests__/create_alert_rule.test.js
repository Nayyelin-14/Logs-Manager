"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const alertService = __importStar(require("../services/alert.service"));
const authService = __importStar(require("../services/auth.service"));
const authUtils = __importStar(require("../utils/auth.utils"));
const alertUtils = __importStar(require("../utils/alert.util"));
const cacheQueue_1 = __importDefault(require("../jobs/queues/cacheQueue"));
const alert_con_1 = require("../controllers/admin/alert.con");
// Mock dependencies
jest.mock("../services/alert.service");
jest.mock("../services/auth.service");
jest.mock("../utils/auth.utils");
jest.mock("../utils/alert.util");
jest.mock("../jobs/queues/cacheQueue", () => ({
    __esModule: true,
    default: { add: jest.fn() },
}));
describe("createAlertRule controller", () => {
    let req;
    let res;
    let next;
    const handler = alert_con_1.createAlertRule[alert_con_1.createAlertRule.length - 1];
    beforeEach(() => {
        req = {
            body: {
                name: "Test Rule",
                tenant: "Tenant1",
                description: "Sample rule",
                conditions: [{ type: "LOGIN_FAIL", threshold: 3 }],
            },
            user: { userId: 1 },
        };
        res = {
            status: jest.fn().mockReturnThis(),
            json: jest.fn(),
        };
        next = jest.fn();
        jest.clearAllMocks();
    });
    it("should create an alert rule successfully", async () => {
        authService.getUserById.mockResolvedValue({
            id: 1,
            name: "Admin",
        });
        authUtils.checkUserIfNotExist.mockResolvedValue(undefined);
        alertService.getExistedAlertRule.mockResolvedValue(null);
        alertUtils.checkExistedAlertRule.mockResolvedValue(undefined);
        alertService.createNewAlertRule.mockResolvedValue({
            id: 1,
            name: "Test Rule",
        });
        await handler(req, res, next);
        expect(authService.getUserById).toHaveBeenCalledWith(1);
        expect(alertService.getExistedAlertRule).toHaveBeenCalledWith({
            tenant: "Tenant1",
            name: "Test Rule",
        });
        expect(alertService.createNewAlertRule).toHaveBeenCalledWith({
            name: "Test Rule",
            tenant: "Tenant1",
            description: "Sample rule",
            conditions: [{ type: "LOGIN_FAIL", threshold: 3 }],
        });
        expect(cacheQueue_1.default.add).toHaveBeenCalled();
        expect(res.status).toHaveBeenCalledWith(201);
        expect(res.json).toHaveBeenCalledWith({
            message: "Alert rule is created",
            createdRule: { id: 1, name: "Test Rule" },
        });
    });
    it("should return 401 if user is not authenticated", async () => {
        req.user = undefined;
        await handler(req, res, next);
        expect(res.status).toHaveBeenCalledWith(401);
        expect(res.json).toHaveBeenCalledWith({ message: "Unauthenticated User" });
    });
    it("should return 500 if an error occurs", async () => {
        authService.getUserById.mockRejectedValue(new Error("DB error"));
        await handler(req, res, next);
        expect(res.status).toHaveBeenCalledWith(500);
        expect(res.json).toHaveBeenCalledWith({ message: "Internal server error" });
    });
});
//# sourceMappingURL=create_alert_rule.test.js.map