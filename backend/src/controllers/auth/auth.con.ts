import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { CookieOptions } from "express";
import { NextFunction, Request, Response } from "express";
import { PrismaClient } from "@prisma/client";
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
  checkUserIfNotExist,
} from "../../utils/auth.utils";
import { generateOTP, generateToken } from "../../utils/generateOTP";

import { errorCode } from "../../config/errrorcode";
import { CustomRequest } from "../../utils/refreshToken";

import { OtpEmailQueue } from "../../utils/queueHelper";

const prisma = new PrismaClient();

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

export const confirmPassword = [
  body("email")
    .trim()
    .notEmpty()
    .withMessage("Email is required")
    .isEmail()
    .withMessage("Invalid email address"),
  body("username")
    .trim()
    .notEmpty()
    .withMessage("Name is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Name must be between 2 and 50 characters"),
  body("password", "Invalid Credentials")
    .trim()
    .notEmpty()
    .matches(/^[0-9]+$/)
    .isLength({ min: 8, max: 8 }),
  body("confirmPassword", "Invalid Credentials")
    .trim()
    .notEmpty()
    .matches(/^[0-9]+$/)
    .isLength({ min: 8, max: 8 }),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),

  body("token", "Invalid token").trim().notEmpty().escape(),
  async (req: Request, res: Response, next: NextFunction) => {
    const errors = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      const error: any = new Error(errors[0].msg);
      error.status = 400;
      error.code = errorCode.invalid;
      return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
    }
    console.log(errors);
    const { password, token, email, username, tenant, confirmPassword } =
      req.body;
    if (
      !password ||
      !token ||
      !email ||
      !username ||
      !tenant ||
      !confirmPassword
    ) {
      return res.status(400).json({ error: "Missing required fields" });
    }
    const user = await getUserByEmail(email);

    await checkUserExist(user);

    const otpResult = await getOtpByEmail(email);
    await checkOtpExist(otpResult);

    if (otpResult!.error > 5) {
      const error: any = new Error("Invalid crendentials");
      error.status = 400;
      error.code = errorCode.overLimit;
      return next(error);
    }
    if (otpResult?.verifyToken !== token) {
      //if token is wrong , error and can't be verify again
      const otpData = {
        error: 5,
      };
      await updateOtp(otpData, otpResult!.id);

      const error: any = new Error("Invalid Token");
      error.status = 400;
      error.code = errorCode.invalid;
      return next(error);
    }
    const isOtpExpired = moment().diff(otpResult?.updatedAt, "minutes") > 10; //lek shi a chain nk minute htoke pyy pee 10 mins htk kyee yin expired
    if (isOtpExpired) {
      const error: any = new Error("Your request is expired. Try again later");
      error.status = 403;
      error.code = errorCode.otpExpired;
      return next(error);
    }
    const isPasswordMatch = password === confirmPassword;
    if (!isPasswordMatch) {
      const error: any = new Error("Passwords do not match");
      error.status = 400;
      error.code = errorCode.invalid;
      return next(error);
    }

    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    const userData = { email, username, tenant, password: hashedPassword };
    const newUser = await prisma.user.create({
      data: userData,
    });

    const Payload = {
      userId: newUser.id,
      email: newUser!.email,
      tenant: newUser!.tenant,
      role: newUser!.role,
    };

    const generateAccessToken = jwt.sign(
      Payload,
      process.env.ACCESS_TOKEN_SECRET!,
      { expiresIn: 60 * 15 }
    );

    const generateRefreshToken = jwt.sign(
      Payload,
      process.env.REFRESH_TOKEN_SECRET!,
      { expiresIn: "30d" }
    );

    const option = {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: (process.env.NODE_ENV === "production" ? "none" : "strict") as
        | "none"
        | "strict",
    };

    return res
      .cookie("accessToken", generateAccessToken, {
        ...option,
        maxAge: 15 * 60 * 1000, // 15 minutes
      })
      .cookie("refreshToken", generateRefreshToken, {
        ...option,
        maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
      })
      .status(201)
      .json({
        message: "Successfully created a new account",
        userId: newUser.id,
        userData: newUser,
      });
  },
];
export const loginUser = async (
  req: CustomRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const email = req.body.email?.trim();
    const inputPassword = req.body.password?.trim();
    if (!email || !inputPassword)
      return res
        .status(400)
        .json({ message: "Email and password are required" });

    // Find user by email
    const user = await getUserByEmail(email);
    await checkUserIfNotExist(user);
    console.log(user);

    // Check password
    const isPasswordValid = await bcrypt.compare(
      inputPassword,
      user?.password!
    );

    if (!isPasswordValid)
      return res.status(401).json({ message: "Invalid credentials" });

    const Payload = {
      userId: user?.id,
      email: user?.email,
      tenant: user?.tenant,
      role: user?.role,
    };

    const generateAccessToken = jwt.sign(
      Payload,
      process.env.ACCESS_TOKEN_SECRET!,
      { expiresIn: 60 * 15 }
    );

    const generateRefreshToken = jwt.sign(
      Payload,
      process.env.REFRESH_TOKEN_SECRET!,
      { expiresIn: "30d" }
    );

    const option: CookieOptions = {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: (process.env.NODE_ENV === "production" ? "none" : "strict") as
        | "none"
        | "strict",
    };

    const { password, ...safeUser } = user!;
    return res
      .cookie("accessToken", generateAccessToken, {
        ...option,
        maxAge: 15 * 60 * 1000, // 15 minutes
      })
      .cookie("refreshToken", generateRefreshToken, {
        ...option,
        maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
      })
      .status(201)
      .json({
        message: `Welcome back!!! ${user?.username}`,
        userData: safeUser,
      });
  } catch (error: any) {
    return res.status(500).json({ message: error?.message, isSuccess: false });
  }
};
export const logout = async (
  req: CustomRequest,
  res: Response,
  next: NextFunction
) => {
  console.log(req.user);
  if (!req.user || !req.user.userId) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = req.user.userId!;
  const user = await prisma.user.findUnique({
    where: {
      id: userId,
    },
  });
  if (!user) return res.status(404).json({ message: "User not found" });

  const option: CookieOptions = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? "none" : "strict",
  };
  return res
    .clearCookie("refreshToken", option)
    .clearCookie("accessToken", option)
    .json({
      message: "Loggedout successfully",
    });
};

export const UserProfile = async (
  req: Request,
  res: Response,
  next: NextFunction
) => {};
export default {
  loginUser,
  UserProfile,
  registerUser,
  logout,
  veridyOtp,
  confirmPassword,
};
