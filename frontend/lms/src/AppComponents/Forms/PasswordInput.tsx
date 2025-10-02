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
        variant={"ghost"}
        size="sm"
        className="absolute right-0 top-0 h-full cursor-pointer hover:bg-transparent"
        disabled={props.value === "" || props.disabled}
      >
        {showpassword ? (
          <Eye className="w-4 h-4" aria-hidden="true" />
        ) : (
          <EyeClosed className="w-4 h-4" aria-hidden="true" />
        )}
      </Button>
      <span className="sr-only">
        {showpassword ? "Hide Password" : "Show password"}
      </span>
    </div>
  );
}

export { PassworInput };
