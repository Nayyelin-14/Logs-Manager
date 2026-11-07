import React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle } from "lucide-react";

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
import { Button } from "../../components/ui/button";
import {
  CreateSchema,
  type CreateUserFormInput,
  type CreateUserFormValues,
} from "../../Schemas/AuthSchema";
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
  const form = useForm<CreateUserFormInput, unknown, CreateUserFormValues>({
    resolver: zodResolver(CreateSchema),
    defaultValues: {
      username: "",
      role: "VIEWER",
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

  const onSubmit = form.handleSubmit((values) => createUser(values, {
    onSuccess: () => setOpen(false),
  }));

  if (formName !== "Create User") {
    return null;
  }

  return (
    <Form {...form}>
      <form onSubmit={onSubmit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Full name</FormLabel>
                <FormControl>
                  <Input placeholder="e.g. Maya Chen" autoComplete="off" {...field} className="h-10 rounded-xl border-border/60 bg-surface-container-low px-3.5 text-[13px] placeholder:text-ink-muted/40" />
                </FormControl>
                <FormDescription>
                  Display name used in audit views.
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
                <FormLabel>Work email address</FormLabel>
                <FormControl>
                  <Input
                    placeholder="e.g. maya.chen@company.com"
                    autoComplete="off"
                    {...field}
                    className="h-10 rounded-xl border-border/60 bg-surface-container-low px-3.5 text-[13px] placeholder:text-ink-muted/40"
                  />
                </FormControl>
                <FormDescription>Sign-in address for this account.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="tenant"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tenant scope</FormLabel>
                <FormControl>
                  <Input placeholder="e.g. demoA" autoComplete="off" {...field} className="h-10 rounded-xl border-border/60 bg-surface-container-low px-3.5 text-[13px] placeholder:text-ink-muted/40" />
                </FormControl>
                <FormDescription>
                  Workspace this account belongs to.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="role"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Role assignment</FormLabel>
                <FormControl>
                  <select
                    {...field}
                    className="h-10 w-full rounded-xl border border-border/60 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none transition-[border-color,box-shadow] hover:border-ink/20 focus-visible:border-brand focus-visible:ring-[3px] focus-visible:ring-brand/15"
                  >
                    <option value="VIEWER">Viewer</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </FormControl>
                <FormDescription>
                  Controls access to administration views.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Access password</FormLabel>
                <FormControl>
                  <PassworInput
                    {...field}
                    id="password"
                    autoComplete="new-password"
                    required
                    inputMode="numeric"
                    className="h-10 rounded-xl border-border/60 bg-surface-container-low text-[13px]"
                  />
                </FormControl>
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
                    className="h-10 rounded-xl border-border/60 bg-surface-container-low text-[13px]"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <Button type="submit" variant="signal" className="h-10 w-full rounded-xl shadow-md shadow-signal/20" disabled={userCreating}>
          {userCreating && <LoaderCircle className="size-3.5 animate-spin" />}
          {userCreating ? "Creating user" : "Create User"}
        </Button>
      </form>
    </Form>
  );
};

export default CreateForm;