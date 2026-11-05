import { z } from "zod";

export const LoginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;

// User creation schema
export const CreateSchema = z.object({
  username: z.string().min(1, "Full name is required"),
  email: z.string().email("Invalid email address"),
  tenant: z.string().min(1, "Tenant is required"),
  role: z.enum(["USER", "ADMIN"], { errorMap: () => ({ message: "Select a role" }) }),
  password: z.string().min(1, "Password is required"),
  confirmPassword: z.string().min(1, "Confirm password is required"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

export type CreateUserFormValues = z.infer<typeof CreateSchema>;