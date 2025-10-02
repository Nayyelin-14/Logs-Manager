import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";

import { getUserById } from "../services/auth.service";
import { checkUserIfNotExist } from "../utils/auth.utils";
import { handleError } from "../utils/errorHandeling";
import { errorCode } from "../config/errrorcode";
import { CustomRequest } from "../utils/refreshToken";

export const authroiseMiddleware = (
  permission: boolean,
  ...roles: string[]
) => {
  return async (req: CustomRequest, res: Response, next: NextFunction) => {
    if (!req.user || !req.user.userId) {
      return res.status(401).json({ message: "Unauthorized" });
    }
    const user = await getUserById(req.user!.userId!);
    checkUserIfNotExist(user);

    const roleResult = roles.includes(user!.role);

    if ((permission && !roleResult) || (!permission && roleResult)) {
      return next(
        handleError("Unauthorized User", 401, errorCode.unauthorized)
      );
    }

    next();
  };
};
