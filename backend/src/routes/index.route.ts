import { Router } from "express";
import authRoutes from "./auth.route";
import logRoutes from "./logs.route";
import manageRoutes from "./manage.route";
import alertRoutes from "./alert.route";
import authMiddleware from "../middleware/isAuth";
import { authroiseMiddleware } from "../middleware/authorization";
const route = Router();

route.use("/api/auth", authRoutes);
route.use("/api", authMiddleware, logRoutes);
route.use(
  "/api",
  authMiddleware,
  authroiseMiddleware(true, "ADMIN"),
  manageRoutes
);

route.use(
  "/api",
  authMiddleware,
  authroiseMiddleware(true, "ADMIN"),
  alertRoutes
);
export default route;
