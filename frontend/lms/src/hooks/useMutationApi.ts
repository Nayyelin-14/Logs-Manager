/* eslint-disable @typescript-eslint/no-explicit-any */

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "../api";

type IngestResponse = {
  success: boolean;
  eventId: string;
  message: string;
  event: any;
  alertTriggered: boolean;
  alerts: any[];
};

type MutationOptions<TData = any, _TVariables = any> = {
  endpoint: string | ((variables: _TVariables) => string);
  method?: "post" | "put" | "patch" | "delete";
  invalidateFn?: () => Promise<void>;
  successMessage?: string;
  errorMessage?: string;
  transformResponse?: (res: any) => TData;
};

export function useAppMutation<
  TData extends Partial<IngestResponse> = any,
  TVariables = any
>({
  endpoint,
  method = "post",
  invalidateFn,
  successMessage, // optional, fallback
  errorMessage = "Something went wrong. Please try again.",
  transformResponse,
}: MutationOptions<TData, TVariables>) {
  const { mutate, isPending } = useMutation<TData, any, TVariables>({
    mutationFn: async (payload: TVariables) => {
      const url = typeof endpoint === "function" ? endpoint(payload) : endpoint;
      const res = await (adminApi as any)[method](
        url,
        method === "delete" ? undefined : payload
      );
      console.log(res);
      return transformResponse ? transformResponse(res.data) : res.data;
    },
    onSuccess: async (data) => {
      if (invalidateFn) await invalidateFn();
      const msg = (data as any)?.message || successMessage || "Success";

      toast.success(msg);

      if (data?.alertTriggered && data.alerts?.length) {
        toast.warning(
          `⚠️ Alert triggered: ${
            data.alerts[0]?.title || "Check alerts for details"
          }`
        );
      } else if (data?.alertTriggered) {
        toast.warning(`⚠️ Alert triggered: Check alerts for details`);
      }
    },
    onError: (err: any) => {
      console.log(errorMessage, err);

      toast.error("Something went wrong");
    },
  });

  return { mutate, isPending };
}
