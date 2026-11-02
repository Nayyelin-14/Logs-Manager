import * as React from "react";

import { Eye, EyeClosed } from "lucide-react";
import { cn } from "../../lib/utils";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";

function PassworInput({ className, ...props }: React.ComponentProps<"input">) {
  const [showpassword, setShowpassword] = React.useState<boolean>(false);

  return (
    <div className="relative">
      <Input
        type={showpassword ? "text" : "password"}
        data-slot="input"
        className={cn("pr-10", className)}
        {...props}
      />
      <Button
        type="button"
        onClick={() => setShowpassword((prev) => !prev)}
        variant="ghost"
        size="icon"
        className="absolute top-0.5 right-0.5 size-8 rounded-sm text-ink-muted hover:bg-surface-muted hover:text-ink"
        aria-label={showpassword ? "Hide password" : "Show password"}
        disabled={props.value === "" || props.disabled}
      >
        {showpassword ? (
          <Eye className="size-3.5" aria-hidden="true" />
        ) : (
          <EyeClosed className="size-3.5" aria-hidden="true" />
        )}
      </Button>
      <span className="sr-only">
        {showpassword ? "Hide Password" : "Show password"}
      </span>
    </div>
  );
}

export { PassworInput };
