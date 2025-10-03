import { Response } from "express";
import { CustomRequest } from "../utils/refreshToken";
import * as alertService from "../services/alert.service";
import * as authService from "../services/auth.service";
import * as authUtils from "../utils/auth.utils";
import * as alertUtils from "../utils/alert.util";
import cacheQueue from "../jobs/queues/cacheQueue";
import { createAlertRule } from "../controllers/admin/alert.con";

// Mock dependencies
jest.mock("../services/alert.service");
jest.mock("../services/auth.service");
jest.mock("../utils/auth.utils");
jest.mock("../utils/alert.util");
jest.mock("../jobs/queues/cacheQueue", () => ({
  __esModule: true,
  default: { add: jest.fn() },
}));

describe("createAlertRule controller", () => {
  let req: Partial<CustomRequest>;
  let res: Partial<Response>;
  let next: jest.Mock;

  const handler = createAlertRule[createAlertRule.length - 1];

  beforeEach(() => {
    req = {
      body: {
        name: "Test Rule",
        tenant: "Tenant1",
        description: "Sample rule",
        conditions: [{ type: "LOGIN_FAIL", threshold: 3 }],
      },
      user: { userId: 1 } as any,
    };

    res = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn(),
    };

    next = jest.fn();

    jest.clearAllMocks();
  });

  it("should create an alert rule successfully", async () => {
    (authService.getUserById as jest.Mock).mockResolvedValue({
      id: 1,
      name: "Admin",
    });
    (authUtils.checkUserIfNotExist as jest.Mock).mockResolvedValue(undefined);
    (alertService.getExistedAlertRule as jest.Mock).mockResolvedValue(null);
    (alertUtils.checkExistedAlertRule as jest.Mock).mockResolvedValue(
      undefined
    );
    (alertService.createNewAlertRule as jest.Mock).mockResolvedValue({
      id: 1,
      name: "Test Rule",
    });

    await handler(req as CustomRequest, res as Response, next);

    expect(authService.getUserById).toHaveBeenCalledWith(1);
    expect(alertService.getExistedAlertRule).toHaveBeenCalledWith({
      tenant: "Tenant1",
      name: "Test Rule",
    });
    expect(alertService.createNewAlertRule).toHaveBeenCalledWith({
      name: "Test Rule",
      tenant: "Tenant1",
      description: "Sample rule",
      conditions: [{ type: "LOGIN_FAIL", threshold: 3 }],
    });
    expect(cacheQueue.add).toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(201);
    expect(res.json).toHaveBeenCalledWith({
      message: "Alert rule is created",
      createdRule: { id: 1, name: "Test Rule" },
    });
  });

  it("should return 401 if user is not authenticated", async () => {
    req.user = undefined;

    await handler(req as CustomRequest, res as Response, next);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(res.json).toHaveBeenCalledWith({ message: "Unauthenticated User" });
  });

  it("should return 500 if an error occurs", async () => {
    (authService.getUserById as jest.Mock).mockRejectedValue(
      new Error("DB error")
    );

    await handler(req as CustomRequest, res as Response, next);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith({ message: "Internal server error" });
  });
});
