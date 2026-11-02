"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ingestEvent = void 0;
const express_validator_1 = require("express-validator");
const prisma_1 = require("../../generated/prisma");
const ingest_service_1 = require("../../services/ingest.service");
const source_1 = require("../../ingest/source");
exports.ingestEvent = [
    (0, express_validator_1.body)("tenant")
        .optional({ checkFalsy: true })
        .isString()
        .withMessage("Tenant must be a string."),
    (0, express_validator_1.body)("source")
        .exists()
        .withMessage("Source is required.")
        .custom((value) => {
        const normalized = (0, source_1.normalizeSourceInput)(value);
        if (!normalized) {
            throw new Error(`Source must be one of: ${Object.values(prisma_1.Source).join(", ")} or an alias such as syslog, firewall, cloudtrail, m365, or active_directory.`);
        }
        return true;
    }),
    (0, express_validator_1.body)("raw").optional().isObject().withMessage("raw must be an object"),
    (0, express_validator_1.body)("tags").optional().isArray().withMessage("tags must be an array"),
    async (req, res, next) => {
        try {
            const errors = (0, express_validator_1.validationResult)(req);
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
            const result = await new ingest_service_1.IngestService().ingest(rawEvent, rawEvent.source, {
                tenant: req.user.tenant,
                username: req.user.username || req.user.email,
                email: req.user.email,
            });
            return res.status(201).json({
                success: true,
                eventId: result.event.id,
                message: "Log has been ingested successfully.",
                event: result.event,
                alertTriggered: result.alerts.length > 0,
                alerts: result.alerts,
            });
        }
        catch (error) {
            console.error("Error ingesting log:", error);
            const status = error?.status || 500;
            return res.status(status).json({
                success: false,
                error: error?.code || "Failed to ingest log",
                message: error instanceof Error ? error.message : "Unknown error",
            });
        }
    },
];
//# sourceMappingURL=logs.ingest.js.map