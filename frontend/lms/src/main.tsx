import { createRoot } from "react-dom/client";
import "./index.css";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { queryClient } from "./api/query.ts";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { RouterProvider } from "react-router-dom";
import router from "./routes.tsx";

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
    <ReactQueryDevtools initialIsOpen={false} />
    <Toaster
      position="bottom-right"
      duration={5000}
      closeButton
      theme="dark"
      richColors
      style={{
        "--normal-bg": "#202c36",
        "--normal-text": "#f0eee8",
        "--normal-border": "#45545e",
      } as React.CSSProperties}
      toastOptions={{
        className:
          "rounded-md border border-border bg-card text-ink shadow-[0_16px_40px_-12px_rgba(0,0,0,0.45)] font-sans",
      }}
    />
  </QueryClientProvider>
);
