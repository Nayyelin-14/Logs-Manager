import { Response } from "express";
import { body, param, validationResult } from "express-validator";
import { prisma } from "../../config/PrismaClient";
import { CustomRequest } from "../../utils/refreshToken";

export const updateAlertStatus = [
  param("id").isString().notEmpty(),
  body("status").isIn(["open", "resolved"]),
  async (req: CustomRequest, res: Response) => {
    const errors = validationResult(req).array({ onlyFirstError: true });
    if (errors.length) {
      return res.status(400).json({ message: errors[0].msg });
    }

    try {
      const existing = await prisma.alert.findUnique({
        where: { id: req.params.id },
        select: { id: true },
      });
      if (!existing) {
        return res.status(404).json({ message: "Alert not found." });
      }

      const alert = await prisma.alert.update({
        where: { id: req.params.id },
        data: { status: req.body.status },
      });
      return res.status(200).json({ message: "Alert status updated.", alert });
    } catch (error) {
      return res.status(500).json({ message: "Could not update alert status." });
    }
  },
];
