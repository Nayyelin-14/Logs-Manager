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
    <ReactQueryDevtools initialIsOpen={true} />
    <Toaster
      position="bottom-right"
      richColors={true}
      duration={5000}
      closeButton
    />
  </QueryClientProvider>
);
