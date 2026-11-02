import express from "express";
import {
  createAlertRule,
  deleteAlertRule,
  getAllAlertRule,
  updateAlertRule,
  setAlertRuleEnabled,
} from "../controllers/admin/alert.con";
import { updateAlertStatus } from "../controllers/admin/alert.status";
const router = express.Router();

router.post("/create-alertRule", createAlertRule);
router.get("/get-rules", getAllAlertRule);
router.put("/update-rule/:id", updateAlertRule);
router.patch("/rules/:id/enabled", setAlertRuleEnabled);
router.patch("/alerts/:id", updateAlertStatus);
router.delete("/delete-rule/:id", deleteAlertRule);

export default router;
