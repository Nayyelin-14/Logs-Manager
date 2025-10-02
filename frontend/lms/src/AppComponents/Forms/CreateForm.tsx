import React from "react";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { useForm } from "react-hook-form";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { CreateSchema } from "../../Schemas/AuthSchema";
import { useAppMutation } from "../../hooks/useMutationApi";
import { invalidateAllDataCount, invalidateUserQueries } from "../../api/query";
import { PassworInput } from "./PasswordInput";
interface CreateFormProps {
  formName: string;
  setOpen: (open: boolean) => void;
  tenant: string;
}

const CreateForm: React.FC<CreateFormProps> = ({
  formName,
  setOpen,
  tenant,
}) => {
  const form = useForm<z.infer<typeof CreateSchema>>({
    resolver: zodResolver(CreateSchema),
    defaultValues: {
      username: "",
      role: "USER",
      email: "",
      tenant: "",
      password: "",
      confirmPassword: "",
    },
  });

  const { mutate: createUser, isPending: userCreating } = useAppMutation({
    endpoint: "/create-user",
    method: "post",
    invalidateFn: async () => {
      await invalidateUserQueries();
      await invalidateAllDataCount(tenant);
    },
    successMessage: "User has been created successfully.",
    errorMessage: "Failed to create user.",
  });

  function onSubmit(values: z.infer<typeof CreateSchema>) {
    console.log(values);
    createUser(values, {
      onSuccess: () => {
        setOpen(false); // <-- close the dialog
      },
    });
  }
  if (formName === "Create User") {
    return (
      <div>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
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
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input placeholder="abc@gmail.com" {...field} />
                  </FormControl>
                  <FormDescription>Please enter a valid email</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex items-center gap-5">
              <FormField
                control={form.control}
                name="tenant"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tenant</FormLabel>
                    <FormControl>
                      <Input placeholder="demoA" {...field} />
                    </FormControl>
                    <FormDescription>
                      Please enter a valid tenant
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="role" // make sure your schema includes "role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Role</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="border border-gray-300 rounded-lg px-3 py-2 w-full"
                      >
                        <option value="">Select a role</option>
                        <option value="USER">User</option>
                        <option value="ADMIN">Admin</option>
                      </select>
                    </FormControl>
                    <FormDescription>
                      Select the role for this user.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="flex gap-3 items-center">
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
                        id="confirmPassword"
                        required
                        inputMode="numeric"
                      />
                    </FormControl>

                    <FormMessage />
                  </FormItem>
                )}
              />{" "}
            </div>
            <Button type="submit" disabled={userCreating}>
              {userCreating ? "Creating..." : "Create"}
            </Button>
          </form>
        </Form>
      </div>
    );
  }
};

export default CreateForm;
