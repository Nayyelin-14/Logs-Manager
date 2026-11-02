import express from "express";

import {
  deleteLog,
  getAllLogs,
  getDashboardStats,
} from "../controllers/admin/logs.con";
import { getUserDashboardStats } from "../controllers/users/users.con";
import { listAlerts } from "../controllers/admin/alert.query";
// import { saveLog } from "../controllers/logs.js";

const router = express.Router();

router.get("/get-logs", getAllLogs);
router.get("/get-alerts", listAlerts);

router.delete("/delete-log/:logId", deleteLog);

//for user data
router.get("/user-dashboard/:userId", getUserDashboardStats);

export default router;
