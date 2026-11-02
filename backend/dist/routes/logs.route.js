"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const logs_con_1 = require("../controllers/admin/logs.con");
const users_con_1 = require("../controllers/users/users.con");
const alert_query_1 = require("../controllers/admin/alert.query");
// import { saveLog } from "../controllers/logs.js";
const router = express_1.default.Router();
router.get("/get-logs", logs_con_1.getAllLogs);
router.get("/get-alerts", alert_query_1.listAlerts);
router.delete("/delete-log/:logId", logs_con_1.deleteLog);
//for user data
router.get("/user-dashboard/:userId", users_con_1.getUserDashboardStats);
exports.default = router;
//# sourceMappingURL=logs.route.js.map