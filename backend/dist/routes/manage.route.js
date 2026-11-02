"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const manage_con_1 = require("../controllers/admin/manage.con");
const logs_con_1 = require("../controllers/admin/logs.con");
// import { saveLog } from "../controllers/logs.js";
const router = express_1.default.Router();
router.put("/update-user", manage_con_1.updateUserController);
router.post("/create-user", manage_con_1.createUser);
router.get("/get-users", manage_con_1.getAllUsers);
router.delete("/delete-user/:userId", manage_con_1.deleteUser);
router.get("/get-all-data", manage_con_1.getAllDataCount);
router.get("/dashboard", logs_con_1.getDashboardStats);
exports.default = router;
//# sourceMappingURL=manage.route.js.map