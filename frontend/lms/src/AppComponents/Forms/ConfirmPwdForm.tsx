import { cn } from "../../lib/utils";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Link,
  useActionData,
  useNavigation,
  useSubmit,
} from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { useState } from "react";

import { PassworInput } from "./PasswordInput";
import { confirmPwdSchema } from "../../Schemas/AuthSchema";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Button } from "../../components/ui/button";
import { AuthPanel } from "../layout/AuthPanel";

export function ConfirmPwdForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";
  const actionData = useActionData() as { message?: string } | undefined;
  const [clientError, setClientError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof confirmPwdSchema>>({
    resolver: zodResolver(confirmPwdSchema),
    defaultValues: {
      password: "",
      confirmPassword: "",
    },
  });

  const passwordSubmit = (values: z.infer<typeof confirmPwdSchema>) => {
    if (values.password !== values.confirmPassword) {
      setClientError("Passwords do not match.");
      return;
    }
    setClientError(null);
    submit(values, { method: "post", action: "/register/confirm-password" });
  };

  return (
    <div className={cn("w-full", className)} {...props}>
      <AuthPanel
        eyebrow="Account security"
        title="Confirm your password"
        description="Set an 8-digit numeric password for your account. Both entries must match."
        footer={
          <p className="text-center text-xs text-ink-muted">
            <Link
              to="/register"
              className="font-medium text-ink underline underline-offset-4 hover:text-brand"
            >
              Back to registration
            </Link>
          </p>
        }
      >
        <Form {...form}>
          <form onSubmit={form.handleSubmit(passwordSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <PassworInput
                      {...field}
                      id="password"
                      autoComplete="new-password"
                      required
                      inputMode="numeric"
                    />
                  </FormControl>
                  <FormDescription>
                    Exactly 8 digits. Numbers only.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm password</FormLabel>
                  <FormControl>
                    <PassworInput
                      {...field}
                      id="confirmPassword"
                      autoComplete="new-password"
                      required
                      inputMode="numeric"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {actionData?.message && (
              <p className="rounded-sm border border-critical/20 bg-critical/10 px-2.5 py-2 text-[11px] text-critical">
                {actionData.message}
              </p>
            )}
            {clientError && (
              <p className="rounded-sm border border-critical/20 bg-critical/10 px-2.5 py-2 text-[11px] text-critical">
                {clientError}
              </p>
            )}

            <Button
              type="submit"
              className="mt-1 w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  Saving
                </>
              ) : (
                "Save password"
              )}
            </Button>
          </form>
        </Form>
      </AuthPanel>
    </div>
  );
}
