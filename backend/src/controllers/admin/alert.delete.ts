import { Response } from "express";
import { param } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import {
  deleteExistedAlert,
  getExistedAlertRule,
} from "../../services/alert.service";
import { getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import cacheQueue from "../../jobs/queues/cacheQueue";
import { prisma } from "../../config/PrismaClient";

export const deleteAlertRule = [
  param("id", "Rule Id is required.").trim().notEmpty().escape(),
  async (req: CustomRequest, res: Response) => {
    try {
      const { id } = req.params;

      if (!id) {
        return res.status(400).json({ message: "Missing AlertRule ID" });
      }

      if (!req.user || req.user.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId } = req.user;
      const user = await getUserById(userId!);
      await checkUserIfNotExist(user);

      console.log(id);
      const existedRules = await getExistedAlertRule({ id });
      const existedRule = existedRules[0];

      if (!existedRule) {
        return res.status(404).json({ message: "AlertRule not found" });
      }

      const alertHistoryCount = await prisma.alert.count({
        where: { ruleId: existedRule.id },
      });
      if (alertHistoryCount > 0) {
        return res.status(409).json({
          message:
            "This rule has triggered alerts and cannot be deleted while its alert history is retained.",
        });
      }

      // Delete the alert rule
      await deleteExistedAlert(existedRule.id);

      await cacheQueue.add(
        "invalidate-rule-cache",
        {
          pattern: "rules:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );

      return res
        .status(200)
        .json({ message: "AlertRule deleted successfully" });
    } catch (error) {
      console.error("Error deleting AlertRule:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];
