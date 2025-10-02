import z from "zod";

export const LoginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  password: z
    .string()
    .min(8, "Password must be 8 digit")
    .max(8, "Password must be 8 digit")
    .regex(/^\d+$/, "Password  must be a number"),
});

// 🔹 Enums
export const RoleEnum = z.enum(["ADMIN", "USER"]);
export const StatusEnum = z.enum(["ACTIVE", "INACTIVE", "SUSPENDED"]);

// 🔹 User Schema
export const RegisterSchema = z.object({
  username: z.string().min(1, "Name is too short").max(100, "Name is too long"), // Optional string
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  tenant: z
    .string()
    .min(1, "Tenant name is too short")
    .max(100, "Tenant name is too long"), // Optional unique string
});

export const confirmPwdSchema = z.object({
  password: z
    .string()
    .min(8, "Password must be 8 digit")
    .max(8, "Password must be 8 digit")
    .regex(/^\d+$/, "Password  must be a number"),
  confirmPassword: z
    .string()
    .min(8, "Password must be 8 digit")
    .max(8, "Password must be 8 digit")
    .regex(/^\d+$/, "Password  must be a number"),
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
  password: z
    .string()
    .min(8, "Password must be 8 digit")
    .max(8, "Password must be 8 digit")
    .regex(/^\d+$/, "Password  must be a number"),
  confirmPassword: z
    .string()
    .min(8, "Password must be 8 digit")
    .max(8, "Password must be 8 digit")
    .regex(/^\d+$/, "Password  must be a number"),
});
