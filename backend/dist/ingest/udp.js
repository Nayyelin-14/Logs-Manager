"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.startUdpSyslogListener = startUdpSyslogListener;
const dgram_1 = __importDefault(require("dgram"));
const ingest_service_1 = require("../services/ingest.service");
const syslog_1 = require("./syslog");
function startUdpSyslogListener() {
    const port = Number(process.env.SYSLOG_UDP_PORT || 514);
    const host = process.env.SYSLOG_UDP_HOST || undefined;
    const tenant = process.env.SYSLOG_TENANT ||
        process.env.INGEST_DEFAULT_TENANT ||
        "demoA";
    const username = process.env.SYSLOG_USERNAME || "syslog";
    const defaultSource = process.env.SYSLOG_SOURCE || "firewall";
    const service = new ingest_service_1.IngestService();
    const socket = dgram_1.default.createSocket("udp4");
    socket.on("message", (message, remote) => {
        const parsed = (0, syslog_1.parseSyslogMessage)(message.toString("utf8"));
        if (!parsed)
            return;
        parsed.remoteAddress = remote.address;
        parsed.remotePort = remote.port;
        void service
            .ingest(parsed, parsed.source || defaultSource, { tenant, username })
            .catch((error) => {
            console.error("Failed to ingest syslog UDP message:", error);
        });
    });
    socket.on("error", (error) => {
        console.error(`Syslog UDP listener error on port ${port}:`, error.message);
        try {
            socket.close();
        }
        catch {
            // ignore close errors
        }
    });
    socket.bind(port, host, () => {
        const address = socket.address();
        console.log(`Syslog UDP listener listening on ${address.address}:${address.port}`);
    });
    return socket;
}
//# sourceMappingURL=udp.js.map