"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NormalizationService = void 0;
const structured_1 = require("./normalization/structured");
const cloud_1 = require("./normalization/cloud");
const identity_1 = require("./normalization/identity");
class NormalizationService {
    static normalizeEvent(rawEvent, source) {
        const sourceKey = String(source ?? "").toLowerCase();
        switch (sourceKey) {
            case "firewall":
            case "syslog":
                return (0, structured_1.normalizeSyslog)(rawEvent);
            case "api":
                return (0, structured_1.normalizeAPI)(rawEvent);
            case "aws":
                return (0, cloud_1.normalizeAWS)(rawEvent);
            case "crowdstrike":
                return (0, cloud_1.normalizeCrowdStrike)(rawEvent);
            case "m365":
                return (0, identity_1.normalizeM365)(rawEvent);
            case "ad":
            case "active_directory":
                return (0, identity_1.normalizeAD)(rawEvent);
            case "network":
                return (0, structured_1.normalizeNetwork)(rawEvent);
            default:
                return (0, structured_1.normalizeUnknown)(rawEvent);
        }
    }
}
exports.NormalizationService = NormalizationService;
//# sourceMappingURL=normalize.js.map