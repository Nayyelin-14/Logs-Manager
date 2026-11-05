import { Link, useNavigation, useSubmit } from "react-router-dom";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
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

export function LoginForm({ className, ...props }: React.ComponentProps<"div">) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const submitting = navigation.state === "submitting";
  const [showPassword, setShowPassword] = useState(false);

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
    <div className={cn("w-full min-h-screen bg-surface flex flex-col lg:hidden", className)} {...props}>
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md space-y-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              Sign in to Logs-Manager
            </h1>
            <p className="mt-2 text-sm text-ink-muted">
              Use your work email and password.
            </p>
          </div>
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
                        placeholder="name@company.com"
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
                    <div className="flex items-center justify-between">
                      <FormLabel>Password</FormLabel>
                      <Link
                        to="/forgot-password"
                        className="text-sm text-brand hover:underline"
                      >
                        Forgot password?
                      </Link>
                    </div>
                    <FormControl>
                      <div className="relative">
                        <Input
                          {...field}
                          id="password"
                          type={showPassword ? "text" : "password"}
                          autoComplete="current-password"
                          required
                          placeholder="••••••••••••"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-2 top-1/2 -translate-y-1/2 h-6 w-6"
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label={showPassword ? "Hide password" : "Show password"}
                        >
                          {showPassword ? (
                            <Eye className="h-4 w-4" />
                          ) : (
                            <EyeOff className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                    Verifying
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
          </Form>
          
          <p className="text-center text-sm text-ink-muted">
            New to Logs-Manager?{" "}
            <Link to="/register" className="text-brand hover:underline">
              Create an account
            </Link>
          </p>
          
          <div className="mt-8 pt-6 bg-surface-container-low rounded-xl p-3 flex items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-brand" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v14l5 5h7a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-7z" />
            </svg>
            <span className="text-sm text-ink-muted leading-tight">
              SOC2 Type II & HIPAA certified tenant partition isolation active.
            </span>
          </div>
          
          <div className="flex items-center justify-between text-ink-muted text-xs">
            <span>© 2026 Logs-Manager</span>
            <div className="flex items-center gap-4">
              <Link to="/privacy" className="hover:text-ink transition-colors">Privacy</Link>
              <span>·</span>
              <Link to="/terms" className="hover:text-ink transition-colors">Terms</Link>
              <span>·</span>
              <Link to="/status" className="hover:text-ink transition-colors">Status</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LoginFormDesktop({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("hidden lg:flex min-h-screen bg-inverse-surface flex-col relative overflow-hidden", className)} {...props}>
      <svg className="absolute inset-0 w-full h-full opacity-[0.04] pointer-events-none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern height="32" id="grid-pattern" patternUnits="userSpaceOnUse" width="32">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#FFFFFF" strokeWidth="1"></path>
          </pattern>
        </defs>
        <rect fill="url(#grid-pattern)" height="100%" width="100%"></rect>
      </svg>
      
      <div className="flex-1 flex items-center justify-center px-12">
        <div className="w-full max-w-[540px] flex flex-col items-center">
          <div className="w-full bg-[#131c1a] rounded-xl shadow-2xl p-5 font-code-sm text-code-sm">
            <div className="flex items-center justify-between pb-3.5 mb-3.5 bg-[#172320] -mx-5 -mt-5 px-5 pt-4 rounded-t-xl">
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary"></span>
                </span>
                <span className="text-sm font-medium text-inverse-on-surface">
                  Live events
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-outline-variant">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary-fixed"></span>
                <span>streaming · 142 eps</span>
              </div>
            </div>
            
            <div className="space-y-2.5 text-[11px] leading-relaxed text-[#c4d1cd] overflow-x-auto select-none">
              <div className="flex items-start gap-2 whitespace-nowrap hover:bg-[#1a2623] px-2 py-1 rounded transition-colors">
                <span className="text-outline-variant shrink-0">14:23:01.402</span>
                <span className="bg-primary/20 text-primary-fixed px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">INFO</span>
                <span className="text-inverse-on-surface">auth.login</span>
                <span className="text-secondary-fixed-dim">success</span>
                <span className="text-outline-variant">tenant=acme_corp</span>
                <span className="text-outline-variant">ip=192.168.1.42</span>
              </div>
              <div className="flex items-start gap-2 whitespace-nowrap hover:bg-[#1a2623] px-2 py-1 rounded transition-colors opacity-90">
                <span className="text-outline-variant shrink-0">14:23:02.115</span>
                <span className="bg-primary/20 text-primary-fixed px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">INFO</span>
                <span className="text-inverse-on-surface">session.verify</span>
                <span className="text-secondary-fixed-dim">token_valid</span>
                <span className="text-outline-variant">tenant=fintech_api</span>
                <span className="text-outline-variant">scope=read:logs</span>
              </div>
              <div className="flex items-start gap-2 whitespace-nowrap hover:bg-[#1a2623] px-2 py-1 rounded transition-colors">
                <span className="text-outline-variant shrink-0">14:23:02.890</span>
                <span className="bg-[#854d0e]/30 text-[#facc15] px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">WARN</span>
                <span className="text-inverse-on-surface">rate_limit.threshold</span>
                <span className="text-[#facc15]">84%</span>
                <span className="text-outline-variant">tenant=cloudscale</span>
                <span className="text-outline-variant">window=60s</span>
              </div>
              <div className="flex items-start gap-2 whitespace-nowrap hover:bg-[#1a2623] px-2 py-1 rounded transition-colors opacity-75">
                <span className="text-outline-variant shrink-0">14:23:03.042</span>
                <span className="bg-primary/20 text-primary-fixed px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">INFO</span>
                <span className="text-inverse-on-surface">kms.key_rotate</span>
                <span className="text-secondary-fixed-dim">cycle_ok</span>
                <span className="text-outline-variant">tenant=acme_corp</span>
                <span className="text-outline-variant">arn=aws:kms:...</span>
              </div>
              <div className="flex items-start gap-2 whitespace-nowrap opacity-90 hover:bg-[#1a2623] px-2 py-1 rounded transition-colors">
                <span className="text-outline-variant shrink-0">14:23:03.411</span>
                <span className="bg-error/30 text-error-container px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">ERROR</span>
                <span className="text-inverse-on-surface">auth.mfa_expired</span>
                <span className="text-error-container">retry=2</span>
                <span className="text-outline-variant">tenant=vault_sec</span>
                <span className="text-outline-variant">user=dev_ops</span>
              </div>
              <div className="flex items-start gap-2 whitespace-nowrap opacity-75 hover:bg-[#1a2623] px-2 py-1 rounded transition-colors">
                <span className="text-outline-variant shrink-0">14:23:04.008</span>
                <span className="bg-primary/20 text-primary-fixed px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider shrink-0">INFO</span>
                <span className="text-inverse-on-surface">audit.export_batch</span>
                <span className="text-secondary-fixed-dim">4.2k_events</span>
                <span className="text-outline-variant">tenant=sentinel_io</span>
              </div>
            </div>
            
            <div className="mt-4 pt-3 bg-[#0f1715] -mx-5 -mb-5 px-5 py-2.5 rounded-b-xl flex items-center justify-between font-code-sm text-[11px] text-outline-variant">
              <div className="flex items-center gap-1.5">
                <span className="text-primary-fixed font-bold">$</span>
                <span>lq --stream --filter="tenant=*"</span>
              </div>
              <span className="bg-surface-variant/10 text-outline-variant px-1.5 py-0.5 rounded text-[10px]">ESC to pause</span>
            </div>
          </div>
          
          <div className="w-full grid grid-cols-3 gap-3 mt-4">
            <div className="bg-[#131c1a] p-3 rounded-lg text-left">
              <span className="block text-[10px] text-outline-variant uppercase tracking-wider">Ingest Latency</span>
              <span className="text-2xl font-semibold text-inverse-on-surface">4.8ms</span>
            </div>
            <div className="bg-[#131c1a] p-3 rounded-lg text-left">
              <span className="block text-[10px] text-outline-variant uppercase tracking-wider">Partition Status</span>
              <span className="text-2xl font-semibold text-tertiary-fixed">100% OK</span>
            </div>
            <div className="bg-[#131c1a] p-3 rounded-lg text-left">
              <span className="block text-[10px] text-outline-variant uppercase tracking-wider">Query SLA</span>
              <span className="text-2xl font-semibold text-inverse-on-surface">&lt; 300ms</span>
            </div>
          </div>
          
          <div className="mt-8 text-center px-4">
            <h2 className="text-lg font-medium text-inverse-on-surface tracking-tight">
              Every event, every tenant, one clear timeline.
            </h2>
            <p className="text-sm text-inverse-on-surface-variant mt-1.5 max-w-[420px] mx-auto leading-relaxed">
              High-throughput audit ingestion with zero-lag queries and strict compliance isolation across production environments.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}