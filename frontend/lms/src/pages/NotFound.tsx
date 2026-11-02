import { ArrowLeft, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../components/ui/button";
import { Panel } from "../components/ui/panel";

const NotFound = () => {
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

        <p className="mt-10 font-mono text-[10px] font-semibold tracking-[0.2em] text-ink-muted uppercase">
          Error / 404
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">
          Route not found
        </h1>
        <p className="mt-2 max-w-sm text-sm leading-6 text-ink-muted">
          The requested console view does not exist or is no longer available.
        </p>

        <Button asChild className="mt-6">
          <Link to="/">
            <ArrowLeft className="size-3.5" />
            Return to console
          </Link>
        </Button>
      </Panel>
    </div>
  );
};

export default NotFound;
