import { startTcpSyslogListener } from "./tcp";
import { startUdpSyslogListener } from "./udp";

export function startSyslogListeners() {
  if (process.env.SYSLOG_ENABLED !== "true") {
    console.log("Syslog listeners are disabled (set SYSLOG_ENABLED=true).");
    return;
  }

  startUdpSyslogListener();
  startTcpSyslogListener();
}

export { parseSyslogMessage } from "./syslog";
