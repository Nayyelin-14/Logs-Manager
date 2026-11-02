import { Source } from "../generated/prisma";
import type { SecurityEventInput } from "./normalization/helpers";
import {
  normalizeAPI,
  normalizeNetwork,
  normalizeSyslog,
  normalizeUnknown,
} from "./normalization/structured";
import {
  normalizeAWS,
  normalizeCrowdStrike,
} from "./normalization/cloud";
import { normalizeAD, normalizeM365 } from "./normalization/identity";

export type { SecurityEventInput } from "./normalization/helpers";

export class NormalizationService {
  static normalizeEvent(rawEvent: any, source: Source): SecurityEventInput {
    const sourceKey = String(source ?? "").toLowerCase();

    switch (sourceKey) {
      case "firewall":
      case "syslog":
        return normalizeSyslog(rawEvent);
      case "api":
        return normalizeAPI(rawEvent);
      case "aws":
        return normalizeAWS(rawEvent);
      case "crowdstrike":
        return normalizeCrowdStrike(rawEvent);
      case "m365":
        return normalizeM365(rawEvent);
      case "ad":
      case "active_directory":
        return normalizeAD(rawEvent);
      case "network":
        return normalizeNetwork(rawEvent);
      default:
        return normalizeUnknown(rawEvent);
    }
  }
}
