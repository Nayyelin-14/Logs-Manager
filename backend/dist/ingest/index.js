"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseSyslogMessage = void 0;
exports.startSyslogListeners = startSyslogListeners;
const tcp_1 = require("./tcp");
const udp_1 = require("./udp");
function startSyslogListeners() {
    if (process.env.SYSLOG_ENABLED !== "true") {
        console.log("Syslog listeners are disabled (set SYSLOG_ENABLED=true).");
        return;
    }
    (0, udp_1.startUdpSyslogListener)();
    (0, tcp_1.startTcpSyslogListener)();
}
var syslog_1 = require("./syslog");
Object.defineProperty(exports, "parseSyslogMessage", { enumerable: true, get: function () { return syslog_1.parseSyslogMessage; } });
//# sourceMappingURL=index.js.map