"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const alert_con_1 = require("../controllers/admin/alert.con");
const alert_status_1 = require("../controllers/admin/alert.status");
const router = express_1.default.Router();
router.post("/create-alertRule", alert_con_1.createAlertRule);
router.get("/get-rules", alert_con_1.getAllAlertRule);
router.put("/update-rule/:id", alert_con_1.updateAlertRule);
router.patch("/rules/:id/enabled", alert_con_1.setAlertRuleEnabled);
router.patch("/alerts/:id", alert_status_1.updateAlertStatus);
router.delete("/delete-rule/:id", alert_con_1.deleteAlertRule);
exports.default = router;
//# sourceMappingURL=alert.route.js.map