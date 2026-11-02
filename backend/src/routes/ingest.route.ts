import express from "express";
import multer from "multer";
import { ingestEvent } from "../controllers/admin/logs.con";
import { ingestBatch } from "../controllers/ingest.con";
import { ingestAuth } from "../middleware/ingestAuth";

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: Number(process.env.INGEST_MAX_FILE_BYTES || 10 * 1024 * 1024),
    files: 1,
  },
});

router.post("/ingest", ingestAuth, ingestEvent);
router.post("/ingest/batch", ingestAuth, upload.single("file"), ingestBatch);

export default router;
