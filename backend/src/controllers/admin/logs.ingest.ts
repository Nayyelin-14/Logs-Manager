import { NextFunction, Response } from "express";
import { body, validationResult } from "express-validator";
import { Source } from "../../generated/prisma";
import { CustomRequest } from "../../utils/refreshToken";
import { IngestService } from "../../services/ingest.service";
import { normalizeSourceInput } from "../../ingest/source";

export const ingestEvent = [
  body("tenant")
    .optional({ checkFalsy: true })
    .isString()
    .withMessage("Tenant must be a string."),

  body("source")
    .exists()
    .withMessage("Source is required.")
    .custom((value) => {
      const normalized = normalizeSourceInput(value);
      if (!normalized) {
        throw new Error(
          `Source must be one of: ${Object.values(Source).join(", ")} or an alias such as syslog, firewall, cloudtrail, m365, or active_directory.`
        );
      }
      return true;
    }),

  body("raw").optional().isObject().withMessage("raw must be an object"),
  body("tags").optional().isArray().withMessage("tags must be an array"),

  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          success: false,
          errors: errors.array(),
        });
      }

      if (!req.user) {
        return res.status(401).json({
          success: false,
          message: "Unauthenticated user.",
        });
      }

      const rawEvent = req.body;
      if (!rawEvent || typeof rawEvent !== "object" || Array.isArray(rawEvent)) {
        return res.status(400).json({
          success: false,
          message: "Request body must be a JSON object.",
        });
      }

      const result = await new IngestService().ingest(
        rawEvent,
        rawEvent.source,
        {
          tenant: req.user.tenant,
          username: req.user.username || req.user.email,
          email: req.user.email,
        }
      );

      return res.status(201).json({
        success: true,
        eventId: result.event.id,
        message: "Log has been ingested successfully.",
        event: result.event,
        alertTriggered: result.alerts.length > 0,
        alerts: result.alerts,
      });
    } catch (error) {
      console.error("Error ingesting log:", error);
      const status = (error as any)?.status || 500;
      return res.status(status).json({
        success: false,
        error: (error as any)?.code || "Failed to ingest log",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  },
];
