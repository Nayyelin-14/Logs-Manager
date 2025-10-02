import express from "express";
import {
  createAlertRule,
  deleteAlertRule,
  getAllAlertRule,
} from "../controllers/admin/alert.con";
const router = express.Router();

router.post("/create-alertRule", createAlertRule);
router.get("/get-rules", getAllAlertRule);
router.delete("/delete-rule/:id", deleteAlertRule);

export default router;
