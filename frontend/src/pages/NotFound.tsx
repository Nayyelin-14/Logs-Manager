import { ArrowLeft, RefreshCcw, ShieldCheck } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";
import { useEffect } from "react";
import { Button } from "../components/ui/button";
import { Panel } from "../components/ui/panel";

const NotFound = () => {
  const error = useRouteError();
  const isRouteError = isRouteErrorResponse(error) && error.status === 404;
  const isError = error instanceof Error;
  const errorMessage = isError ? error.message : String(error ?? "Unknown error");
  const errorStack = isError ? error.stack : undefined;

  useEffect(() => {
    if (!isRouteError) {
      console.error("Route error:", error);
    }
  }, [error, isRouteError]);

  return (
    <div className="flex min-h-svh items-center justify-center bg-canvas px-4 py-10">
      <Panel className="w-full max-w-lg p-6 sm:p-8">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-sm bg-rail text-signal">
            <ShieldCheck className="size-[18px]" />
          </span>
          <div>
            <p className="text-sm font-semibold tracking-tight text-ink">
              LogManager
            </p>
            <p className="font-mono text-[8px] tracking-[0.16em] text-ink-muted uppercase">
              Security operations
            </p>
          </div>
        </div>

        <h1 className="mt-10 font-mono text-[10px] font-semibold tracking-[0.2em] text-ink-muted uppercase">
          {isRouteError ? "Error / 404" : "Application error"}
        </h1>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">
          {isRouteError ? "Route not found" : "This view could not be loaded"}
        </h1>
        <p className="mt-2 max-w-sm text-sm leading-6 text-ink-muted">
          {isRouteError
            ? "The requested console view does not exist or is no longer available."
            : "A page component failed to render. Retry the view; if it keeps failing, check the browser console and the API service."}
        </p>

        <div className="mt-10">
          <details className="border rounded-md p-4">
            <summary className="cursor-pointer text-sm font-medium text-ink-muted">
              Click to see technical error details
            </summary>
            <pre className="mt-2 text-xs font-mono text-ink-muted overflow-auto max-h-60">{isError ? (errorStack || errorMessage) : errorMessage}</pre>
          </details>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {!isRouteError && (
            <Button type="button" variant="outline" onClick={() => window.location.reload()}>
              <RefreshCcw className="size-3.5" />
              Retry view
            </Button>
          )}
          <Button asChild>
            <Link to="/">
              <ArrowLeft className="size-3.5" />
              Return to console
            </Link>
          </Button>
        </div>
      </Panel>
    </div>
  );
};

export default NotFound;
