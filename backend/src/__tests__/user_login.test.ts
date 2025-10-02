import { Request, Response, NextFunction } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { loginUser } from "../controllers/auth/auth.con";
import { getUserByEmail } from "../services/auth.service";
import { checkUserIfNotExist } from "../utils/auth.utils";

// Mock dependencies
jest.mock("bcryptjs");
jest.mock("jsonwebtoken");
jest.mock("../services/auth.service.ts");
jest.mock("../utils/auth.utils.ts");

describe("loginUser Controller", () => {
  let mockReq: Partial<Request>;
  let mockRes: Partial<Response>;
  let mockNext: NextFunction;
  let jsonMock: jest.Mock;
  let statusMock: jest.Mock;
  let cookieMock: jest.Mock;

  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();

    // Setup mock response methods
    jsonMock = jest.fn();
    statusMock = jest.fn().mockReturnThis();
    cookieMock = jest.fn().mockReturnThis();

    mockReq = {
      body: {},
    };

    mockRes = {
      status: statusMock,
      json: jsonMock,
      cookie: cookieMock,
    };

    mockNext = jest.fn();

    // Setup environment variables
    process.env.ACCESS_TOKEN_SECRET = "test-access-secret";
    process.env.REFRESH_TOKEN_SECRET = "test-refresh-secret";
    process.env.NODE_ENV = "development";
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe("Validation Tests", () => {
    it("should return 400 if email is missing", async () => {
      mockReq.body = { password: "password123" };

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Email and password are required",
      });
    });

    it("should return 400 if password is missing", async () => {
      mockReq.body = { email: "test@example.com" };

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Email and password are required",
      });
    });

    it("should return 400 if both email and password are missing", async () => {
      mockReq.body = {};

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Email and password are required",
      });
    });
  });

  describe("Authentication Tests", () => {
    const mockUser = {
      id: "123",
      email: "test@example.com",
      username: "testuser",
      password: "$2b$10$hashedpassword",
      tenant: "tenant1",
      role: "user",
    };

    beforeEach(() => {
      mockReq.body = {
        email: "test@example.com",
        password: "password123",
      };
    });

    it("should handle user not found error", async () => {
      (getUserByEmail as jest.Mock).mockResolvedValue(null);
      (checkUserIfNotExist as jest.Mock).mockImplementation(() => {
        throw new Error("User not found");
      });

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(getUserByEmail).toHaveBeenCalledWith("test@example.com");
      expect(checkUserIfNotExist).toHaveBeenCalledWith(null);
      expect(statusMock).toHaveBeenCalledWith(500);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "User not found",
        isSuccess: false,
      });
    });

    it("should return 401 if password is invalid", async () => {
      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockResolvedValue(false);

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(bcrypt.compare).toHaveBeenCalledWith(
        "password123",
        mockUser.password
      );
      expect(statusMock).toHaveBeenCalledWith(401);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Invalid credentials",
      });
    });

    it("should successfully login user with valid credentials", async () => {
      const mockAccessToken = "mock-access-token";
      const mockRefreshToken = "mock-refresh-token";

      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockResolvedValue(true);
      (jwt.sign as jest.Mock)
        .mockReturnValueOnce(mockAccessToken)
        .mockReturnValueOnce(mockRefreshToken);

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      // Verify JWT tokens were created with correct payload
      const expectedPayload = {
        userId: mockUser.id,
        email: mockUser.email,
        tenant: mockUser.tenant,
        role: mockUser.role,
      };

      expect(jwt.sign).toHaveBeenCalledTimes(2);
      expect(jwt.sign).toHaveBeenCalledWith(
        expectedPayload,
        "test-access-secret",
        { expiresIn: 900 }
      );
      expect(jwt.sign).toHaveBeenCalledWith(
        expectedPayload,
        "test-refresh-secret",
        { expiresIn: "30d" }
      );

      // Verify cookies were set
      expect(cookieMock).toHaveBeenCalledTimes(2);
      expect(cookieMock).toHaveBeenCalledWith("accessToken", mockAccessToken, {
        httpOnly: true,
        secure: false,
        sameSite: "strict",
        maxAge: 15 * 60 * 1000,
      });
      expect(cookieMock).toHaveBeenCalledWith(
        "refreshToken",
        mockRefreshToken,
        {
          httpOnly: true,
          secure: false,
          sameSite: "strict",
          maxAge: 30 * 24 * 60 * 60 * 1000,
        }
      );

      // Verify response
      expect(statusMock).toHaveBeenCalledWith(201);
      expect(jsonMock).toHaveBeenCalledWith({
        message: `Welcome back!!! ${mockUser.username}`,
        userData: {
          id: mockUser.id,
          email: mockUser.email,
          username: mockUser.username,
          tenant: mockUser.tenant,
          role: mockUser.role,
        },
      });
    });

    it("should set secure cookies in production environment", async () => {
      process.env.NODE_ENV = "production";
      const mockAccessToken = "mock-access-token";
      const mockRefreshToken = "mock-refresh-token";

      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockResolvedValue(true);
      (jwt.sign as jest.Mock)
        .mockReturnValueOnce(mockAccessToken)
        .mockReturnValueOnce(mockRefreshToken);

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(cookieMock).toHaveBeenCalledWith("accessToken", mockAccessToken, {
        httpOnly: true,
        secure: true,
        sameSite: "none",
        maxAge: 15 * 60 * 1000,
      });
      expect(cookieMock).toHaveBeenCalledWith(
        "refreshToken",
        mockRefreshToken,
        {
          httpOnly: true,
          secure: true,
          sameSite: "none",
          maxAge: 30 * 24 * 60 * 60 * 1000,
        }
      );
    });

    it("should not include password in response userData", async () => {
      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockResolvedValue(true);
      (jwt.sign as jest.Mock).mockReturnValue("token");

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(jsonMock).toHaveBeenCalledWith(
        expect.objectContaining({
          userData: expect.not.objectContaining({
            password: expect.anything(),
          }),
        })
      );
    });
  });

  describe("Error Handling Tests", () => {
    it("should handle unexpected errors", async () => {
      mockReq.body = {
        email: "test@example.com",
        password: "password123",
      };

      const errorMessage = "Database connection failed";
      (getUserByEmail as jest.Mock).mockRejectedValue(new Error(errorMessage));

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(500);
      expect(jsonMock).toHaveBeenCalledWith({
        message: errorMessage,
        isSuccess: false,
      });
    });

    it("should handle bcrypt comparison error", async () => {
      const mockUser = {
        id: "123",
        email: "test@example.com",
        username: "testuser",
        password: "$2b$10$hashedpassword",
        tenant: "tenant1",
        role: "user",
      };

      mockReq.body = {
        email: "test@example.com",
        password: "password123",
      };

      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockRejectedValue(
        new Error("Bcrypt error")
      );

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(500);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Bcrypt error",
        isSuccess: false,
      });
    });

    it("should handle JWT signing error", async () => {
      const mockUser = {
        id: "123",
        email: "test@example.com",
        username: "testuser",
        password: "$2b$10$hashedpassword",
        tenant: "tenant1",
        role: "user",
      };

      mockReq.body = {
        email: "test@example.com",
        password: "password123",
      };

      (getUserByEmail as jest.Mock).mockResolvedValue(mockUser);
      (checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
      (bcrypt.compare as jest.Mock).mockResolvedValue(true);
      (jwt.sign as jest.Mock).mockImplementation(() => {
        throw new Error("JWT signing failed");
      });

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(500);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "JWT signing failed",
        isSuccess: false,
      });
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty string email", async () => {
      mockReq.body = {
        email: "",
        password: "password123",
      };

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Email and password are required",
      });
    });

    it("should handle empty string password", async () => {
      mockReq.body = {
        email: "test@example.com",
        password: "",
      };

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
      expect(jsonMock).toHaveBeenCalledWith({
        message: "Email and password are required",
      });
    });

    it("should handle whitespace-only email", async () => {
      mockReq.body = {
        email: "   ",
        password: "password123",
      };

      await loginUser(mockReq as any, mockRes as Response, mockNext);

      expect(statusMock).toHaveBeenCalledWith(400);
    });
  });
});
