import { Request, Response } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";

import { getUserByEmail } from "../services/auth.service";
import { checkUserIfNotExist } from "../utils/auth.utils";
import { loginUser } from "../controllers/auth/auth.con";

// Mock external dependencies
jest.mock("bcryptjs");
jest.mock("jsonwebtoken");
jest.mock("../services/auth.service");
jest.mock("../utils/auth.utils");

describe("loginUser Controller", () => {
  let mockReq: Partial<Request>;
  let mockRes: Partial<Response>;
  let mockNext: jest.Mock;
  let statusMock: jest.Mock;
  let jsonMock: jest.Mock;
  let cookieMock: jest.Mock;

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Mock response methods
    jsonMock = jest.fn();
    statusMock = jest.fn().mockReturnThis();
    cookieMock = jest.fn().mockReturnThis();

    mockRes = {
      status: statusMock,
      json: jsonMock,
      cookie: cookieMock,
    };

    mockNext = jest.fn();

    // Default request body
    mockReq = {
      body: {},
    };

    // Environment
    process.env.ACCESS_TOKEN_SECRET = "test-access-secret";
    process.env.REFRESH_TOKEN_SECRET = "test-refresh-secret";
    process.env.NODE_ENV = "development";
  });

  /** Validation Tests */
  it("should return 400 if email or password is missing", async () => {
    // Missing both
    await loginUser(mockReq as any, mockRes as Response, mockNext);
    expect(statusMock).toHaveBeenCalledWith(400);

    // Missing password
    mockReq.body = { email: "test@example.com" };
    await loginUser(mockReq as any, mockRes as Response, mockNext);
    expect(statusMock).toHaveBeenCalledWith(400);

    // Missing email
    mockReq.body = { password: "password123" };
    await loginUser(mockReq as any, mockRes as Response, mockNext);
    expect(statusMock).toHaveBeenCalledWith(400);
  });

  /** Authentication Tests */
  it("should return 401 if password is incorrect", async () => {
    const mockUser = {
      id: "1",
      email: "test@example.com",
      password: "hashed",
      username: "user",
      tenant: "t1",
      role: "user",
    };

    (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
    (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
    (bcrypt.compare as jest.Mock).mockResolvedValue(false);

    mockReq.body = { email: "test@example.com", password: "wrongpassword" };

    await loginUser(mockReq as any, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(401);
    expect(jsonMock).toHaveBeenCalledWith({ message: "Invalid credentials" });
  });

  it("should login successfully with valid credentials", async () => {
    const mockUser = {
      id: "1",
      email: "test@example.com",
      password: "hashed",
      username: "user",
      tenant: "t1",
      role: "user",
    };
    const mockAccessToken = "access-token";
    const mockRefreshToken = "refresh-token";

    (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
    (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
    (bcrypt.compare as jest.Mock).mockResolvedValue(true);
    (jwt.sign as jest.Mock)
      .mockReturnValueOnce(mockAccessToken)
      .mockReturnValueOnce(mockRefreshToken);

    mockReq.body = { email: "test@example.com", password: "password123" };

    await loginUser(mockReq as any, mockRes as Response, mockNext);

    // Check if tokens are created
    expect(jwt.sign).toHaveBeenCalledTimes(2);

    // Check if cookies were set
    expect(cookieMock).toHaveBeenCalledTimes(2);

    // Check final response
    expect(statusMock).toHaveBeenCalledWith(201);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining("Welcome back"),
        userData: expect.objectContaining({ email: mockUser.email }),
      })
    );
  });

  /** Error handling */
  it("should handle unexpected errors", async () => {
    (getUserByEmail as jest.Mock).mockRejectedValue(new Error("DB error"));

    mockReq.body = { email: "test@example.com", password: "password123" };

    await loginUser(mockReq as any, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(500);
    expect(jsonMock).toHaveBeenCalledWith({
      message: "DB error",
      isSuccess: false,
    });
  });
});
