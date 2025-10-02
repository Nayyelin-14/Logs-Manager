import express from "express";

import {
  createUser,
  deleteUser,
  getAllDataCount,
  getAllUsers,
  updateUserController,
} from "../controllers/admin/manage.con";
import { getDashboardStats } from "../controllers/admin/logs.con";
// import { saveLog } from "../controllers/logs.js";

const router = express.Router();

router.put("/update-user", updateUserController);
router.post("/create-user", createUser);
router.get("/get-users", getAllUsers);
router.delete("/delete-user/:userId", deleteUser);
router.get("/get-all-data", getAllDataCount);
router.get("/dashboard", getDashboardStats);
export default router;
