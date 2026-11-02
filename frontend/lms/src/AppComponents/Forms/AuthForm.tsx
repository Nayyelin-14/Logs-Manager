import { Link, useNavigation, useSubmit } from "react-router-dom";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";

import { cn } from "../../lib/utils";
import { LoginSchema, RegisterSchema } from "../../Schemas/AuthSchema";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { AuthPanel } from "../layout/AuthPanel";
import { PassworInput } from "./PasswordInput";

type FormName = "login" | "register";
interface AuthFormProps extends React.ComponentProps<"div"> {
  formName: FormName;
}

export function AuthForm({ formName, className, ...props }: AuthFormProps) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const submitting = navigation.state === "submitting";

  const defaultValues =
    formName === "login"
      ? { email: "", password: "" }
      : { username: "", email: "", tenant: "" };

  const schema = formName === "login" ? LoginSchema : RegisterSchema;
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  const authSubmit = (values: z.infer<typeof schema>) => {
    const actionUrl = formName === "login" ? "/login" : ".";
    const formData = new FormData();
    Object.entries(values).forEach(([key, value]) => {
      formData.append(key, value as string);
    });

    submit(formData, { method: "post", action: actionUrl });
  };

  const isLogin = formName === "login";

  return (
    <div className={cn("w-full", className)} {...props}>
      <AuthPanel
        eyebrow={isLogin ? "Workspace access" : "Create workspace access"}
        title={isLogin ? "Sign in to LogManager" : "Create your account"}
        description={
          isLogin
            ? "Use your workspace credentials to open the security console."
            : "Provision a tenant-scoped account for monitoring and triage."
        }
        footer={
          <div className="space-y-3">
            <p className="text-center text-xs text-ink-muted">
              {isLogin ? "New to LogManager? " : "Already have an account? "}
              <Link
                to={isLogin ? "/register" : "/login"}
                className="font-medium text-ink underline underline-offset-4 hover:text-brand"
              >
                {isLogin ? "Create an account" : "Sign in"}
              </Link>
            </p>
            <p className="text-center text-[10px] leading-5 text-ink-muted/80">
              By continuing, you agree to the{" "}
              <a href="#" className="underline underline-offset-2 hover:text-ink">
                Terms of Service
              </a>{" "}
              and{" "}
              <a href="#" className="underline underline-offset-2 hover:text-ink">
                Privacy Policy
              </a>
              .
            </p>
          </div>
        }
      >
        <Form {...form}>
          <form onSubmit={form.handleSubmit(authSubmit)} className="space-y-4">
            {!isLogin && (
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Display name</FormLabel>
                      <FormControl>
                        <Input placeholder="analyst" autoComplete="name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="tenant"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tenant</FormLabel>
                      <FormControl>
                        <Input placeholder="demoA" autoComplete="organization" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      id="email"
                      type="email"
                      placeholder="you@company.com"
                      autoComplete="email"
                      required
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {isLogin && (
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <div className="flex items-center justify-between gap-3">
                      <FormLabel>Password</FormLabel>
                    </div>
                    <FormControl>
                      <PassworInput
                        {...field}
                        id="password"
                        autoComplete="current-password"
                        required
                        inputMode="numeric"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <Button
              type="submit"
              className="mt-1 w-full"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  Verifying
                </>
              ) : (
                <>
                  {isLogin ? "Sign in" : "Create account"}
                  <ArrowRight className="size-3.5" />
                </>
              )}
            </Button>
          </form>
        </Form>
      </AuthPanel>
    </div>
  );
}
