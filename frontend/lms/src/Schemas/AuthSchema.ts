import z from "zod";

const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(128, "Password is too long")
  .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
  .regex(/[a-z]/, "Password must contain at least one lowercase letter")
  .regex(/[0-9]/, "Password must contain at least one number")
  .regex(/[^A-Za-z0-9]/, "Password must contain at least one special character");

export const LoginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

// 🔹 Enums
export const RoleEnum = z.enum(["ADMIN", "USER"]);
export const StatusEnum = z.enum(["ACTIVE", "INACTIVE", "SUSPENDED"]);

// 🔹 User Schema
export const RegisterSchema = z.object({
  username: z.string().min(1, "Name is too short").max(100, "Name is too long"),
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  tenant: z
    .string()
    .min(1, "Tenant name is too short")
    .max(100, "Tenant name is too long"),
});

export const confirmPwdSchema = z.object({
  password: passwordSchema,
  confirmPassword: z.string().min(1, "Please confirm your password"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

export const otpSchema = z.object({
  otp: z
    .string()
    .length(6, "OTP must be exactly 6 digits")
    .regex(/^\d+$/, "OTP must contain only numbers"),
});

export const CreateSchema = z.object({
  role: RoleEnum.default("USER").optional(),
  username: z.string().min(1, "Name is too short").max(100, "Name is too long"),
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  tenant: z
    .string()
    .min(1, "Tenant name is too short")
    .max(100, "Tenant name is too long"),
  password: passwordSchema,
  confirmPassword: z.string().min(1, "Please confirm your password"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});
