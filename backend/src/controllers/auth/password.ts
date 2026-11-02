import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { NextFunction, Request, Response } from "express";
import { body, validationResult } from "express-validator";
import moment from "moment/moment";
import {
  getOtpByEmail,
  getUserByEmail,
  updateOtp,
} from "../../services/auth.service";
import { checkOtpExist, checkUserExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import { prisma } from "../../config/PrismaClient";

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
      username: newUser.username,
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

    const { password: _storedPassword, ...safeUser } = newUser;
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
        userData: safeUser,
      });
  },
];
