"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.startTcpSyslogListener = startTcpSyslogListener;
const net_1 = __importDefault(require("net"));
const ingest_service_1 = require("../services/ingest.service");
const syslog_1 = require("./syslog");
const MAX_BUFFER_BYTES = 1024 * 1024;
function startTcpSyslogListener() {
    const port = Number(process.env.SYSLOG_TCP_PORT || 514);
    const host = process.env.SYSLOG_TCP_HOST || undefined;
    const tenant = process.env.SYSLOG_TENANT ||
        process.env.INGEST_DEFAULT_TENANT ||
        "demoA";
    const username = process.env.SYSLOG_USERNAME || "syslog";
    const defaultSource = process.env.SYSLOG_SOURCE || "firewall";
    const service = new ingest_service_1.IngestService();
    const server = net_1.default.createServer((socket) => {
        socket.setEncoding("utf8");
        let buffer = "";
        const ingestLine = (line) => {
            const parsed = (0, syslog_1.parseSyslogMessage)(line);
            if (!parsed)
                return;
            parsed.remoteAddress = socket.remoteAddress;
            parsed.remotePort = socket.remotePort;
            void service
                .ingest(parsed, parsed.source || defaultSource, { tenant, username })
                .catch((error) => {
                console.error("Failed to ingest syslog TCP message:", error);
            });
        };
        const drainBuffer = () => {
            while (buffer.length > 0) {
                const octet = buffer.match(/^(\d+)\s/);
                if (octet) {
                    const length = Number(octet[1]);
                    const start = octet[0].length;
                    if (buffer.length < start + length)
                        return;
                    const line = buffer.slice(start, start + length);
                    buffer = buffer.slice(start + length);
                    ingestLine(line);
                    continue;
                }
                const newline = buffer.indexOf("\n");
                if (newline === -1)
                    return;
                const line = buffer.slice(0, newline).replace(/\r$/, "");
                buffer = buffer.slice(newline + 1);
                if (line.trim())
                    ingestLine(line);
            }
        };
        socket.on("data", (chunk) => {
            buffer += chunk;
            if (buffer.length > MAX_BUFFER_BYTES) {
                console.warn("Syslog TCP message exceeded buffer limit; closing socket.");
                socket.destroy();
                return;
            }
            drainBuffer();
        });
        socket.on("end", () => {
            if (buffer.trim())
                ingestLine(buffer.trim());
            buffer = "";
        });
        socket.on("error", (error) => {
            console.error("Syslog TCP connection error:", error.message);
        });
    });
    server.on("error", (error) => {
        console.error(`Syslog TCP listener error on port ${port}:`, error.message);
    });
    server.listen(port, host, () => {
        const address = server.address();
        if (address && typeof address === "object") {
            console.log(`Syslog TCP listener listening on ${address.address}:${address.port}`);
        }
        else {
            console.log(`Syslog TCP listener listening on port ${port}`);
        }
    });
    return server;
}
//# sourceMappingURL=tcp.js.map