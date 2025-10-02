import { NextFunction, Request, Response } from "express";
import { getUserById } from "../../services/auth.service";

import { checkUserIfNotExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import { CustomRequest } from "../../utils/refreshToken";

export const authcheck = async (
  req: CustomRequest,
  res: Response,
  next: NextFunction
) => {
  const userId = req.user?.userId;

  if (!userId) {
    const error: any = new Error("Unauthenticated User");
    error.status = 400;
    error.code = errorCode.unthenticated;
    return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
  }
  const user = await getUserById(userId!);
  await checkUserIfNotExist(user);

  return res.status(200).json({ message: "Authenticated user", user });
};
