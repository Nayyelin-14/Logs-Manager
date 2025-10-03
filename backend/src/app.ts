import express, { NextFunction, Request, Response } from "express";
import helmet from "helmet";
import cors, { CorsOptions } from "cors";
import compression from "compression";
import morgan from "morgan";

import cookieParser from "cookie-parser";

import path from "path";
import cron from "node-cron";
import route from "./routes/index.route";
import { cleanupOldLogs } from "./scripts/logCleanUp";

export const app = express();
const whitelist = ["http://localhost:5173", "https://yourdomain.com"];

const corsOptions: CorsOptions = {
  origin: function (origin, callback) {
    if (!origin) return callback(null, true);
    if (whitelist.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error("Not allowed by CORS"));
    }
  },
  credentials: true,
};
app.use(morgan("dev"));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static("upload/images"));
app.use(cookieParser());
app.use(cors(corsOptions));
app.use(compression({}));
// app.use(rateLimiter);
app.use(helmet());
app.set("trust proxy", true);
app.use((req, res, next) => {
  res.setHeader("Cross-Origin-Resource-Policy", "same-site");
  next();
});

app.use(
  "/optimizedImages",
  express.static(path.join(__dirname, "../upload/optimizedImages"))
);
//for all routes
app.use(route);
app.use((error: any, req: Request, res: Response, next: NextFunction) => {
  console.log(error);
  const status = error.status || 404;
  const message = error.message || "Something went wrong";
  const errorCode = error.code || "Error_code";
  res.status(status).json({ message, error: errorCode });
});

//run once a week on Monday at 5 AM.
cron.schedule("0 5 * * 1", async () => {
  console.log("🕒 Running scheduled cleanup task...");
  try {
    await cleanupOldLogs();
  } catch (err) {
    console.error("Cleanup failed:", err);
  }
});
