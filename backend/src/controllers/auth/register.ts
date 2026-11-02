import bcrypt from "bcryptjs";
import { NextFunction, Request, Response } from "express";
import { body, validationResult } from "express-validator";
import moment from "moment/moment";
import {
  getOtpByEmail,
  getUserByEmail,
  storeOtp,
  updateOtp,
} from "../../services/auth.service";
import {
  checkOtpExist,
  checkUserExist,
} from "../../utils/auth.utils";
import { generateOTP, generateToken } from "../../utils/generateOTP";
import { OtpEmailQueue } from "../../utils/queueHelper";
import { prisma } from "../../config/PrismaClient";

export const registerUser = [
  body("username")
    .trim()
    .notEmpty()
    .withMessage("Name is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Name must be between 2 and 50 characters"),
  body("email")
    .trim()
    .notEmpty()
    .withMessage("Email is required")
    .isEmail()
    .withMessage("Invalid email address"),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),

  async (req: Request, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      const error: any = new Error(errors[0].msg);
      error.status = 400;
      error.code = "Invalid_Error";
      return next(error);
    }
    const { email, tenant, username } = req.body;
    if (!email || !tenant || !username) {
      return res.status(403).json({
        message: "All fields are required",
      });
    }
    const user = await getUserByEmail(email);

    await checkUserExist(user);

    //generate OTP function
    const otp = generateOTP();
    //hash otp
    const salt = await bcrypt.genSalt(10);
    const hashedOtp = await bcrypt.hash(otp.toString(), salt);

    //generate Token function
    const token = generateToken();

    const otpHistory = await getOtpByEmail(email);

    let otpResult;
    if (!otpHistory) {
      //store  new  otp data if there is no otp request history
      const otpData = {
        optCode: hashedOtp,
        email,
        rememberToken: token,
        count: 1,
      };

      otpResult = await storeOtp(otpData);
      await OtpEmailQueue({
        email: otpResult.email,
        otp,
        otpId: otpResult.id,
      });
    } else {
      //if there is otp request history
      //otp is wrong 5 times in one day
      const lastRequestDate = new Date(otpHistory.updatedAt)
        .toISOString()
        .split("T")[0];
      const currentDate = new Date().toISOString().split("T")[0];
      const isSameDate = lastRequestDate === currentDate;
      if (isSameDate && otpHistory.error > 5) {
        return res.status(403).json({
          message: "OTP is wrong for 5 times. Try again after 24 hours",
        });
      }

      if (!isSameDate) {
        //reset error count and store new otp if not the same date
        const updateotpData = {
          optCode: hashedOtp,
          rememberToken: token,
          count: 1,
          error: 0,
        };
        otpResult = await updateOtp(updateotpData, otpHistory.id);
      } else {
        if (otpHistory.count === 3) {
          const error: any = new Error(
            "OTP is allowed to request to 3 times per day.Try again later"
          );
          error.status = 429;
          error.code = "Exceed_Limit";
          return next(error);
        } else {
          const updateotpData = {
            optCode: hashedOtp,
            rememberToken: token,
            count: {
              increment: 1,
            },
            error: 0,
          };
          otpResult = await updateOtp(updateotpData, otpHistory.id);
        }
      }
      await OtpEmailQueue({
        email: otpResult.email,
        otp,
        otpId: otpResult.id,
      });
    }

    return res.status(200).json({
      message: `We are sending otp to ${otpResult.email}`,
      userData: otpResult,
      tenant,
      username,
      token: otpResult.rememberToken,
    });
  },
];
export const veridyOtp = [
  body("username")
    .trim()
    .notEmpty()
    .withMessage("Name is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Name must be between 2 and 50 characters"),
  body("email")
    .trim()
    .notEmpty()
    .withMessage("Email is required")
    .isEmail()
    .withMessage("Invalid email address"),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),
  body("otp", "Invalid OTP")
    .trim()
    .notEmpty()
    .matches(/^[0-9]+$/)
    .isLength({ min: 6, max: 6 }),
  body("token", "Invalid token").trim().notEmpty().escape(),
  async (req: Request, res: Response, next: NextFunction) => {
    const errors = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      const error: any = new Error(errors[0].msg);
      error.status = 400;
      error.code = "Invalid_Error";
      return next(error);
    }

    const { otp, token, email } = req.body;

    const user = await getOtpByEmail(email);
    await checkOtpExist(user);

    //there must have otp to verify

    const existedOtp = await getOtpByEmail(user!.email);
    await checkOtpExist(existedOtp);

    const lastVerifyDate = new Date(existedOtp!.updatedAt)
      .toISOString()
      .split("T")[0];
    const currentDate = new Date().toISOString().split("T")[0];

    const isSameDate = lastVerifyDate === currentDate;
    if (isSameDate && existedOtp!.error > 5) {
      return res.status(403).json({
        message: "OTP is wrong for 5 times. Try again after 24 hours",
        isSuccess: false,
      });
    }
    //-------//

    //check token //

    if (existedOtp?.rememberToken !== token) {
      //if token is wrong , error and can't be verify again
      const otpData = {
        error: 5,
      };
      await prisma.otp.update({
        where: { id: existedOtp!.id },
        data: otpData,
      });
      const error: any = new Error("Unauhorized OTP detected");
      error.status = 400;
      error.code = "Error_Invalid";
      return next(error);
    }
    //====//

    //check otp is expired over 2 minutes//
    const isOtpExpired = moment().diff(existedOtp?.updatedAt, "minutes") > 2;
    if (isOtpExpired) {
      return res
        .status(403)
        .json({ message: "One time password is expired", isSuccess: false });
    }
    //
    //check otp match or not
    const isOtpMatch = await bcrypt.compare(otp, existedOtp!.optCode);
    if (!isOtpMatch) {
      const otpData = isSameDate ? { error: { increment: 1 } } : { error: 1 };
      await updateOtp(otpData, existedOtp!.id);

      return res
        .status(403)
        .json({ message: "One time password is incorrect", isSuccess: false });
    }
    //
    //if everything ok , an otp must have verify token for that account is verified
    const verifiedToken = generateToken();
    const latestOtpData = {
      verifyToken: verifiedToken,
      count: 1,
      error: 0,
    };

    const latestOtpResult = await updateOtp(latestOtpData, existedOtp!.id);

    //

    return res.json({
      isSuccess: true,
      message: "OTP is successfully verified",

      token: latestOtpResult.verifyToken,
    });
  },
];
