import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { CookieOptions, NextFunction, Response } from "express";
import { getUserByEmail } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { CustomRequest } from "../../utils/refreshToken";
import { prisma } from "../../config/PrismaClient";

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
    if (user?.status && user.status !== "ACTIVE") {
      return res.status(403).json({ message: "This account is not active." });
    }

    // Check password
    const isPasswordValid = await bcrypt.compare(
      inputPassword,
      user?.password!
    );

    if (!isPasswordValid)
      return res.status(401).json({ message: "Invalid credentials" });

    const Payload = {
      userId: user?.id,
      username: user?.username,
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
