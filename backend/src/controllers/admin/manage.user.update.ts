import { NextFunction, Response } from "express";
import { body, param, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import {
  deleteUserById,
  getUserById,
  updateUser,
} from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import cacheQueue from "../../jobs/queues/cacheQueue";

export const updateUserController = [
  body("userId").notEmpty().withMessage("User ID is required").isInt(),
  body("username")
    .optional()
    .isString()
    .withMessage("Username must be a string"),
  body("email").optional().isEmail().withMessage("Invalid email"),
  body("role")
    .optional()
    .isIn(["USER", "ADMIN"])
    .withMessage("Role must be USER or ADMIN"),
  body("status")
    .optional()
    .isIn(["FREEZE", "INACTIVE", "ACTIVE"])
    .withMessage("Invalid status"),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req).array({ onlyFirstError: true });

      if (errors.length > 0) {
        const error: any = new Error(errors[0].msg);
        error.status = 400;
        error.code = errorCode.invalid;
        return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
      }
      // Auth check: only admins
      const currentUser = req.user; // assume you attach currentUser in middleware
      if (!currentUser || currentUser.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId, username, email, role, status, tenant } = req.body;

      // Check if user exists
      const existedUser = await getUserById(userId);
      await checkUserIfNotExist(existedUser);

      // Prepare update data
      const updateData: any = {};
      if (username !== undefined) updateData.username = username;
      if (email !== undefined) updateData.email = email;

      if (role !== undefined) updateData.role = role;
      if (tenant !== undefined) updateData.tenant = tenant;
      if (status !== undefined) updateData.status = status;

      // Update user
      const updatedUserData = await updateUser(updateData, userId);

      return res.status(200).json({
        success: true,
        message: "User updated successfully",
        user: updatedUserData,
      });
    } catch (error) {
      console.error("Error updating user:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];
export const deleteUser = [
  param("userId").notEmpty().withMessage("User ID is required").isInt(),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      // Auth check: only admins
      if (!req.user || req.user.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId } = req.params;

      // Check if user exists
      const existedUser = await getUserById(Number(userId));
      await checkUserIfNotExist(existedUser);

      // Delete user
      const userdeletion = await deleteUserById(Number(userId));
      await cacheQueue.add(
        "invalidate-user-cache",
        {
          pattern: "users:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );
      return res
        .status(200)
        .json({ success: true, message: "User deleted", data: userdeletion });
    } catch (error) {
      console.error("Error deleting user:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];
