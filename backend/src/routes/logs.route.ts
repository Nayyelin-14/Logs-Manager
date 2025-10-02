import express from "express";

import {
  deleteLog,
  getAllLogs,
  getDashboardStats,
  ingestEvent,
} from "../controllers/admin/logs.con";
import { getUserDashboardStats } from "../controllers/users/users.con";
// import { saveLog } from "../controllers/logs.js";

const router = express.Router();

router.post("/ingest", ingestEvent);
router.get("/get-logs", getAllLogs);

router.delete("/delete-log/:logId", deleteLog);

//for user data
router.get("/user-dashboard/:userId", getUserDashboardStats);

export default router;
