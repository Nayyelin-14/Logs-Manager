import { Calendar, ChevronDown, X } from "lucide-react";
import "react-day-picker/style.css";
import { DayPicker } from "react-day-picker";

import { Button } from "../../../components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../../components/ui/popover";
import { cn } from "../../../lib/utils";

interface DateFilterPopoverProps {
  value?: string;
  selected?: Date;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (date: Date) => void;
  format?: "iso" | "locale";
  id?: string;
  buttonClassName?: string;
}

export function DateFilterPopover({
  value,
  selected,
  open,
  onOpenChange,
  onSelect,
  format = "iso",
  id,
  buttonClassName,
}: DateFilterPopoverProps) {
  const label = value
    ? format === "locale"
      ? new Date(value).toLocaleDateString()
      : new Date(value).toISOString().split("T")[0]
    : "Any date";

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          id={id}
          className={cn(
            "h-9 justify-start gap-2 border-input px-2.5 text-[13px] font-normal",
            value && "border-brand/30 bg-brand-soft text-brand-hover",
            buttonClassName
          )}
        >
          <Calendar className="size-3.5" />
          <span className="font-mono text-[11px]">{label}</span>
          <ChevronDown className="ml-auto size-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto overflow-hidden p-0" align="start">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <p className="font-mono text-[9px] font-semibold tracking-[0.14em] text-ink-muted uppercase">
            Filter by date
          </p>
          {value && (
            <span className="inline-flex items-center gap-1 text-[10px] text-ink-muted">
              <X className="size-3" />
              Applied
            </span>
          )}
        </div>
        <DayPicker
          animate
          mode="single"
          selected={selected}
          onSelect={(date) => {
            if (date) onSelect(date);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
