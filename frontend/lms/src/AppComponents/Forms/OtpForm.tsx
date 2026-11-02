import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  useActionData,
  useNavigation,
  useSubmit,
} from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { REGEXP_ONLY_DIGITS } from "input-otp";

import { cn } from "../../lib/utils";
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
import { AuthPanel } from "../layout/AuthPanel";

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
  const navigation = useNavigation();
  const actionData = useActionData() as {
    error?: string;
    message?: string;
  };

  const submitting = navigation.state === "submitting";
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
    <div className={cn("w-full", className)} {...props}>
      <AuthPanel
        eyebrow="Identity verification"
        title="Enter your code"
        description="Enter the six-digit one-time password sent to the phone number linked to your account."
        footer={
          <p className="text-center font-mono text-[9px] tracking-[0.08em] text-ink-muted uppercase">
            Codes expire shortly after they are issued
          </p>
        }
      >
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(OtpSubmit)}
            className="space-y-5"
          >
            <FormField
              control={form.control}
              name="otp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>One-time password</FormLabel>
                  <FormControl>
                    <InputOTP
                      maxLength={6}
                      {...field}
                      pattern={REGEXP_ONLY_DIGITS}
                      containerClassName="justify-between gap-1 sm:gap-2"
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
                    Digits only. Check your registered device if the code has
                    not arrived.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {actionData?.message && (
              <p className="rounded-sm border border-critical/20 bg-critical/10 px-2.5 py-2 text-[11px] text-critical">
                {actionData.message}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  Verifying
                </>
              ) : (
                "Verify code"
              )}
            </Button>
          </form>
        </Form>
      </AuthPanel>
    </div>
  );
}
