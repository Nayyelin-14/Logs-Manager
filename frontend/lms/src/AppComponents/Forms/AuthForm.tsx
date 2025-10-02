import {
  Link,
  //   useActionData,
  useNavigation,
  useSubmit,
} from "react-router-dom";
import { cn } from "../../lib/utils";

import { useForm } from "react-hook-form";
import type { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { LoaderCircle } from "lucide-react";
import { LoginSchema, RegisterSchema } from "../../Schemas/AuthSchema";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { PassworInput } from "./PasswordInput";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../components/ui/card";

type FormName = "login" | "register";
interface AuthFormProps extends React.ComponentProps<"div"> {
  formName: FormName;
}
export function AuthForm({ formName, className, ...props }: AuthFormProps) {
  const submit = useSubmit();
  const navigate = useNavigation();
  //   const actionData = useActionData() as { error?: string; message?: string };
  const submitting = navigate.state === "submitting";

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

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center w-full",
        className
      )}
      {...props}
    >
      <Card className="overflow-hidden  w-[80%] xl:w-[50%] mb-4">
        <CardHeader>
          <div className="flex flex-col items-center text-center">
            <h1 className="text-2xl font-bold">Welcome</h1>
            <p className="text-balance text-muted-foreground">
              Enter your email number below
            </p>
          </div>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(authSubmit)}
              className="space-y-6"
            >
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
                        type="text"
                        placeholder="abc@gmail.com"
                        required
                      />
                    </FormControl>
                    <FormDescription>
                      This is your public display name.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {formName === "login" && (
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center">
                        <FormLabel>Password</FormLabel>
                        <Link
                          to="/reset-password"
                          className="ml-auto text-sm underline-offset-2 hover:underline"
                        >
                          Forgot your password?
                        </Link>
                      </div>
                      <FormControl>
                        <PassworInput
                          {...field}
                          id="password"
                          required
                          inputMode="numeric"
                        />
                      </FormControl>
                      <FormDescription>
                        This is your public display name.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
              {formName === "register" && (
                <>
                  <FormField
                    control={form.control}
                    name="username"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Username</FormLabel>
                        <FormControl>
                          <Input placeholder="shadcn" {...field} />
                        </FormControl>
                        <FormDescription>
                          This is your public display name.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="tenant"
                    render={({ field }) => (
                      <FormItem className="w-[50%]">
                        <FormLabel>Tenant</FormLabel>
                        <FormControl>
                          <Input placeholder="demoA" {...field} />
                        </FormControl>
                        <FormDescription>
                          Please enter a valid email
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </>
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
                  `${formName === "login" ? "Sign In" : "Sign Up"}`
                )}
              </Button>
            </form>
          </Form>

          <div className="flex flex-col gap-4 mt-5">
            <div className="text-center text-sm">
              {formName === "login"
                ? " Don&apos;t have an account? "
                : "Already had an account? "}

              <Link
                to={formName === "login" ? "/register" : "/login"}
                className="underline underline-offset-4"
              >
                {formName === "login" ? "Sign Up" : "Sign In"}
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
      <div className="text-balance  text-center text-xs text-muted-foreground [&_a]:underline [&_a]:underline-offset-4 hover:[&_a]:text-primary">
        By clicking continue, you agree to our <a href="#">Terms of Service</a>{" "}
        and <a href="#">Privacy Policy</a>.
      </div>
    </div>
  );
}
