"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ingestBatch = ingestBatch;
const ingest_service_1 = require("../services/ingest.service");
const batch_1 = require("../ingest/batch");
async function ingestBatch(req, res, next) {
    try {
        const service = new ingest_service_1.IngestService();
        const body = req.body;
        let events = [];
        let sourceInput = body?.source ?? req.query.source;
        if (req.file) {
            events = (0, batch_1.parseBatchBuffer)(req.file.buffer, req.file.originalname, req.file.mimetype);
        }
        else if (Array.isArray(body)) {
            events = body;
        }
        else if (body && typeof body === "object") {
            const listKey = ["events", "logs", "records", "items", "data"].find((key) => Array.isArray(body[key]));
            if (listKey) {
                events = body[listKey];
                sourceInput = body.source ?? sourceInput;
            }
            else if (body.event && typeof body.event === "object") {
                events = [body.event];
            }
            else {
                events = [body];
            }
        }
        if (events.length === 0) {
            return res.status(400).json({
                success: false,
                message: "Provide a multipart file field named 'file', a JSON array, or a JSONL/CSV file.",
            });
        }
        const requestedTenant = !Array.isArray(body) && typeof body?.tenant === "string"
            ? body.tenant.trim()
            : undefined;
        if (requestedTenant &&
            req.user?.tenant &&
            requestedTenant !== req.user.tenant) {
            return res.status(403).json({
                success: false,
                message: "Tenant does not match the authenticated identity.",
            });
        }
        if (requestedTenant) {
            for (const event of events) {
                if (event && typeof event === "object" && !event.tenant) {
                    event.tenant = requestedTenant;
                }
            }
        }
        const maxEvents = Number(process.env.INGEST_BATCH_MAX_EVENTS || 1000);
        if (Number.isFinite(maxEvents) && events.length > maxEvents) {
            return res.status(413).json({
                success: false,
                message: `Batch contains ${events.length} events; the limit is ${maxEvents}.`,
            });
        }
        const result = await service.ingestBatch(events, sourceInput, {
            tenant: req.user?.tenant,
            username: req.user?.username || req.user?.email,
            email: req.user?.email,
        });
        return res.status(result.ingested > 0 ? 201 : 400).json({
            success: result.ingested > 0,
            ...result,
        });
    }
    catch (error) {
        return next(error);
    }
}
//# sourceMappingURL=ingest.con.js.map