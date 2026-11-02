"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteLog = exports.getDashboardStats = exports.getAllLogs = exports.ingestEvent = void 0;
var logs_ingest_1 = require("./logs.ingest");
Object.defineProperty(exports, "ingestEvent", { enumerable: true, get: function () { return logs_ingest_1.ingestEvent; } });
var logs_list_1 = require("./logs.list");
Object.defineProperty(exports, "getAllLogs", { enumerable: true, get: function () { return logs_list_1.getAllLogs; } });
var logs_dashboard_1 = require("./logs.dashboard");
Object.defineProperty(exports, "getDashboardStats", { enumerable: true, get: function () { return logs_dashboard_1.getDashboardStats; } });
var logs_delete_1 = require("./logs.delete");
Object.defineProperty(exports, "deleteLog", { enumerable: true, get: function () { return logs_delete_1.deleteLog; } });
//# sourceMappingURL=logs.con.js.map