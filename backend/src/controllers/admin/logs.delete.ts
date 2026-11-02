import { NextFunction, Response } from "express";
import { param, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import { getUserById } from "../../services/auth.service";
import { checkLogIfNotExist, checkUserIfNotExist } from "../../utils/auth.utils";
import { deleteLogById, getLogById } from "../../services/logs.service";
import cacheQueue from "../../jobs/queues/cacheQueue";

export const deleteLog = [
  param("logId").notEmpty().withMessage("Log ID is required"),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { logId } = req.params;

      // Check if user exists
      const existedLog = await getLogById(logId);
      await checkLogIfNotExist(existedLog);

      const existedUser = await getUserById(Number(req.user?.userId));
      await checkUserIfNotExist(existedUser);
      const ownIdentity = existedUser?.username ?? existedUser?.email ?? "";
      const ownsLog =
        existedLog?.tenant === existedUser?.tenant &&
        existedLog?.user?.toLowerCase() === ownIdentity.toLowerCase();
      if (req.user?.role !== "ADMIN" && !ownsLog) {
        return res.status(403).json({ message: "Forbidden: Not authorized" });
      }
      // Delete user
      const logdeletion = await deleteLogById(logId);
      await cacheQueue.add(
        "invalidate-log-cache",
        {
          pattern: "logs:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );
      return res.status(200).json({
        success: true,
        message: "Selected log is deleted",
        data: logdeletion,
      });
    } catch (error) {
      console.error("Error deleting log:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];
