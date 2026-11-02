"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const app_1 = require("./app");
const PrismaClient_1 = require("./config/PrismaClient");
const ingest_1 = require("./ingest");
const PORT = process.env.PORT || 4500;
(async () => {
    await (0, PrismaClient_1.connectWithRetry)();
    app_1.app.listen(PORT, () => console.log(`server is running at ${PORT}`));
    (0, ingest_1.startSyslogListeners)();
})();
//# sourceMappingURL=index.js.map