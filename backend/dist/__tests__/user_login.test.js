"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const auth_service_1 = require("../services/auth.service");
const auth_utils_1 = require("../utils/auth.utils");
const auth_con_1 = require("../controllers/auth/auth.con");
// Mock external dependencies
jest.mock("bcryptjs");
jest.mock("jsonwebtoken");
jest.mock("../services/auth.service");
jest.mock("../utils/auth.utils");
describe("loginUser Controller", () => {
    let mockReq;
    let mockRes;
    let mockNext;
    let statusMock;
    let jsonMock;
    let cookieMock;
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
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
        expect(statusMock).toHaveBeenCalledWith(400);
        // Missing password
        mockReq.body = { email: "test@example.com" };
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
        expect(statusMock).toHaveBeenCalledWith(400);
        // Missing email
        mockReq.body = { password: "password123" };
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
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
        auth_service_1.getUserByEmail.mockResolvedValue(mockUser);
        auth_utils_1.checkUserIfNotExist.mockResolvedValue(undefined);
        bcryptjs_1.default.compare.mockResolvedValue(false);
        mockReq.body = { email: "test@example.com", password: "wrongpassword" };
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
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
        auth_service_1.getUserByEmail.mockResolvedValue(mockUser);
        auth_utils_1.checkUserIfNotExist.mockResolvedValue(undefined);
        bcryptjs_1.default.compare.mockResolvedValue(true);
        jsonwebtoken_1.default.sign
            .mockReturnValueOnce(mockAccessToken)
            .mockReturnValueOnce(mockRefreshToken);
        mockReq.body = { email: "test@example.com", password: "password123" };
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
        // Check if tokens are created
        expect(jsonwebtoken_1.default.sign).toHaveBeenCalledTimes(2);
        // Check if cookies were set
        expect(cookieMock).toHaveBeenCalledTimes(2);
        // Check final response
        expect(statusMock).toHaveBeenCalledWith(201);
        expect(jsonMock).toHaveBeenCalledWith(expect.objectContaining({
            message: expect.stringContaining("Welcome back"),
            userData: expect.objectContaining({ email: mockUser.email }),
        }));
    });
    /** Error handling */
    it("should handle unexpected errors", async () => {
        auth_service_1.getUserByEmail.mockRejectedValue(new Error("DB error"));
        mockReq.body = { email: "test@example.com", password: "password123" };
        await (0, auth_con_1.loginUser)(mockReq, mockRes, mockNext);
        expect(statusMock).toHaveBeenCalledWith(500);
        expect(jsonMock).toHaveBeenCalledWith({
            message: "DB error",
            isSuccess: false,
        });
    });
});
//# sourceMappingURL=user_login.test.js.map