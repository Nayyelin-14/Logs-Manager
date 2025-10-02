import { errorCode } from "../config/errrorcode";
import { handleError } from "./errorHandeling";

export const checkUserExist = async (user: any) => {
  if (user) {
    throw handleError(
      "This email number is already in use",
      409,
      errorCode.userExist
    );
  }
};

export const checkUserIfNotExist = async (user: any) => {
  if (!user) {
    throw handleError(
      "User not found.Try Again!!!",
      409,
      errorCode.unthenticated
    );
  }
};
export const checkOtpExist = async (otp: any) => {
  if (!otp) {
    throw handleError(
      "Something went wrong with one time password",
      400,
      errorCode.invalid
    );
  }
};

export const checkLogIfNotExist = async (log: any) => {
  if (!log) {
    throw handleError(
      "Log not found.Try Again!!!",
      409,
      errorCode.unthenticated
    );
  }
};
