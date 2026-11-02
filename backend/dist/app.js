"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.app = void 0;
const express_1 = __importDefault(require("express"));
const helmet_1 = __importDefault(require("helmet"));
const cors_1 = __importDefault(require("cors"));
const compression_1 = __importDefault(require("compression"));
const morgan_1 = __importDefault(require("morgan"));
const cookie_parser_1 = __importDefault(require("cookie-parser"));
const path_1 = __importDefault(require("path"));
const node_cron_1 = __importDefault(require("node-cron"));
const index_route_1 = __importDefault(require("./routes/index.route"));
const logCleanUp_1 = require("./scripts/logCleanUp");
exports.app = (0, express_1.default)();
const whitelist = new Set([
    "http://localhost:5173",
    ...(process.env.CORS_ORIGINS || "").split(","),
    process.env.FRONTEND_URL || "",
]
    .map((origin) => origin.trim())
    .filter(Boolean));
const corsOptions = {
    origin: function (origin, callback) {
        if (!origin)
            return callback(null, true);
        if (whitelist.has(origin)) {
            callback(null, true);
        }
        else {
            const error = new Error("Not allowed by CORS");
            error.status = 403;
            callback(error);
        }
    },
    credentials: true,
};
exports.app.use((0, morgan_1.default)("dev"));
exports.app.use(express_1.default.urlencoded({ extended: true }));
exports.app.use(express_1.default.json());
exports.app.use(express_1.default.static("upload/images"));
exports.app.use((0, cookie_parser_1.default)());
exports.app.use((0, cors_1.default)(corsOptions));
exports.app.use((0, compression_1.default)({}));
// app.use(rateLimiter);
exports.app.use((0, helmet_1.default)());
exports.app.set("trust proxy", true);
exports.app.use((req, res, next) => {
    res.setHeader("Cross-Origin-Resource-Policy", "same-site");
    next();
});
exports.app.use("/optimizedImages", express_1.default.static(path_1.default.join(__dirname, "../upload/optimizedImages")));
//for all routes
exports.app.use(index_route_1.default);
exports.app.use((error, req, res, next) => {
    console.log(error);
    const status = error.status || 500;
    const message = error.message || "Something went wrong";
    const errorCode = error.code || "Error_code";
    res.status(status).json({ message, error: errorCode });
});
//run once a week on Monday at 5 AM.
node_cron_1.default.schedule("0 5 * * 1", async () => {
    console.log("🕒 Running scheduled cleanup task...");
    try {
        await (0, logCleanUp_1.cleanupOldLogs)();
    }
    catch (err) {
        console.error("Cleanup failed:", err);
    }
});
//# sourceMappingURL=app.js.map