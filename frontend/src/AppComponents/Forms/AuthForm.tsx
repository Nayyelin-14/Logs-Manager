import { useNavigation, useSubmit } from "react-router-dom";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";

import { cn } from "../../lib/utils";
import { LoginSchema } from "../../Schemas/AuthSchema";
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

export function AuthForm({ className, ...props }: React.ComponentProps<"div">) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const submitting = navigation.state === "submitting";

  const form = useForm<z.infer<typeof LoginSchema>>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: "", password: "" },
  });

  const authSubmit = (values: z.infer<typeof LoginSchema>) => {
    const formData = new FormData();
    Object.entries(values).forEach(([key, value]) => {
      formData.append(key, value as string);
    });

    submit(formData, { method: "post", action: "/login" });
  };

  return (
    <div className={cn("w-full", className)} {...props}>
      <AuthPanel
        eyebrow="Workspace access"
        title="Sign in to LogManager"
        description="Use your workspace credentials to open the security console."
        footer={
          <div className="space-y-3">
            <p className="text-center text-xs text-ink-muted">
              New to LogManager? Contact your administrator for access.
            </p>
          </div>
        }
      >
        <Form {...form}>
          <form onSubmit={form.handleSubmit(authSubmit)} className="space-y-4">
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
                  Sign in
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