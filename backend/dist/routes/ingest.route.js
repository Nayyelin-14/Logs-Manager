"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const multer_1 = __importDefault(require("multer"));
const logs_con_1 = require("../controllers/admin/logs.con");
const ingest_con_1 = require("../controllers/ingest.con");
const ingestAuth_1 = require("../middleware/ingestAuth");
const router = express_1.default.Router();
const upload = (0, multer_1.default)({
    storage: multer_1.default.memoryStorage(),
    limits: {
        fileSize: Number(process.env.INGEST_MAX_FILE_BYTES || 10 * 1024 * 1024),
        files: 1,
    },
});
router.post("/ingest", ingestAuth_1.ingestAuth, logs_con_1.ingestEvent);
router.post("/ingest/batch", ingestAuth_1.ingestAuth, upload.single("file"), ingest_con_1.ingestBatch);
exports.default = router;
//# sourceMappingURL=ingest.route.js.map