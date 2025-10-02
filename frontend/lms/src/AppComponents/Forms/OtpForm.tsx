import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { z } from "zod";

import {
  Link,
  useActionData,
  useNavigation,
  useSubmit,
} from "react-router-dom";
import { cn } from "../../lib/utils";
import { LoaderCircle, LockIcon } from "lucide-react";
import { REGEXP_ONLY_DIGITS } from "input-otp";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "../../components/ui/input-otp";
import { Button } from "../../components/ui/button";

const OtpSchema = z.object({
  otp: z.string().min(6, {
    message: "Your one-time password must be 6 characters.",
  }),
});

export function InputOTPForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const submit = useSubmit();
  const navigate = useNavigation();
  const actionData = useActionData() as {
    error?: string;
    message?: string;
  };

  const submitting = navigate.state === "submitting";
  const form = useForm<z.infer<typeof OtpSchema>>({
    resolver: zodResolver(OtpSchema),
    defaultValues: {
      otp: "",
    },
  });

  function OtpSubmit(data: z.infer<typeof OtpSchema>) {
    submit(data, { method: "post", action: "/register/otp" });
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2">
          <Link to="#" className="flex flex-col items-center gap-2 font-medium">
            <div className="flex size-8 items-center justify-center rounded-md">
              <LockIcon className="h-10 w-10" aria-hidden="true" />
            </div>
            <span className="sr-only">Otp Verify form</span>
          </Link>
          <h1 className="text-xl font-bold my-5">
            We had sent OTP to your Phone
          </h1>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(OtpSubmit)}
              className="w-2/3 space-y-6"
            >
              <FormField
                control={form.control}
                name="otp"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>One-Time Password</FormLabel>
                    <FormControl>
                      <InputOTP
                        maxLength={6}
                        {...field}
                        pattern={REGEXP_ONLY_DIGITS}
                      >
                        <InputOTPGroup>
                          <InputOTPSlot index={0} />
                          <InputOTPSlot index={1} />
                        </InputOTPGroup>
                        <InputOTPSeparator />
                        <InputOTPGroup>
                          <InputOTPSlot index={2} />
                          <InputOTPSlot index={3} />
                        </InputOTPGroup>
                        <InputOTPSeparator />
                        <InputOTPGroup>
                          <InputOTPSlot index={4} />
                          <InputOTPSlot index={5} />
                        </InputOTPGroup>
                      </InputOTP>
                    </FormControl>
                    <FormDescription>
                      Please enter the one-time password sent to your phone.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {actionData && (
                <p className="text-sm text-red-700">{actionData?.message}</p>
              )}
              <Button
                type="submit"
                className={cn(
                  `${
                    submitting && "bg-gray-300 text-black"
                  } w-full cursor-pointer hover:bg-black/60`
                )}
                disabled={submitting}
              >
                {submitting ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  "Verify"
                )}
              </Button>
            </form>
          </Form>
        </div>
      </div>
    </div>
  );
}
