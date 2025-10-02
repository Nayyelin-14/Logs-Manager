import { CookieOptions, NextFunction, Request, Response } from "express";
import { JwtPayload } from "jsonwebtoken";
import jwt from "jsonwebtoken";
import { handleError } from "./errorHandeling";
import { getUserByEmail } from "../services/auth.service";
import { checkUserIfNotExist } from "./auth.utils";
import { errorCode } from "../config/errrorcode";

export interface TokenPayload extends JwtPayload {
  userId: number;
  role: string;
  tenant: string;
  email: string;
  username?: string;
}

export interface CustomRequest extends Request {
  user?: TokenPayload;
}

export const generateNewToken = async (
  oldRefreshToken: string,
  req: CustomRequest,
  res: Response,
  next: NextFunction
) => {
  let decoded;
  if (!oldRefreshToken) {
    return next(
      handleError("Not an authenticated user", 401, errorCode.unthenticated)
    );
  }
  try {
    decoded = jwt.verify(
      oldRefreshToken,
      process.env.REFRESH_TOKEN_SECRET!
    ) as TokenPayload;
  } catch (error) {
    return next(
      handleError("Not an authenticated user", 401, errorCode.unthenticated)
    );
  }

  const user = await getUserByEmail(decoded.email);
  await checkUserIfNotExist(user);

  const validUser = user?.email === decoded.email;

  if (!validUser) {
    return next(
      handleError("Not an authenticated user", 401, errorCode.unthenticated)
    );
  }

  const TokenPayload = {
    userId: user!.id,
    email: user!.email,
    tenant: user!.tenant,
    role: user!.role,
  };
  const NewAccessToken = jwt.sign(
    TokenPayload,
    process.env.ACCESS_TOKEN_SECRET!,
    { expiresIn: 60 * 15 }
  );

  const NewRefreshToken = jwt.sign(
    TokenPayload,
    process.env.REFRESH_TOKEN_SECRET!,
    { expiresIn: "30d" }
  );
  const option: CookieOptions = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? "none" : "strict",
  };
  res
    .cookie("accessToken", NewAccessToken, {
      ...option,
      maxAge: 15 * 60 * 1000, // 15 minutes
    })
    .cookie("refreshToken", NewRefreshToken, {
      ...option,
      maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
    });
  req.cookies = {
    ...req.cookies,
    accessToken: NewAccessToken,
  };
  req.user = {
    userId: user!.id,
    email: user!.email,
    tenant: user!.tenant!,
    role: user!.role,
  };

  next();
};
