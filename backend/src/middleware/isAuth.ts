import { PrismaClient } from "@prisma/client";
import jwt, { JwtPayload } from "jsonwebtoken";
import { Request, Response, NextFunction } from "express";
import { handleError } from "../utils/errorHandeling";

import { generateNewToken } from "../utils/refreshToken";
import { errorCode } from "../config/errrorcode";
const prisma = new PrismaClient();

interface TokenPayload extends JwtPayload {
  userId: number;
  role: string;
  tenant: string;
  email: string;
}

interface CustomRequest extends Request {
  user?: TokenPayload;
}
async function authMiddleware(
  req: CustomRequest,
  res: Response,
  next: NextFunction
) {
  const accessToken = req.cookies?.accessToken || null;
  const refreshToken = req.cookies?.refreshToken || null;

  if (!refreshToken) {
    return next(
      handleError(
        "Unauthenticated user. Try Again!!!",
        401,
        errorCode.unthenticated
      )
    );
  }
  let decoded;
  try {
    if (accessToken) {
      decoded = jwt.verify(
        accessToken,
        process.env.ACCESS_TOKEN_SECRET!
      ) as TokenPayload;
      req.user = {
        userId: decoded.userId,
        role: decoded.role,
        tenant: decoded.tenant,
        email: decoded.email,
      };
      return next();
    } else {
      throw new jwt.TokenExpiredError("AccessToken Missing", new Date());
    }
  } catch (error: any) {
    if (
      error.name === "TokenExpiredError" ||
      error.name === "JsonWebTokenError"
    ) {
      try {
        await generateNewToken(refreshToken, req, res, () => {});
        const newAccessToken = req.cookies?.accessToken;
        if (!newAccessToken) {
          return next(
            handleError(
              "New Token refresh failed",
              401,
              errorCode.unthenticated
            )
          );
        }

        // Step 3: Verify new access token
        decoded = jwt.verify(
          newAccessToken,
          process.env.ACCESS_TOKEN_SECRET!
        ) as TokenPayload;
        req.user = {
          userId: decoded.userId,
          role: decoded.role,
          tenant: decoded.tenant,
          email: decoded.email,
        };
        return next();
      } catch (refreshError) {
        return next(
          handleError("Token refresh failed", 401, errorCode.unthenticated)
        );
      }
    }
  }
}

export const requireRole = (roles: string[]) => {
  return (req: CustomRequest, res: Response, next: NextFunction) => {
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({ error: "Insufficient permissions" });
    }
    next();
  };
};
export const requireTenant = (
  req: CustomRequest,
  res: Response,
  next: NextFunction
) => {
  const tenant =
    (req.query.tenant as string) ||
    (req.body.tenant as string) ||
    (req.cookies?.tenant as string);

  if (!tenant) {
    return res.status(400).json({ error: "Tenant parameter required" });
  }

  if (req.user?.role !== "ADMIN" && !req.user?.tenants.includes(tenant)) {
    return res.status(403).json({ error: "Access denied to this tenant" });
  }

  next();
};
export default authMiddleware;
