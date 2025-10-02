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

import { LoaderCircle, LockIcon } from "lucide-react";
import { PassworInput } from "./PasswordInput";
import { useState } from "react";
import { confirmPwdSchema } from "../../Schemas/AuthSchema";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Button } from "../../components/ui/button";
export function ConfirmPwdForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const submit = useSubmit();
  const navigate = useNavigation();
  const isSubmitting = navigate.state === "submitting";
  const actionData = useActionData();
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
      setClientError("Password is not match");
      return;
    }
    setClientError(null);
    submit(values, { method: "post", action: "/register/confirm-password" }); // dot (.) means current route , cause form under register page with index true
    console.log(values);
  };

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2">
          <a href="#" className="flex flex-col items-center gap-2 font-medium">
            <div className="flex size-8 items-center justify-center rounded-md">
              <LockIcon className="h-10 w-10" aria-hidden="true" />
            </div>
            <span className="sr-only">Confirm password</span>
          </a>
          <h1 className="text-xl font-bold">Confirm your password</h1>
          <div className="text-center text-sm">
            <p className="font-semibold">
              Password must be 8 digits long and contain only numbers. They must
              match
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-6">
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(passwordSubmit)}
              className="space-y-6"
            >
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
                        required
                        inputMode="numeric"
                      />
                    </FormControl>

                    <FormMessage />
                  </FormItem>
                )}
              />{" "}
              <FormField
                control={form.control}
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm Password</FormLabel>
                    <FormControl>
                      <PassworInput
                        {...field}
                        id="phone"
                        required
                        inputMode="numeric"
                      />
                    </FormControl>

                    <FormMessage />
                  </FormItem>
                )}
              />
              {actionData && (
                <div className="flex items-center gap-4">
                  <p className="text-sm text-red-700">{actionData?.message}</p>
                  <Link
                    to={"/register"}
                    className="text-sm hover:underline cursor-pointer"
                  >
                    Go back to register
                  </Link>
                </div>
              )}
              {clientError && (
                <p className="text-sm text-red-700">{clientError}</p>
              )}
              <Button
                type="submit"
                className={cn(
                  `${
                    isSubmitting && "bg-gray-300 text-black"
                  } w-full cursor-pointer hover:bg-black/60`
                )}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  "Submit"
                )}
              </Button>
            </form>
          </Form>
        </div>
      </div>

      <div className="text-muted-foreground *:[a]:hover:text-primary text-center text-xs text-balance *:[a]:underline *:[a]:underline-offset-4">
        By clicking continue, you agree to our
        <Link to="#">Terms of Service</Link> and{" "}
        <Link to="#">Privacy Policy</Link>.
      </div>
    </div>
  );
}
