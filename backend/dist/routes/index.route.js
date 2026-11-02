"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const auth_route_1 = __importDefault(require("./auth.route"));
const ingest_route_1 = __importDefault(require("./ingest.route"));
const logs_route_1 = __importDefault(require("./logs.route"));
const manage_route_1 = __importDefault(require("./manage.route"));
const alert_route_1 = __importDefault(require("./alert.route"));
const isAuth_1 = __importDefault(require("../middleware/isAuth"));
const authorization_1 = require("../middleware/authorization");
const route = (0, express_1.Router)();
route.use("/api/auth", auth_route_1.default);
route.use("/api", ingest_route_1.default);
route.use("/api", isAuth_1.default, logs_route_1.default);
route.use("/api", isAuth_1.default, (0, authorization_1.authroiseMiddleware)(true, "ADMIN"), manage_route_1.default);
route.use("/api", isAuth_1.default, (0, authorization_1.authroiseMiddleware)(true, "ADMIN"), alert_route_1.default);
exports.default = route;
//# sourceMappingURL=index.route.js.map