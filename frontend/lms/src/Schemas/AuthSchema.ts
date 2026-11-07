import { z } from "zod";

export const LoginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;

// Role enum for the API - matches backend ADMIN/VIEWER
export const RoleEnum = z.enum(["VIEWER", "ADMIN"]);

// User creation schema
export const CreateSchema = z.object({
  username: z.string().min(1, "Full name is required"),
  email: z.string().email("Invalid email address"),
  tenant: z.string().min(1, "Tenant is required"),
  role: RoleEnum.default("VIEWER"),
  password: z.string().min(1, "Password is required"),
  confirmPassword: z.string().min(1, "Confirm password is required"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

export type CreateUserFormValues = z.infer<typeof CreateSchema>;
export type CreateUserFormInput = z.input<typeof CreateSchema>;