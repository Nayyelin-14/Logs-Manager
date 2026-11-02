import { NextFunction, Response } from "express";
import { body, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import { createNewUser, getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import { handleError } from "../../utils/errorHandeling";
import bcrypt from "bcryptjs";
import cacheQueue from "../../jobs/queues/cacheQueue";

export const createUser = [
  body("username")
    .trim()
    .notEmpty()
    .withMessage("Name is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Name must be between 2 and 50 characters"),
  body("role", "Invalid role").isIn(["ADMIN", "USER"]).optional(),
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
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid));
    }
    const { email, username, role, tenant, password, confirmPassword } =
      req.body;

    if (!email || !username || !tenant || !password || !confirmPassword) {
      return res.status(400).json({ message: "All field sare required" });
    }
    const userId = req.user?.userId;

    const user = await getUserById(Number(userId!));
    await checkUserIfNotExist(user);

    if (user?.role !== "ADMIN") {
      return next(
        handleError("Unauthorized user detected ", 400, errorCode.unauthorized)
      );
    }
    if (password !== confirmPassword) {
      return res.status(400).json({ message: "Passwords do not  match" });
    }
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUserData = {
      username,
      email,
      password: hashedPassword,
      tenant,
      role,
    };
    const newUser = await createNewUser(newUserData);
    const { password: _storedPassword, ...safeUser } = newUser;

    await cacheQueue.add(
      "invalidate-post-cache",
      {
        pattern: "users:*",
      },
      {
        jobId: `invalidate-${Date.now()}`,
        priority: 1,
      }
    );
    return res.status(201).json({
      message: "New user created successfully",
      newUser: safeUser,
    });
  },
];
