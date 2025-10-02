import { errorCode } from "../config/errrorcode";
import { handleError } from "./errorHandeling";

export const checkExistedAlertRule = async (rule: any) => {
  if (!rule) {
    throw handleError(
      "This rule is already existed.",
      400,
      errorCode.existedRule
    );
  }
};

export function getSeverityLevel(severity?: number): string {
  if (severity === undefined || severity === null) return "Unknown";

  if (severity >= 0 && severity <= 3) return "Low";
  if (severity >= 4 && severity <= 7) return "Medium";
  if (severity >= 8 && severity <= 10) return "High";

  return "Unknown";
}
